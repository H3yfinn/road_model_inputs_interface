"""
Tests for back-end/api/run_model_router.py.

Covers:
  - _to_canonical_economy: pure conversion helper
  - _write_module1_csv: file-writing helper
  - POST /api/v1/road-module1/run-model: 503 when road_workflow.py is absent
  - GET  /api/v1/road-module1/run-model-stream: 404 for unknown run_id
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# _to_canonical_economy
# ---------------------------------------------------------------------------

def test_canonical_economy_adds_underscore():
    from api.run_model_router import _to_canonical_economy
    assert _to_canonical_economy("20USA") == "20_USA"
    assert _to_canonical_economy("12NZ") == "12_NZ"
    assert _to_canonical_economy("01AUS") == "01_AUS"


def test_canonical_economy_preserves_existing_underscore():
    from api.run_model_router import _to_canonical_economy
    assert _to_canonical_economy("20_USA") == "20_USA"
    assert _to_canonical_economy("12_NZ") == "12_NZ"


# ---------------------------------------------------------------------------
# _write_module1_csv
# ---------------------------------------------------------------------------

def test_write_module1_csv_creates_file(tmp_path, monkeypatch):
    import api.run_model_router as router_mod
    monkeypatch.setattr(router_mod, "_MODULE1_INPUT_DIR", tmp_path)

    rows = [
        {
            "Branch Path": "Demand\\Passenger road\\LPVs\\BEV medium",
            "Variable": "Sales Share",
            "Scenario": "Reference",
            "Region": "New Zealand",
            "2022": 5.0,
        }
    ]
    path = router_mod._write_module1_csv(rows, "12_NZ", "v2026_test")

    assert path.exists()
    with path.open() as f:
        data = list(csv.DictReader(f))
    assert len(data) == 1
    assert data[0]["Branch Path"] == rows[0]["Branch Path"]
    assert data[0]["Variable"] == "Sales Share"


def test_write_module1_csv_empty_rows_raises(tmp_path, monkeypatch):
    import api.run_model_router as router_mod
    monkeypatch.setattr(router_mod, "_MODULE1_INPUT_DIR", tmp_path)

    with pytest.raises(ValueError, match="No rows provided"):
        router_mod._write_module1_csv([], "12_NZ", "v2026_test")


def test_write_module1_csv_normalises_economy_code(tmp_path, monkeypatch):
    """Economy code without underscore (e.g. '20USA') should be normalised before writing."""
    import api.run_model_router as router_mod
    monkeypatch.setattr(router_mod, "_MODULE1_INPUT_DIR", tmp_path)

    rows = [{"Branch Path": "x", "Variable": "Stock", "2022": 1}]
    path = router_mod._write_module1_csv(rows, "20USA", "v2026_test")

    assert "20_USA" in str(path)
    assert path.exists()


# ---------------------------------------------------------------------------
# FastAPI endpoint tests via TestClient
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """
    TestClient with data_ingestor.load_data no-oped so startup doesn't need
    the APEC CSV on disk.
    """
    import api.routers as routers_mod
    original = routers_mod.data_ingestor.load_data
    routers_mod.data_ingestor.load_data = lambda: None

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    routers_mod.data_ingestor.load_data = original


def test_run_model_503_when_workflow_missing(tmp_path, client, monkeypatch):
    import api.run_model_router as router_mod
    monkeypatch.setattr(router_mod, "_ROAD_WORKFLOW", tmp_path / "does_not_exist.py")

    response = client.post(
        "/api/v1/road-module1/run-model",
        json={"economy": "12_NZ", "version": "v2026_test", "rows": [{"key": "val"}]},
    )
    assert response.status_code == 503
    assert "road_workflow" in response.json()["detail"].lower()


def test_stream_404_unknown_run_id(client):
    response = client.get("/api/v1/road-module1/run-model-stream?run_id=not-a-real-id")
    assert response.status_code == 404
