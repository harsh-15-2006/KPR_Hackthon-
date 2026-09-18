"""Stage 1 tests: validation, calculation, hotspot aggregation, action library.

Runs against a throwaway SQLite file so it never touches Supabase.
"""
import os
import tempfile

import pytest

# Point the app at a temp DB BEFORE app modules import settings.
_TMP_DB = os.path.join(tempfile.gettempdir(), "stage1_test.db")

# Start from a clean file every run. SQLAlchemy's create_all() only CREATEs
# missing tables - it never ALTERs an existing one - so a database left over
# from an older model definition silently keeps the old columns and every
# query against a newly added column fails with "no such column".
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)

os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["CLIMATIQ_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        c.delete("/api/emissions")
        yield c


# --- emission request validation -------------------------------------------


def test_rejects_unknown_source(client):
    r = client.post(
        "/api/emissions/calculate?demo=true",
        json={
            "source": "nuclear",
            "activity_type": "x",
            "activity_value": 10,
            "activity_unit": "kWh",
        },
    )
    assert r.status_code == 422


def test_rejects_non_positive_value(client):
    r = client.post(
        "/api/emissions/calculate?demo=true",
        json={
            "source": "fuel",
            "activity_type": "diesel",
            "activity_value": 0,
            "activity_unit": "L",
        },
    )
    assert r.status_code == 422


def test_rejects_unit_that_does_not_belong_to_source(client):
    """kWh is valid for electricity but must be rejected for waste."""
    r = client.post(
        "/api/emissions/calculate?demo=true",
        json={
            "source": "waste",
            "activity_type": "landfill",
            "activity_value": 10,
            "activity_unit": "kWh",
        },
    )
    assert r.status_code == 422
    assert "not valid for source" in r.json()["detail"]


# --- emission calculation service ------------------------------------------


def test_demo_calculation_is_correct_and_labelled(client):
    r = client.post(
        "/api/emissions/calculate?demo=true",
        json={
            "source": "electricity",
            "activity_type": "grid_electricity",
            "activity_value": 1000,
            "activity_unit": "kWh",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["co2e"] == pytest.approx(710.0)  # 1000 * 0.71
    assert body["calculation_source"] == "demo"
    assert "DEMO DATA" in body["emission_factor_reference"]


def test_climatiq_path_fails_loudly_without_a_key(client):
    """A failed real call must NOT be silently replaced by demo numbers."""
    r = client.post(
        "/api/emissions/calculate?demo=false",
        json={
            "source": "fuel",
            "activity_type": "diesel",
            "activity_value": 100,
            "activity_unit": "L",
        },
    )
    assert r.status_code == 502
    assert "not configured" in r.json()["detail"].lower()


# --- hotspot aggregation + source contribution -----------------------------


def test_hotspot_aggregation_and_contribution(client):
    client.delete("/api/emissions")
    # electricity 1000 kWh * 0.71 = 710 kg ; waste 1 t * 458 = 458 kg
    client.post(
        "/api/emissions/calculate?demo=true",
        json={
            "source": "electricity",
            "activity_type": "grid_electricity",
            "activity_value": 1000,
            "activity_unit": "kWh",
        },
    )
    client.post(
        "/api/emissions/calculate?demo=true",
        json={
            "source": "waste",
            "activity_type": "landfill",
            "activity_value": 1,
            "activity_unit": "t",
        },
    )

    s = client.get("/api/emissions/summary").json()
    assert s["total_co2e"] == pytest.approx(1168.0)
    assert s["highest_source"] == "electricity"

    by = {b["source"]: b for b in s["by_source"]}
    assert by["electricity"]["contribution_pct"] == pytest.approx(60.79, abs=0.05)
    assert by["waste"]["contribution_pct"] == pytest.approx(39.21, abs=0.05)
    assert sum(b["contribution_pct"] for b in s["by_source"]) == pytest.approx(100.0, abs=0.1)
    # All five sources are always present, even at zero.
    assert len(s["by_source"]) == 5


def test_summary_is_empty_safe(client):
    client.delete("/api/emissions")
    s = client.get("/api/emissions/summary").json()
    assert s["total_co2e"] == 0
    assert s["highest_source"] is None
    assert len(s["by_source"]) == 5


# --- reduction-action retrieval --------------------------------------------


def test_action_library_is_seeded(client):
    assert client.get("/api/actions/count").json()["count"] == 10


def test_action_filter_by_source(client):
    rows = client.get("/api/actions?source=electricity").json()
    assert len(rows) == 2
    assert all(r["source"] == "electricity" for r in rows)


def test_action_search_and_availability_filter(client):
    assert len(client.get("/api/actions?search=solar").json()) == 1
    limited = client.get("/api/actions?availability=limited").json()
    assert all(r["availability"] == "limited" for r in limited)


def test_every_action_declares_its_data_source(client):
    """No action may present cost/reduction without saying where it came from."""
    for row in client.get("/api/actions").json():
        assert row["data_source"]
        assert "DEMO DATA" in row["data_source"]


# --- CSV upload -------------------------------------------------------------


def test_csv_preview_reports_per_row_errors(client):
    csv = (
        "source,activity_type,activity_value,activity_unit,period\n"
        "electricity,grid_electricity,100,kWh,Q1\n"
        "waste,landfill,50,kWh,Q1\n"
        "fuel,diesel,abc,L,Q1\n"
    )
    r = client.post(
        "/api/emissions/preview-csv",
        files={"file": ("t.csv", csv, "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid_count"] == 1
    assert body["error_count"] == 2
    # Messages must be human-readable, not a pydantic docs URL.
    for e in body["errors"]:
        assert "errors.pydantic.dev" not in e["error"]


def test_csv_missing_columns_is_rejected(client):
    r = client.post(
        "/api/emissions/preview-csv",
        files={"file": ("t.csv", "source,activity_value\nelectricity,100\n", "text/csv")},
    )
    assert r.status_code == 422
    assert "missing required column" in r.json()["detail"].lower()


# --- end-to-end flow --------------------------------------------------------


def test_full_stage1_flow(client):
    """Input -> calculation -> storage -> hotspot -> actions for that hotspot."""
    client.delete("/api/emissions")

    assert (
        client.post(
            "/api/emissions/calculate?demo=true",
            json={
                "source": "production",
                "activity_type": "steel",
                "activity_value": 10,
                "activity_unit": "t",
            },
        ).status_code
        == 201
    )

    assert len(client.get("/api/emissions").json()) == 1

    summary = client.get("/api/emissions/summary").json()
    assert summary["highest_source"] == "production"

    actions = client.get(f"/api/actions?source={summary['highest_source']}").json()
    assert len(actions) > 0
    assert all(a["source"] == "production" for a in actions)
