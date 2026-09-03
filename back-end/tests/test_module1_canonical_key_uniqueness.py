from __future__ import annotations

import pandas as pd
import pytest

import core.road_module1_defaults as defaults


def _long_row(**overrides: object) -> dict[str, object]:
    row = {column: "" for column in defaults.MODULE1_LONG_COLUMNS}
    row.update(
        {
            "Economy": "20USA",
            "Scenario": "Current Accounts",
            "Branch Path": r"Demand\Passenger road\LPVs\ICE\Gasoline",
            "Variable": "Fuel Economy",
            "Year": 2022,
            "Value": 150.0,
            "Units": "MJ/100 km",
            "Source": "road_module1_source_20USA.csv",
            "Comment": "Selected by the ranked source merge.",
            "Input Status": "default",
            "Shown In Interface": "True",
        }
    )
    row.update(overrides)
    return row


def _wide_row(**overrides: object) -> dict[str, object]:
    row = {column: "" for column in defaults.MODULE1_INPUT_COLUMNS}
    row.update(
        {
            "Branch Path": r"Demand\Passenger road\LPVs",
            "Variable": "Stock",
            "Scenario": "Target",
            "Region": "United States",
            "Scale": "Millions",
            "Units": "Device",
            "2022": 2_000_000.0,
            "source_name": "road_module1_source_20USA.csv",
            "source_type": "processed_source",
            "input_source": "provided",
            "researcher_review_recommended": False,
        }
    )
    row.update(overrides)
    return row


def test_package_collapses_exact_source_overlay_duplicates_and_records_them():
    source_row = _long_row()
    canonical, audit = defaults.canonicalise_module1_long_rows(
        pd.DataFrame([source_row, dict(source_row)])
    )

    assert len(canonical) == 1
    assert canonical.loc[0, "Value"] == 150.0
    assert audit.to_dict("records") == [
        {
            "Action": "collapsed_exact_duplicate",
            "Economy": "20USA",
            "Scenario": "Current Accounts",
            "Branch Path": r"Demand\Passenger road\LPVs\ICE\Gasoline",
            "Variable": "Fuel Economy",
            "Year": 2022,
            "Duplicate Row Count": 2,
            "Retained Source": "road_module1_source_20USA.csv",
            "Retained Comment": "Selected by the ranked source merge.",
        }
    ]


def test_package_rejects_conflicting_source_overlay_duplicates():
    source_row = _long_row()
    overlay_row = _long_row(
        Value=151.0,
        Source="transport_leap_export_combined_ALL_ECONS_Target.xlsx",
        Comment="Transport LEAP export overlay.",
    )

    with pytest.raises(ValueError, match="conflicting duplicate canonical keys"):
        defaults.canonicalise_module1_long_rows(pd.DataFrame([source_row, overlay_row]))


def test_final_override_value_survives_canonical_package_validation(tmp_path, monkeypatch):
    override = pd.DataFrame(
        [
            {
                "Branch Path": r"Demand\Passenger road\LPVs",
                "Variable": "Stock",
                "Scenario": "Target",
                "Year": 2022,
                "Value": 3_000_000.0,
                "Units": "Device",
                "share_decreased_from": "",
                "note": "Reviewed economy-specific correction.",
                "DO_NOT_USE": "",
            }
        ]
    )
    override.to_csv(tmp_path / "module1_final_value_overrides_20USA.csv", index=False)
    monkeypatch.setattr(defaults, "FINAL_VALUE_OVERRIDE_DIR", tmp_path)

    completed, report = defaults.apply_final_value_overrides_with_report(
        pd.DataFrame([_wide_row()]),
        defaults.EconomyInfo("20USA", "United States", 0.0),
    )
    long_rows = defaults._wide_defaults_to_long(completed, "20USA")
    canonical, audit = defaults.canonicalise_module1_long_rows(long_rows)

    assert report.loc[0, "new_value"] == 3_000_000.0
    assert len(canonical) == 1
    assert canonical.loc[0, "Value"] == 3.0
    assert audit.empty


def test_static_publication_rejects_any_duplicate_that_reaches_the_bundle():
    row = _long_row()
    with pytest.raises(ValueError, match="Static Module 1 bundle.*duplicate canonical"):
        defaults.raise_if_module1_long_rows_have_duplicate_keys(
            pd.DataFrame([row, dict(row)]),
            context="Static Module 1 bundle for 20USA",
        )
