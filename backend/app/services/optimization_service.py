"""Bridge between the database and the CP-SAT optimizer.

OR-Tools is authoritative. Nothing in this module (and no AI) adjusts the
allocation the solver returns. Every run is persisted with a snapshot of
the actions and constraints it used, so results stay reproducible after
the library is edited.
"""
import json
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.action import ReductionAction
from app.models.optimization import (
    BusinessConstraintRow,
    OptimizationAllocation,
    OptimizationRun,
    ReoptimizationRun,
    Scenario,
)
from app.optimization.models import Action, BusinessConstraint, ParameterType
from app.optimization.optimizer import STATUS_EXPLANATION, optimize

logger = get_logger(__name__)


def _json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def load_actions(db: Session, overrides: dict[str, dict] | None = None) -> list[Action]:
    """DB rows -> optimizer Action objects, with optional scenario overrides.

    Overrides are applied in memory ONLY. The stored action library is never
    mutated by a what-if.
    """
    overrides = overrides or {}
    rows = db.scalars(select(ReductionAction)).all()
    out: list[Action] = []
    for r in rows:
        ov = overrides.get(str(r.id), {})
        out.append(
            Action(
                id=str(r.id),
                name=r.action_name,
                emission_source=r.source,
                cost=float(ov.get("cost", r.cost) or 0.0),
                expected_reduction=float(
                    ov.get("expected_reduction", r.expected_reduction) or 0.0
                ),
                maximum_capacity=int(ov.get("maximum_capacity", r.maximum_capacity) or 1),
                availability=str(ov.get("availability", r.availability)),
                parameter_type=(
                    ParameterType.INTEGER
                    if str(ov.get("parameter_type", r.parameter_type)) == "integer"
                    else ParameterType.BINARY
                ),
                is_demo_assumption=bool(r.is_demo_assumption),
            )
        )
    return out


def load_constraints(db: Session, extra: list[dict] | None = None) -> list[BusinessConstraint]:
    rows = db.scalars(
        select(BusinessConstraintRow).where(BusinessConstraintRow.is_active.is_(True))
    ).all()
    out = [
        BusinessConstraint(
            name=r.name,
            constraint_type=r.constraint_type,
            emission_source=r.emission_source,
            action_ids=tuple(str(a) for a in _json_list(r.action_ids)),
            numeric_value=r.numeric_value,
            is_active=r.is_active,
        )
        for r in rows
    ]
    for e in extra or []:
        out.append(
            BusinessConstraint(
                name=e.get("name", "scenario constraint"),
                constraint_type=e.get("constraint_type", ""),
                emission_source=e.get("emission_source"),
                action_ids=tuple(str(a) for a in (e.get("action_ids") or [])),
                numeric_value=e.get("numeric_value"),
                is_active=bool(e.get("is_active", True)),
            )
        )
    return out


def run_optimization(
    db: Session,
    budget: float,
    scope_key: str = "default",
    trigger_reason: str = "manual",
    is_baseline: bool = True,
    scenario_id: int | None = None,
    action_overrides: dict[str, dict] | None = None,
    extra_constraints: list[dict] | None = None,
) -> OptimizationRun:
    """Solve, persist and return the run. Always persists, even INFEASIBLE."""
    actions = load_actions(db, action_overrides)
    constraints = load_constraints(db, extra_constraints)

    result = optimize(actions, budget, constraints)

    run = OptimizationRun(
        scope_key=scope_key,
        budget=budget,
        solver=result.solver,
        solver_version=result.solver_version,
        solver_status=result.solver_status.value,
        total_cost=result.total_cost,
        expected_reduction=result.expected_reduction,
        unused_budget=result.unused_budget,
        budget_utilization=result.budget_utilization,
        objective_value=result.objective_value,
        best_bound=result.best_bound,
        wall_time_seconds=result.wall_time_seconds,
        actions_snapshot=json.dumps([asdict(a) for a in actions], default=str),
        constraints_snapshot=json.dumps([asdict(c) for c in constraints], default=str),
        constraints_applied=json.dumps(result.constraints_applied),
        message=result.message,
        trigger_reason=trigger_reason,
        is_baseline=is_baseline,
        scenario_id=scenario_id,
    )
    db.add(run)
    db.flush()

    for al in result.allocations:
        db.add(
            OptimizationAllocation(
                run_id=run.id,
                action_id=al.action_id,
                action_name=al.action_name,
                emission_source=al.emission_source,
                selected=al.selected,
                units=al.units,
                allocated_cost=al.allocated_cost,
                expected_reduction=al.expected_reduction,
                reduction_per_cost=al.reduction_per_cost,
                rejection_reason=al.rejection_reason,
            )
        )
    db.commit()
    db.refresh(run)
    logger.info(
        "Optimization stored",
        extra={"event": "optimization", "run_id": str(run.id), "status": run.solver_status},
    )
    return run


def run_to_dict(db: Session, run: OptimizationRun) -> dict[str, Any]:
    allocs = db.scalars(
        select(OptimizationAllocation).where(OptimizationAllocation.run_id == run.id)
    ).all()
    by_source_cost: dict[str, float] = {}
    by_source_red: dict[str, float] = {}
    for a in allocs:
        if a.selected:
            by_source_cost[a.emission_source] = round(
                by_source_cost.get(a.emission_source, 0.0) + a.allocated_cost, 4
            )
            by_source_red[a.emission_source] = round(
                by_source_red.get(a.emission_source, 0.0) + a.expected_reduction, 4
            )
    return {
        "run_id": run.id,
        "scope_key": run.scope_key,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "budget": run.budget,
        "solver": run.solver,
        "solver_version": run.solver_version,
        "solver_status": run.solver_status,
        "status_explanation": STATUS_EXPLANATION.get(run.solver_status, run.message),
        "message": run.message,
        "total_cost": run.total_cost,
        "expected_reduction": run.expected_reduction,
        "unused_budget": run.unused_budget,
        "budget_utilization": run.budget_utilization,
        "objective_value": run.objective_value,
        "best_bound": run.best_bound,
        "proven_optimal": run.solver_status == "OPTIMAL",
        "wall_time_seconds": run.wall_time_seconds,
        "trigger_reason": run.trigger_reason,
        "is_baseline": run.is_baseline,
        "scenario_id": run.scenario_id,
        "constraints_applied": _json_list(run.constraints_applied),
        "allocation_by_source": by_source_cost,
        "reduction_by_source": by_source_red,
        "allocations": [
            {
                "action_id": a.action_id,
                "action_name": a.action_name,
                "emission_source": a.emission_source,
                "selected": a.selected,
                "units": a.units,
                "allocated_cost": a.allocated_cost,
                "expected_reduction": a.expected_reduction,
                "reduction_per_cost": a.reduction_per_cost,
                "rejection_reason": a.rejection_reason,
            }
            for a in allocs
        ],
        # Units are stated explicitly so no consumer - including the AI
        # explanation layer - has to guess them.
        "units": {
            "budget": "INR lakh",
            "total_cost": "INR lakh",
            "unused_budget": "INR lakh",
            "allocated_cost": "INR lakh",
            "expected_reduction": "tCO2e",
            "reduction_per_cost": "tCO2e per INR lakh",
            "budget_utilization": "percent",
        },
        "note": (
            "Allocation decided by Google OR-Tools CP-SAT. Action costs and "
            "reductions are configured project assumptions unless marked otherwise."
        ),
    }


def latest_run(
    db: Session, baseline_only: bool = True, scope_key: str | None = None
) -> OptimizationRun | None:
    stmt = select(OptimizationRun).order_by(
        OptimizationRun.created_at.desc(), OptimizationRun.id.desc()
    )
    if scope_key and scope_key != "__ALL__":
        stmt = stmt.where(OptimizationRun.scope_key == scope_key)
    if baseline_only:
        stmt = stmt.where(OptimizationRun.is_baseline.is_(True))
    return db.scalars(stmt.limit(1)).first()


def get_run(db: Session, run_id: int) -> OptimizationRun | None:
    return db.get(OptimizationRun, run_id)


def compare_runs(db: Session, old: OptimizationRun | None, new: OptimizationRun) -> dict[str, Any]:
    """Structured diff between two runs, for What-If and Re-optimization."""
    new_d = run_to_dict(db, new)
    if old is None:
        return {"baseline": None, "scenario": new_d, "changed": True, "delta": None}
    old_d = run_to_dict(db, old)

    old_sel = {a["action_name"] for a in old_d["allocations"] if a["selected"]}
    new_sel = {a["action_name"] for a in new_d["allocations"] if a["selected"]}

    return {
        "baseline": old_d,
        "scenario": new_d,
        "changed": old_sel != new_sel
        or abs(old_d["expected_reduction"] - new_d["expected_reduction"]) > 1e-9,
        "delta": {
            "budget": round(new_d["budget"] - old_d["budget"], 4),
            "expected_reduction": round(
                new_d["expected_reduction"] - old_d["expected_reduction"], 4
            ),
            "total_cost": round(new_d["total_cost"] - old_d["total_cost"], 4),
            "unused_budget": round(new_d["unused_budget"] - old_d["unused_budget"], 4),
            "budget_utilization": round(
                new_d["budget_utilization"] - old_d["budget_utilization"], 2
            ),
            "actions_added": sorted(new_sel - old_sel),
            "actions_removed": sorted(old_sel - new_sel),
            "actions_unchanged": sorted(old_sel & new_sel),
        },
    }


def create_scenario(
    db: Session,
    name: str,
    budget: float | None,
    overrides: dict[str, dict] | None,
    extra_constraints: list[dict] | None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Clone the baseline, apply overrides, re-solve. Baseline is untouched."""
    baseline = latest_run(db, baseline_only=True)
    effective_budget = budget if budget is not None else (baseline.budget if baseline else 0.0)

    sc = Scenario(
        name=name,
        baseline_run_id=baseline.id if baseline else None,
        modified_budget=effective_budget,
        overrides=json.dumps(
            {"actions": overrides or {}, "constraints": extra_constraints or []}, default=str
        ),
        notes=notes,
    )
    db.add(sc)
    db.flush()

    run = run_optimization(
        db,
        budget=effective_budget,
        trigger_reason="scenario",
        is_baseline=False,           # a scenario NEVER becomes the baseline
        scenario_id=sc.id,
        action_overrides=overrides,
        extra_constraints=extra_constraints,
    )
    sc.result_run_id = run.id
    db.commit()

    cmp = compare_runs(db, baseline, run)
    return {
        "scenario_id": sc.id,
        "name": sc.name,
        "notes": sc.notes,
        "created_at": sc.created_at.isoformat() if sc.created_at else None,
        **cmp,
    }


def reoptimize(
    db: Session, budget: float | None, trigger: str, trigger_detail: str | None
) -> dict[str, Any]:
    """Re-run the baseline optimization and record what changed."""
    previous = latest_run(db, baseline_only=True)
    effective_budget = budget if budget is not None else (previous.budget if previous else 0.0)

    new = run_optimization(
        db, budget=effective_budget, trigger_reason=trigger, is_baseline=True
    )
    cmp = compare_runs(db, previous, new)

    rec = ReoptimizationRun(
        previous_run_id=previous.id if previous else None,
        new_run_id=new.id,
        trigger=trigger,
        trigger_detail=trigger_detail,
        changed=bool(cmp["changed"]),
        change_summary=json.dumps(cmp.get("delta"), default=str),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    return {
        "reoptimization_id": rec.id,
        "trigger": rec.trigger,
        "trigger_detail": rec.trigger_detail,
        "changed": rec.changed,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        **cmp,
    }


def reoptimization_history(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ReoptimizationRun).order_by(ReoptimizationRun.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "reoptimization_id": r.id,
            "previous_run_id": r.previous_run_id,
            "new_run_id": r.new_run_id,
            "trigger": r.trigger,
            "trigger_detail": r.trigger_detail,
            "changed": r.changed,
            "change_summary": json.loads(r.change_summary) if r.change_summary else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
