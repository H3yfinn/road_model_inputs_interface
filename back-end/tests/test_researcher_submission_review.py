from __future__ import annotations

import pandas as pd
import pytest

from core.researcher_submission_review import (
    build_final_value_overrides,
    compare_submission_to_baseline,
    normalise_module1_rows,
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


def test_drive_archive_reports_missing_hf_or_local_credentials(monkeypatch):
    from core.researcher_submission_review import archive_submission_to_drive

    monkeypatch.setenv("ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID", "folder-id")
    monkeypatch.delenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_DRIVE_ARCHIVE_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    result = archive_submission_to_drive(rows=[], economy="20USA", version="v_test", run_id="run")
    assert result["success"] is False
    assert "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON" in result["message"]
