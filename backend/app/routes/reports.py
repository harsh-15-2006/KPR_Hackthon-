"""Report generation from authoritative stored data.

Numerical content comes from the database and OR-Tools only. The AI is
never used to produce a figure in a report.
"""
import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.fault_tolerance import health_snapshot
from app.db.session import db_status, get_db
from app.models.action import ReductionAction
from app.models.optimization import Scenario
from app.services import hotspot_service
from app.services import optimization_service as opt
from app.services.emission_service import list_records

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _build_report(db: Session) -> dict:
    s = get_settings()
    try:
        summary = hotspot_service.build_summary(db)
        carbon = {
            "total_co2e_kg": summary.total_co2e,
            "record_count": summary.record_count,
            "highest_source": summary.highest_source_label,
            "highest_source_pct": summary.highest_source_pct,
            "by_source": [
                {
                    "source": b.source, "label": b.label, "co2e_kg": b.co2e,
                    "contribution_pct": b.contribution_pct, "records": b.record_count,
                }
                for b in summary.by_source
            ],
            "calculation_note": summary.calculation_note,
        }
    except ValueError as exc:
        carbon = {"error": str(exc)}

    records = list_records(db)
    actions = db.scalars(select(ReductionAction)).all()
    run = opt.latest_run(db, baseline_only=True)
    scenarios = db.scalars(select(Scenario).order_by(Scenario.created_at.desc()).limit(10)).all()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "Industrial Carbon Intelligence Report",
        "operational_data": {
            "record_count": len(records),
            "records": [
                {
                    "source": r.source, "activity_type": r.activity_type,
                    "activity_value": r.activity_value, "activity_unit": r.activity_unit,
                    "co2e_kg": r.co2e, "data_class": r.calculation_source,
                    "factor_reference": r.emission_factor_reference,
                    "period": r.period,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records[:500]
            ],
        },
        "data_sources": s.integration_status(),
        "data_provenance": {
            "database": db_status(),
            "source_health": health_snapshot(db),
            "classes": {
                "measured": "reported/measured by an external regulated source",
                "api_derived": "returned by an external API",
                "calculated": "computed by this system",
                "demo_assumption": "prototype assumption, NOT a measurement",
            },
        },
        "carbon_summary": carbon,
        "hotspots": carbon.get("by_source", []),
        "reduction_actions": [
            {
                "id": a.id, "action_name": a.action_name, "source": a.source,
                "cost": a.cost, "expected_reduction": a.expected_reduction,
                "maximum_capacity": a.maximum_capacity, "availability": a.availability,
                "implementation_time": a.implementation_time,
                "is_demo_assumption": a.is_demo_assumption,
                "evidence_source": a.evidence_source,
                "action_version": a.action_version,
            }
            for a in actions
        ],
        "demo_assumptions": [
            {"action_name": a.action_name, "evidence_source": a.evidence_source}
            for a in actions if a.is_demo_assumption
        ],
        "optimization_result": opt.run_to_dict(db, run) if run else None,
        "scenarios": [
            {
                "scenario_id": sc.id, "name": sc.name,
                "baseline_run_id": sc.baseline_run_id, "result_run_id": sc.result_run_id,
                "modified_budget": sc.modified_budget,
                "created_at": sc.created_at.isoformat() if sc.created_at else None,
            }
            for sc in scenarios
        ],
        "reoptimization_history": opt.reoptimization_history(db, 10),
        "methodology": {
            "emissions": "Activity data x emission factor, or measured values where the source provides them.",
            "hotspots": "Deterministic: source_co2e / total_co2e * 100. Not a prediction.",
            "optimization": "Google OR-Tools CP-SAT. Maximize expected CO2e reduction subject to budget and configured business constraints.",
            "ai": "Gemini explains stored results only. It never produces a figure in this report.",
        },
        "limitations": [
            "Reduction action costs and expected reductions are configured project assumptions unless an evidence source states otherwise.",
            "Demo Mode emission factors are illustrative, not measurements.",
            "The data-trust layer flags implausible records; it does not prove any figure is truthful.",
            "EPA CAMPD covers US power-sector facilities only and is an optional reference connector.",
            "Electricity Maps reports GRID carbon intensity, not a facility's own consumption.",
        ],
    }


@router.post("/generate")
def generate(db: Session = Depends(get_db)) -> dict:
    return _build_report(db)


@router.get("/latest")
def latest(db: Session = Depends(get_db)) -> dict:
    return _build_report(db)


@router.get("/csv")
def export_csv(db: Session = Depends(get_db)) -> Response:
    """CSV of the optimization allocation - values identical to the database."""
    rep = _build_report(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Industrial Carbon Intelligence Report"])
    w.writerow(["Generated at", rep["generated_at"]])
    w.writerow([])
    w.writerow(["CARBON SUMMARY"])
    cs = rep["carbon_summary"]
    w.writerow(["Total CO2e (kg)", cs.get("total_co2e_kg")])
    w.writerow(["Records", cs.get("record_count")])
    w.writerow(["Highest source", cs.get("highest_source"), cs.get("highest_source_pct")])
    w.writerow([])
    w.writerow(["HOTSPOTS"])
    w.writerow(["Source", "CO2e (kg)", "Contribution %", "Records"])
    for b in rep.get("hotspots", []):
        w.writerow([b["label"], b["co2e_kg"], b["contribution_pct"], b["records"]])
    w.writerow([])
    opt_res = rep.get("optimization_result")
    if opt_res:
        w.writerow(["OPTIMIZATION RESULT"])
        w.writerow(["Solver", opt_res["solver"], opt_res["solver_status"]])
        w.writerow(["Budget", opt_res["budget"]])
        w.writerow(["Total cost", opt_res["total_cost"]])
        w.writerow(["Expected reduction (tCO2e)", opt_res["expected_reduction"]])
        w.writerow(["Unused budget", opt_res["unused_budget"]])
        w.writerow([])
        w.writerow(["ALLOCATION"])
        w.writerow(["Action", "Source", "Selected", "Units", "Cost", "Expected reduction", "Reason if not selected"])
        for a in opt_res["allocations"]:
            w.writerow([
                a["action_name"], a["emission_source"], "YES" if a["selected"] else "NO",
                a["units"], a["allocated_cost"], a["expected_reduction"],
                a["rejection_reason"] or "",
            ])
    else:
        w.writerow(["OPTIMIZATION RESULT", "No optimization has been run yet."])
    w.writerow([])
    w.writerow(["DEMO ASSUMPTIONS"])
    w.writerow(["Action", "Evidence source"])
    for d in rep["demo_assumptions"]:
        w.writerow([d["action_name"], d["evidence_source"]])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="carbon_report.csv"'},
    )


@router.get("/html")
def export_html(db: Session = Depends(get_db)) -> Response:
    """Printable HTML report. Use the browser's Print to PDF to produce a PDF.

    A dedicated PDF engine is deliberately not added: this keeps the report
    values identical to the database with no extra dependency.
    """
    r = _build_report(db)
    cs = r["carbon_summary"]
    o = r.get("optimization_result")

    def rows(items, cols):
        return "".join(
            "<tr>" + "".join(f"<td>{'' if it.get(c) is None else it.get(c)}</td>" for c in cols) + "</tr>"
            for it in items
        )

    alloc_html = (
        "<p><em>No optimization has been run yet.</em></p>" if not o else f"""
      <table><thead><tr><th>Action</th><th>Source</th><th>Selected</th><th>Units</th>
      <th>Cost</th><th>Expected reduction</th></tr></thead><tbody>
      {"".join(f"<tr><td>{a['action_name']}</td><td>{a['emission_source']}</td>"
               f"<td>{'YES' if a['selected'] else 'no'}</td><td>{a['units']}</td>"
               f"<td>{a['allocated_cost']}</td><td>{a['expected_reduction']}</td></tr>"
               for a in o['allocations'])}
      </tbody></table>
      <p><strong>Solver:</strong> {o['solver']} ({o['solver_status']}) &middot;
         <strong>Budget:</strong> {o['budget']} &middot;
         <strong>Spent:</strong> {o['total_cost']} &middot;
         <strong>Reduction:</strong> {o['expected_reduction']} tCO2e</p>""")

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Industrial Carbon Intelligence Report</title>
<style>
 body{{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;margin:32px;color:#101828;}}
 h1{{font-size:22px;margin-bottom:2px}} h2{{font-size:15px;margin-top:26px;border-bottom:1px solid #e4e7ec;padding-bottom:5px}}
 table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:8px}}
 th,td{{border:1px solid #e4e7ec;padding:5px 7px;text-align:left}} th{{background:#f9fafb}}
 .muted{{color:#667085;font-size:12px}} .warn{{background:#fffaeb;border:1px solid #fedf89;padding:8px;font-size:12px;border-radius:6px}}
 @media print {{ body {{ margin: 12mm }} }}
</style></head><body>
<h1>Industrial Carbon Intelligence Report</h1>
<p class="muted">Generated {r['generated_at']}</p>

<h2>Carbon summary</h2>
<p>Total <strong>{cs.get('total_co2e_kg', 'n/a')} kg CO2e</strong> across {cs.get('record_count', 0)} record(s).
Highest source: <strong>{cs.get('highest_source') or 'n/a'}</strong> ({cs.get('highest_source_pct') or 0}%).</p>
<p class="muted">{cs.get('calculation_note','')}</p>

<h2>Hotspots</h2>
<table><thead><tr><th>Source</th><th>CO2e (kg)</th><th>Contribution %</th><th>Records</th></tr></thead>
<tbody>{rows(r.get('hotspots', []), ['label','co2e_kg','contribution_pct','records'])}</tbody></table>

<h2>Optimization result</h2>
{alloc_html}

<h2>Reduction actions</h2>
<table><thead><tr><th>Action</th><th>Source</th><th>Cost</th><th>Expected reduction</th><th>Demo assumption</th></tr></thead>
<tbody>{"".join(f"<tr><td>{a['action_name']}</td><td>{a['source']}</td><td>{a['cost']}</td>"
                f"<td>{a['expected_reduction']}</td><td>{'YES' if a['is_demo_assumption'] else 'no'}</td></tr>"
                for a in r['reduction_actions'])}</tbody></table>

<h2>Assumptions and limitations</h2>
<div class="warn"><strong>{len(r['demo_assumptions'])} of {len(r['reduction_actions'])} actions use DEMO ASSUMPTION values.</strong>
These are prototype assumptions, not industrial measurements.</div>
<ul class="muted">{"".join(f"<li>{x}</li>" for x in r['limitations'])}</ul>

<h2>Methodology</h2>
<ul class="muted">{"".join(f"<li><strong>{k}:</strong> {v}</li>" for k,v in r['methodology'].items())}</ul>
<p class="muted">To save as PDF: use your browser's Print dialog and choose "Save as PDF".</p>
</body></html>"""
    return Response(content=html, media_type="text/html")
