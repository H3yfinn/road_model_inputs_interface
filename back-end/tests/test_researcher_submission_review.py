from __future__ import annotations

import json
import sys
import types

import pandas as pd
import pytest

from core.researcher_submission_review import (
    build_final_value_overrides,
    canonical_archive_rows,
    compare_submission_to_baseline,
    normalise_module1_rows,
    validate_version,
)


def _canonical_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {"Economy": "20USA", "Scenario": "Target", "Branch Path": "Demand\\Passenger road\\LPVs", "Variable": "Stock", "Year": 2022, "Value": 2.0, "Scale": "Millions", "Units": "Vehicles"},
        {"Economy": "20USA", "Scenario": "Target", "Branch Path": "Demand\\Passenger road\\LPVs\\ICE", "Variable": "Mileage", "Year": 2030, "Value": 12.0, "Scale": "Thousands", "Units": "km"},
        {"Economy": "20USA", "Scenario": "Target", "Branch Path": "Demand\\Passenger road\\LPVs\\BEV", "Variable": "Sales Share", "Year": 2030, "Value": 10.0, "Scale": "%", "Units": "Share"},
        {"Economy": "20USA", "Scenario": "Target", "Branch Path": "Demand\\Passenger road", "Variable": "Passenger Saturation Reached", "Year": 2030, "Value": 0.5, "Scale": "", "Units": "Flag"},
    ])


def test_canonical_rows_normalise_compact_economy_and_collapse_identical_duplicates():
    rows = pd.concat([_canonical_rows(), _canonical_rows().iloc[[0]]], ignore_index=True)
    normalised = normalise_module1_rows(rows, legacy_values_are_internal=False)
    assert len(normalised) == 4
    assert set(normalised["Economy"]) == {"20_USA"}


def test_conflicting_duplicate_is_rejected():
    rows = _canonical_rows()
    conflicting = rows.iloc[[0]].copy()
    conflicting.loc[:, "Value"] = 3.0
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        normalise_module1_rows(pd.concat([rows, conflicting]), legacy_values_are_internal=False)


def test_archive_rows_require_canonical_long_numeric_values_and_one_economy():
    canonical = canonical_archive_rows(_canonical_rows().to_dict("records"), "20USA")
    assert list(canonical.columns) == [
        "Economy", "Scenario", "Branch Path", "Variable", "Year", "Value",
        "Scale", "Units", "Source", "Comment", "Input Status", "Shown In Interface",
        "Source Data Year", "Source Classification", "Base Year Treatment", "Derivation Method",
    ]
    assert set(canonical["Economy"]) == {"20_USA"}

    with pytest.raises(ValueError, match="canonical-long"):
        canonical_archive_rows([{"Economy": "20USA", "2022": 1}], "20USA")
    with pytest.raises(ValueError, match="non-numeric Value"):
        canonical_archive_rows([{**_canonical_rows().iloc[0].to_dict(), "Value": "=1+1"}], "20USA")
    with pytest.raises(ValueError, match="do not match"):
        canonical_archive_rows([{**_canonical_rows().iloc[0].to_dict(), "Economy": "12NZ"}], "20USA")


@pytest.mark.parametrize("value", ["../v1", "v1/escape", "v1\\escape", "", "."])
def test_version_rejects_unsafe_path_components(value):
    with pytest.raises(ValueError, match="Invalid Module 1 defaults version"):
        validate_version(value)


def test_legacy_wide_values_convert_from_internal_units_to_display_units():
    legacy = pd.DataFrame([
        {"Economy": "20USA", "Scenario": "Target", "Branch Path": "Demand\\Passenger road\\LPVs", "Variable": "Stock", "Scale": "Millions", "Units": "Vehicles", "2022": 2_000_000},
        {"Economy": "20USA", "Scenario": "Target", "Branch Path": "Demand\\Passenger road\\LPVs\\ICE", "Variable": "Mileage", "Scale": "Thousands", "Units": "km", "2030": 12_000},
        {"Economy": "20USA", "Scenario": "Target", "Branch Path": "Demand\\Passenger road\\LPVs\\BEV", "Variable": "Sales Share", "Scale": "%", "Units": "Share", "2030": 10},
    ])
    normalised = normalise_module1_rows(legacy, legacy_values_are_internal=True)
    assert normalised.loc[normalised["Variable"].eq("Stock"), "Value"].iloc[0] == 2.0
    assert normalised.loc[normalised["Variable"].eq("Mileage"), "Value"].iloc[0] == 12.0
    assert normalised.loc[normalised["Variable"].eq("Sales Share"), "Value"].iloc[0] == 10.0


def test_review_diff_and_override_values_use_expected_units():
    baseline = normalise_module1_rows(_canonical_rows(), legacy_values_are_internal=False)
    submission = baseline.copy()
    submission.loc[submission["Variable"].eq("Stock"), "Value"] = 3.0
    submission.loc[submission["Variable"].eq("Mileage"), "Value"] = 15.0
    submission.loc[submission["Variable"].eq("Sales Share"), "Value"] = 12.0
    submission = submission.iloc[:-1]  # removed scalar row
    submission = pd.concat([submission, pd.DataFrame([{"Economy": "20_USA", "Scenario": "Target", "Branch Path": "Demand\\Passenger road", "Variable": "New scalar", "Year": 2030, "Value": 7, "Scale": "", "Units": "x"}])], ignore_index=True)
    review = compare_submission_to_baseline(submission, baseline)
    assert set(review["Action"]) == {"changed", "added", "removed"}
    overrides = build_final_value_overrides(review)
    assert overrides.loc[overrides["Variable"].eq("Stock"), "Value"].iloc[0] == 3_000_000
    assert overrides.loc[overrides["Variable"].eq("Mileage"), "Value"].iloc[0] == 15_000
    assert overrides.loc[overrides["Variable"].eq("Sales Share"), "Value"].iloc[0] == 12.0


def test_generated_stock_override_changes_existing_override_engine_result(tmp_path, monkeypatch):
    """The review candidate uses raw values required by final_value_overrides."""
    import core.road_module1_defaults as defaults

    baseline = normalise_module1_rows(_canonical_rows().iloc[[0]], legacy_values_are_internal=False)
    submission = baseline.copy()
    submission.loc[:, "Value"] = 3.0
    candidate = build_final_value_overrides(compare_submission_to_baseline(submission, baseline))
    candidate.to_csv(tmp_path / "module1_final_value_overrides_20USA.csv", index=False)
    monkeypatch.setattr(defaults, "FINAL_VALUE_OVERRIDE_DIR", tmp_path)

    row = {column: "" for column in defaults.MODULE1_INPUT_COLUMNS}
    row.update({
        "Branch Path": "Demand\\Passenger road\\LPVs", "Variable": "Stock", "Scenario": "Target",
        "Region": "United States", "Scale": "Millions", "Units": "Vehicles", "2022": 2_000_000.0,
    })
    changed, report = defaults.apply_final_value_overrides_with_report(
        pd.DataFrame([row]).astype(object), defaults.EconomyInfo("20USA", "United States", 0.0),
    )
    assert changed.loc[0, "2022"] == 3_000_000.0
    assert report.loc[0, "new_value"] == 3_000_000.0


def test_approved_source_promotion_requests_a_new_immutable_version(monkeypatch):
    from scripts import review_researcher_submission as review_script

    called = []
    class FakeStaticBuilder:
        DEFAULT_VERSION = "v_existing"

        @staticmethod
        def main(version):
            called.append(version)

    monkeypatch.setattr(review_script, "_load_static_builder", lambda: FakeStaticBuilder)
    review_script.build_approved_source_version("v2026_08_24_researcher_reviewed")
    assert called == ["v2026_08_24_researcher_reviewed"]
    with pytest.raises(ValueError, match="new immutable"):
        review_script.build_approved_source_version("v_existing")
    with pytest.raises(ValueError, match="Invalid Module 1 defaults version"):
        review_script.build_approved_source_version("../escape")


def test_individual_review_rejects_unsafe_submission_id(tmp_path):
    from scripts.review_researcher_submission import review_submission

    with pytest.raises(ValueError, match="Invalid submission ID"):
        review_submission(
            tmp_path / "submission.csv", tmp_path / "baseline.csv", tmp_path / "output",
            "v1", "../escape",
        )


def test_drive_archive_reports_missing_hf_or_local_credentials(tmp_path, monkeypatch):
    from core.researcher_submission_review import archive_submission_to_drive

    baseline = tmp_path / "20USA.csv"
    baseline.write_text("baseline", encoding="utf-8")
    monkeypatch.setenv("ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID", "folder-id")
    monkeypatch.delenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_DRIVE_ARCHIVE_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    result = archive_submission_to_drive(
        rows=_canonical_rows().to_dict("records"), economy="20USA",
        version="v_test", run_id="run", baseline_path=baseline,
    )
    assert result["success"] is False
    assert "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON" in result["message"]


def test_drive_archive_rejects_missing_baseline_before_drive_access(monkeypatch):
    from core import researcher_submission_review as review

    monkeypatch.setattr(review, "_build_drive_service", lambda: pytest.fail("Drive must not be accessed"))
    result = review.archive_submission_to_drive(
        rows=_canonical_rows().to_dict("records"), economy="20USA", version="v1",
        run_id="run-1", drive_folder_id="root", baseline_path=None,
    )
    assert result["success"] is False
    assert "exact baseline CSV is required" in result["message"]


def test_drive_archive_stages_then_publishes_validated_pair(tmp_path, monkeypatch):
    from core import researcher_submission_review as review

    baseline = tmp_path / "20USA.csv"
    baseline.write_text("baseline", encoding="utf-8")

    class Request:
        def __init__(self, result):
            self.result = result
        def execute(self):
            return self.result

    class Files:
        def __init__(self):
            self.creates = []
            self.updates = []
            self.deleted = []
        def list(self, **kwargs):
            return Request({"files": [{"id": "economy-folder", "name": "20_USA"}]})
        def create(self, **kwargs):
            self.creates.append(kwargs)
            file_id = f"file-{len(self.creates)}"
            return Request({"id": file_id, "webViewLink": f"https://example/{file_id}"})
        def update(self, **kwargs):
            self.updates.append(kwargs)
            return Request({"id": kwargs["fileId"]})
        def delete(self, **kwargs):
            self.deleted.append(kwargs["fileId"])
            return Request({})

    class Service:
        def __init__(self):
            self.file_api = Files()
        def files(self):
            return self.file_api

    service = Service()
    monkeypatch.setattr(review, "_build_drive_service", lambda: service)
    http_module = types.ModuleType("googleapiclient.http")
    class FakeMediaUpload:
        def __init__(self, stream, **kwargs):
            self.payload = stream.read()
        def size(self):
            return len(self.payload)
        def getbytes(self, begin, length):
            return self.payload[begin:begin + length]
    http_module.MediaIoBaseUpload = FakeMediaUpload
    api_module = types.ModuleType("googleapiclient")
    api_module.http = http_module
    monkeypatch.setitem(sys.modules, "googleapiclient", api_module)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", http_module)
    result = review.archive_submission_to_drive(
        rows=_canonical_rows().to_dict("records"), economy="20USA", version="v1",
        run_id="run-1", drive_folder_id="root-folder", baseline_path=baseline,
    )

    assert result["success"] is True, result
    assert all(".pending-" in call["body"]["name"] for call in service.file_api.creates)
    published_names = [call.get("body", {}).get("name") for call in service.file_api.updates]
    assert any(name and name.endswith("_module1_v1.csv") for name in published_names)
    assert any(name and name.endswith("_metadata.json") for name in published_names)
    metadata_update = next(call for call in service.file_api.updates if "media_body" in call)
    media = metadata_update["media_body"]
    payload = json.loads(media.getbytes(0, media.size()).decode("utf-8"))
    assert payload["pair_state"] == "complete"
    assert payload["archive_csv_file_id"] == "file-1"
    assert payload["archive_metadata_file_id"] == "file-2"
    assert payload["row_count"] == len(_canonical_rows())
    assert payload["canonical_long_columns"] == list(canonical_archive_rows(_canonical_rows().to_dict("records"), "20USA").columns)


def test_link_access_is_created_as_viewer_and_rejects_public_writer():
    from core.researcher_submission_review import _ensure_link_viewer_permission

    calls = []
    class Request:
        def execute(self):
            return {"id": "permission"}
    class Permissions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return Request()
    class Service:
        def permissions(self):
            return Permissions()

    _ensure_link_viewer_permission(Service(), "folder", [])
    assert calls[0]["body"] == {"type": "anyone", "role": "reader"}
    with pytest.raises(ValueError, match="non-viewer"):
        _ensure_link_viewer_permission(Service(), "folder", [{"type": "anyone", "role": "writer"}])


def test_drive_archive_status_is_read_only_and_reports_unavailable(monkeypatch):
    from core import researcher_submission_review as review

    class Request:
        def execute(self):
            return {
                "id": "folder", "mimeType": "application/vnd.google-apps.folder",
                "trashed": False, "capabilities": {"canAddChildren": True},
            }

    class Files:
        def __init__(self):
            self.calls = []
        def get(self, **kwargs):
            self.calls.append(kwargs)
            return Request()

    class Service:
        def __init__(self):
            self.file_api = Files()
        def files(self):
            return self.file_api

    service = Service()
    monkeypatch.setattr(review, "_build_drive_service", lambda: service)
    assert review.get_drive_archive_status("folder") == {
        "available": True, "message": "The researcher archive is available.",
    }
    assert len(service.file_api.calls) == 1

    monkeypatch.setattr(review, "_build_drive_service", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    assert review.get_drive_archive_status("folder")["available"] is False
