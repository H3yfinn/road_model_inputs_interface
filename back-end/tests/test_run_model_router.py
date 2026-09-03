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
from urllib.parse import parse_qs, urlparse

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


def test_baseline_static_csv_path_uses_compact_static_economy_code(tmp_path, monkeypatch):
    import api.run_model_router as router_mod
    monkeypatch.setattr(router_mod, "_STATIC_BUNDLE_DIR", tmp_path)
    assert router_mod._baseline_static_csv_path("20_USA", "v_test") == tmp_path / "v_test" / "20USA.csv"


@pytest.mark.parametrize("economy", ["../../tmp", "20_USA/escape", "USA", "20_USAA"])
def test_canonical_economy_rejects_unsafe_or_unknown_shapes(economy):
    from api.run_model_router import _to_canonical_economy
    with pytest.raises(ValueError, match="Invalid economy code"):
        _to_canonical_economy(economy)


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


def test_write_module1_csv_records_base_year_manifest(tmp_path, monkeypatch):
    import json
    import api.run_model_router as router_mod
    monkeypatch.setattr(router_mod, "_MODULE1_INPUT_DIR", tmp_path)

    path = router_mod._write_module1_csv(
        [{"Year": 2025, "Value": 1}], "20USA", "v2026_test", 2025, 2027,
    )

    manifest = json.loads((path.parent / "road_module1_package_manifest.json").read_text(encoding="utf-8"))
    assert manifest["base_year"] == 2025
    assert manifest["economy"] == "20_USA"
    assert manifest["esto_vintage"] == 2027


def test_registered_vintage_selection_requires_exact_mapping():
    import api.run_model_router as router_mod

    assert router_mod._validate_esto_vintage_selection(
        "v2026_08_29_esto_2026", 2024, 2026,
    ) == 2026
    with pytest.raises(ValueError, match="do not match"):
        router_mod._validate_esto_vintage_selection(
            "v2026_08_29_esto_2026", 2023, 2026,
        )
    with pytest.raises(ValueError, match="requires"):
        router_mod._validate_esto_vintage_selection(
            "v2026_08_29_esto_2026", 2024, None,
        )


def test_unregistered_package_rejects_claimed_vintage():
    import api.run_model_router as router_mod

    with pytest.raises(ValueError, match="not registered"):
        router_mod._validate_esto_vintage_selection("v_legacy", 2022, 2024)


def test_resolve_esto_csv_for_vintage_validates_filename_schema_and_final_year(tmp_path, monkeypatch):
    import api.run_model_router as router_mod

    path = tmp_path / "00APEC_2025_low_with_subtotals.csv"
    path.write_text(
        "economy,flows,products,is_subtotal,2022,2023\n"
        "20USA,15.02 Road,19 Total,TRUE,1,2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROAD_MODEL_ESTO_VINTAGE_DIR", str(tmp_path))

    assert router_mod._resolve_esto_csv_for_vintage(2025) == path.resolve()


def test_resolve_esto_csv_for_vintage_rejects_wrong_final_year(tmp_path, monkeypatch):
    import api.run_model_router as router_mod

    path = tmp_path / "00APEC_2025_low_with_subtotals.csv"
    path.write_text(
        "economy,flows,products,is_subtotal,2022\n"
        "20USA,15.02 Road,19 Total,TRUE,1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROAD_MODEL_ESTO_VINTAGE_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="must end at base year 2023"):
        router_mod._resolve_esto_csv_for_vintage(2025)


def test_non_default_vintage_requires_configured_read_only_directory(monkeypatch):
    import api.run_model_router as router_mod

    monkeypatch.delenv("ROAD_MODEL_ESTO_VINTAGE_DIR", raising=False)
    with pytest.raises(ValueError, match="ROAD_MODEL_ESTO_VINTAGE_DIR"):
        router_mod._resolve_esto_csv_for_vintage(2025)


def test_static_bundle_base_year_reads_new_metadata(tmp_path, monkeypatch):
    import json
    import api.run_model_router as router_mod
    monkeypatch.setattr(router_mod, "_STATIC_BUNDLE_DIR", tmp_path)
    (tmp_path / "index.json").write_text(json.dumps({"versions": [{"version": "v_test", "economies": [{"economy": "20USA", "base_year": 2025}]}]}), encoding="utf-8")

    assert router_mod._static_bundle_base_year("20_USA", "v_test") == 2025


def test_submitted_package_requires_declared_base_year_rows():
    from api.run_model_router import _validate_submitted_base_year_rows

    with pytest.raises(ValueError, match="no rows"):
        _validate_submitted_base_year_rows([{"Year": 2022, "Value": 1}], 2025)


def test_write_module1_csv_rejects_version_path_traversal(tmp_path, monkeypatch):
    import api.run_model_router as router_mod
    monkeypatch.setattr(router_mod, "_MODULE1_INPUT_DIR", tmp_path)
    with pytest.raises(ValueError, match="Invalid Module 1 defaults version"):
        router_mod._write_module1_csv([{"Year": 2022, "Value": 1}], "20USA", "../escape")


def test_run_endpoint_archiving_failure_does_not_block_model_start(tmp_path, client, monkeypatch):
    """Drive is optional to the run: its failure is returned, never raised."""
    import api.run_model_router as router_mod

    workflow = tmp_path / "road_workflow.py"
    workflow.write_text("", encoding="utf-8")
    monkeypatch.setattr(router_mod, "_ROAD_WORKFLOW", workflow)
    monkeypatch.setattr(router_mod, "_MODULE1_INPUT_DIR", tmp_path / "module1")
    monkeypatch.setattr(router_mod, "_configured_scenario_labels", lambda: set())
    monkeypatch.setattr(router_mod, "archive_submission_to_drive", lambda **_: {"attempted": True, "success": False, "message": "local mock Drive failure"})

    async def fake_process(*args, **kwargs):
        class Process:
            pid = 123
        return Process()

    monkeypatch.setattr(router_mod.asyncio, "create_subprocess_exec", fake_process)
    response = client.post("/api/v1/road-module1/run-model", json={
        "economy": "20USA", "version": "v_test", "rows": [{"Economy": "20USA", "Scenario": "Target", "Branch Path": "x", "Variable": "Stock", "Year": 2022, "Value": 1}],
        "has_researcher_changes": True,
    })
    assert response.status_code == 200
    assert response.json()["archive"]["success"] is False


def test_archive_status_reports_read_only_availability(client, monkeypatch):
    import api.run_model_router as router_mod

    monkeypatch.setattr(
        router_mod,
        "get_drive_archive_status",
        lambda: {"available": False, "message": "The researcher archive cannot currently be reached."},
    )
    response = client.get("/api/v1/road-module1/archive-status")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "message": "The researcher archive cannot currently be reached.",
    }


def test_run_endpoint_rejects_unsafe_economy_and_version(tmp_path, client, monkeypatch):
    import api.run_model_router as router_mod
    workflow = tmp_path / "road_workflow.py"
    workflow.write_text("", encoding="utf-8")
    monkeypatch.setattr(router_mod, "_ROAD_WORKFLOW", workflow)

    for economy, version in [("../../tmp", "v1"), ("20USA", "../v1")]:
        response = client.post("/api/v1/road-module1/run-model", json={
            "economy": economy, "version": version,
            "rows": [{"Economy": "20USA", "Year": 2022, "Value": 1}],
        })
        assert response.status_code == 422


def test_normalise_projection_scenarios_prefers_requested_values():
    import api.run_model_router as router_mod

    rows = [
        {"Scenario": "Current Accounts"},
        {"Scenario": "Target"},
        {"Scenario": "Reference"},
    ]

    assert router_mod._normalise_projection_scenarios(rows, ["Reference", "Target"]) == [
        "Reference",
        "Target",
    ]


def test_normalise_projection_scenarios_falls_back_to_row_labels():
    import api.run_model_router as router_mod

    rows = [
        {"Scenario": "Current Accounts"},
        {"Scenario": "Target"},
        {"Scenario": "Reference"},
        {"Scenario": "Target"},
    ]

    assert router_mod._normalise_projection_scenarios(rows, None) == ["Target", "Reference"]


def test_validate_projection_scenarios_rejects_unknown(monkeypatch):
    import api.run_model_router as router_mod

    monkeypatch.setattr(router_mod, "_configured_scenario_labels", lambda: {"Current Accounts", "Target"})

    with pytest.raises(ValueError, match="NotARealScenario"):
        router_mod._validate_projection_scenarios(["Target", "NotARealScenario"])


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

    with TestClient(app, raise_server_exceptions=True, base_url="https://testserver") as c:
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


def test_google_oauth_setup_stages_one_time_credentials(client, monkeypatch):
    """The setup token gates both OAuth start and one-time credential retrieval."""
    import api.run_model_router as router_mod

    router_mod._oauth_setup_sessions.clear()
    monkeypatch.setenv("GOOGLE_OAUTH_SETUP_TOKEN", "setup-token")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.test/callback")
    monkeypatch.setenv("ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID", "existing-folder-id")
    monkeypatch.setattr(router_mod, "_exchange_google_oauth_code", lambda **_: "refresh-token")
    folder_arguments = {}
    def fake_archive_folder(**kwargs):
        folder_arguments.update(kwargs)
        return "existing-folder-id"
    monkeypatch.setattr(router_mod, "create_my_drive_archive_folder", fake_archive_folder)

    start = client.get(
        "/api/v1/road-module1/google-oauth/start",
        headers={"X-Road-Model-OAuth-Setup-Token": "setup-token"},
        follow_redirects=False,
    )
    assert start.status_code == 302
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["scope"] == ["https://www.googleapis.com/auth/drive.file"]
    state = query["state"][0]

    callback = client.get(f"/api/v1/road-module1/google-oauth/callback?code=one-time-code&state={state}")
    assert callback.status_code == 200
    assert "Google Drive connected" in callback.text
    assert folder_arguments["existing_folder_id"] == "existing-folder-id"

    pending = client.post(
        "/api/v1/road-module1/google-oauth/pending-credentials",
        data={"state": state},
        headers={"X-Road-Model-OAuth-Setup-Token": "setup-token"},
    )
    assert pending.status_code == 200
    assert "refresh-token" in pending.text
    assert "existing-folder-id" in pending.text

    consumed = client.post(
        "/api/v1/road-module1/google-oauth/pending-credentials",
        data={"state": state},
        headers={"X-Road-Model-OAuth-Setup-Token": "setup-token"},
    )
    assert consumed.status_code == 404


def test_road_model_docs_served_from_model_repo(client):
    response = client.get("/road-model-docs/road_transport_model_overview.md")

    assert response.status_code == 200
    assert "plain-English overview" in response.text


def test_privacy_notice_is_publicly_served(client):
    response = client.get("/privacy.html")

    assert response.status_code == 200
    assert "Privacy notice" in response.text
    assert "drive.file" in response.text


# ---------------------------------------------------------------------------
# Static contract drivetrain scope check
# Mirrors valid_drive_types_by_vehicle_type in
# leap_road_model/codebase/config/vehicle_mappings.yaml — update both together.
# ---------------------------------------------------------------------------


_VALID_DRIVES_BY_VEHICLE_TYPE = {
    "LPVs":        {"ICE", "HEV", "EREV", "PHEV", "BEV", "FCEV"},
    "Motorcycles": {"ICE", "BEV", "FCEV"},
    "Buses":       {"ICE", "BEV", "FCEV"},
    "Trucks":      {"ICE", "PHEV", "BEV", "FCEV"},
    "LCVs":        {"ICE", "PHEV", "BEV", "FCEV"},
}

def test_static_contract_drivetrains_match_vehicle_mappings():
    import csv as csv_mod
    contract = (
        Path(__file__).parent.parent
        / "data" / "road_model" / "config" / "road_module1_static_contract.csv"
    )
    violations = []
    with contract.open(encoding="utf-8-sig") as f:
        for row in csv_mod.DictReader(f):
            if row["branch_level"] != "drive_or_size":
                continue
            parts = row["Branch Path"].split("\\")
            if len(parts) < 4:
                continue
            vehicle_type = parts[2]
            drive_type = parts[3].split()[0]  # strip size suffix ("ICE heavy" → "ICE")
            allowed = _VALID_DRIVES_BY_VEHICLE_TYPE.get(vehicle_type)
            if allowed is not None and drive_type not in allowed:
                violations.append(
                    f"{row['Branch Path']!r}: {drive_type!r} not allowed for {vehicle_type!r}"
                )
    assert not violations, (
        "static_contract has drivetrains outside vehicle_mappings.yaml scope:\n"
        + "\n".join(violations)
    )
