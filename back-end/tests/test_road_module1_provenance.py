from __future__ import annotations

import pandas as pd
import pytest

from core.road_module1_provenance import (
    CURRENT_SOURCE_PACKAGE_VERSION,
    LEGACY_GUIDANCE,
    NINTH_OUTLOOK_ARCHIVE_URL,
    NINTH_OUTLOOK_GUIDANCE,
    LineageRule,
    audit_module1_source_quality,
    enrich_module1_provenance,
)


KEY_COLUMNS = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]


def _row(**overrides: object) -> dict[str, object]:
    row = {
        "Economy": "20USA",
        "Scenario": "Current Accounts",
        "Branch Path": "Demand\\Passenger road\\LPVs",
        "Variable": "Stock",
        "Year": 2022,
        "Value": 12.5,
        "Scale": "Millions",
        "Units": "Device",
        "Source": "road_module1_source_20USA.csv",
        "Comment": "Loaded from preprocessed Road Module 1 source.",
        "Input Status": "default",
        "Shown In Interface": "True",
        "Source Data Year": "",
        "Source Classification": "",
        "Base Year Treatment": "",
        "Derivation Method": "",
    }
    row.update(overrides)
    return row


def _enrich(rows: list[dict[str, object]], base_year: int = 2022) -> pd.DataFrame:
    return enrich_module1_provenance(
        pd.DataFrame(rows),
        package_version=CURRENT_SOURCE_PACKAGE_VERSION,
        target_base_year=base_year,
    )


def test_explicit_year_and_classification_beat_known_lineage_fallback():
    result = _enrich([_row(**{"Source Data Year": 2020, "Source Classification": "projection"})])
    assert result.loc[0, "Source Data Year"] == 2020
    assert result.loc[0, "Source Classification"] == "projection"
    assert result.loc[0, "Base Year Treatment"] == "carried_forward"


def test_proven_ninth_outlook_missing_year_uses_2022_but_is_not_native():
    result = _enrich([_row()])
    assert result.loc[0, "Source Data Year"] == 2022
    assert result.loc[0, "Source Classification"] == "legacy_unknown"
    assert result.loc[0, "Base Year Treatment"] == "transformed"
    assert NINTH_OUTLOOK_GUIDANCE in result.loc[0, "Comment"]
    assert NINTH_OUTLOOK_ARCHIVE_URL in result.loc[0, "Comment"]
    assert "original source detail not yet recorded" not in result.loc[0, "Comment"]


def test_unknown_blank_date_stays_blank_and_requests_legacy_detail():
    result = _enrich([_row(Source="unmapped_source.csv")])
    assert pd.isna(result.loc[0, "Source Data Year"])
    assert result.loc[0, "Source Classification"] == "legacy_unknown"
    assert LEGACY_GUIDANCE in result.loc[0, "Comment"]


def test_explicit_russia_2022_remains_2022_and_is_carried_backward_to_2021():
    result = _enrich([
        _row(
            Economy="16RUS",
            Source="explicit_russia_source.csv",
            **{"Source Data Year": 2022, "Source Classification": "projection"},
        )
    ], base_year=2021)
    assert result.loc[0, "Source Data Year"] == 2022
    assert result.loc[0, "Base Year Treatment"] == "carried_backward"
    assert result.loc[0, "Derivation Method"] == "future_year_seed"
    counts = dict(audit_module1_source_quality(result).itertuples(index=False, name=None))
    assert counts["complete"] == 1
    assert counts["operationally_complete"] == 1


@pytest.mark.parametrize(
    "row, classification, method",
    [
        (
            _row(
                Variable="Stock Share",
                Source="Module 1 base-year Stock rows",
                Comment="Base-year stock split derived from 2022 Stock rows.",
            ),
            "structural_assumption",
            "stock_share_from_stock",
        ),
        (
            _row(
                Scenario="Target",
                Variable="Mileage Correction Factor",
                Year=2030,
                Value=1.0,
                Source="generated_default_correction_factor",
                Comment="Default LEAP correction factor.",
            ),
            "model_assumption",
            "generated_default_correction_factor",
        ),
    ],
)
def test_derived_and_generated_rows_retain_derivation_provenance(row, classification, method):
    result = _enrich([row])
    assert result.loc[0, "Source Classification"] == classification
    assert result.loc[0, "Derivation Method"] == method
    assert "derived" in result.loc[0, "Comment"].lower() or "generated" in result.loc[0, "Comment"].lower()


def test_supplemental_explicit_year_and_classification_are_preserved():
    result = _enrich([
        _row(
            Source="apec_phev_utilisation_rates.csv",
            **{"Source Data Year": 2024, "Source Classification": "model_assumption"},
        )
    ])
    assert result.loc[0, "Source Data Year"] == 2024
    assert result.loc[0, "Source Classification"] == "model_assumption"


def test_source_merge_and_canonical_long_conversion_preserve_structured_metadata(tmp_path, monkeypatch):
    import core.road_module1_defaults as defaults

    source_dir = tmp_path / "processed_source"
    source_dir.mkdir()
    pd.DataFrame([
        {
            "Branch Path": "Demand\\Passenger road\\LPVs",
            "Variable": "Stock",
            "Scenario": "Current Accounts",
            "Year": 2022,
            "Value": 2_000_000,
            "Units": "Device",
            "Source": "Published stock register",
            "Comment": "Observed registered vehicles.",
            "Source Data Year": 2021,
            "Source Classification": "native_observation",
            "Base Year Treatment": "carried_forward",
            "Derivation Method": "prior_observation_seed",
        }
    ]).to_csv(source_dir / "road_module1_source_20USA.csv", index=False)
    monkeypatch.setattr(defaults, "PROCESSED_SOURCE_DIR", source_dir)
    monkeypatch.setattr(defaults, "MANUALLY_FILLED_ROWS_DIR", tmp_path / "manual")
    monkeypatch.setattr(defaults, "SOURCE_PRIORITY_PATH", tmp_path / "priorities.csv")

    wide = defaults.load_processed_source_inputs(
        defaults.EconomyInfo("20USA", "United States", 0.0),
        scenarios=["current_accounts"],
    )
    long_rows = defaults._wide_defaults_to_long(wide, "20USA")
    assert long_rows.loc[0, [
        "Source", "Comment", "Source Data Year", "Source Classification",
        "Base Year Treatment", "Derivation Method",
    ]].tolist() == [
        "Published stock register", "Observed registered vehicles.", 2021,
        "native_observation", "carried_forward", "prior_observation_seed",
    ]


def test_source_prepare_preserves_optional_metadata_in_temp_output(tmp_path):
    from scripts.prepare_road_source import expand_for_viewing_to_long, write_processed_source_files

    source = pd.DataFrame([
        {
            "Region": "United States",
            "Branch Path": "Demand\\Passenger road\\LPVs",
            "Variable": "Stock",
            "Scenario": "Current Accounts",
            "Units": "Device",
            "Source": "Published stock register",
            "Source Data Year": 2021,
            "Source Classification": "native_observation",
            2022: 2_000_000,
        }
    ])
    long_rows = expand_for_viewing_to_long(source)
    written = write_processed_source_files(long_rows, tmp_path)
    restored = pd.read_csv(written[0])
    assert restored.loc[0, "Source"] == "Published stock register"
    assert restored.loc[0, "Source Data Year"] == 2021
    assert restored.loc[0, "Source Classification"] == "native_observation"


def test_specialist_projected_sales_rows_enter_expanded_canonical_contract(tmp_path, monkeypatch):
    import build_road_model_static_defaults as builder

    specialist_dir = tmp_path / "sales_shares_9th_replacement"
    specialist_dir.mkdir()
    pd.DataFrame([
        {
            "Branch Path": "Demand\\Passenger road\\LPVs\\BEV",
            "Variable": "Sales Share",
            "Scenario": "Target",
            "Year": 2030,
            "Value": 20.0,
            "Units": "Share",
        }
    ]).to_csv(specialist_dir / "module1_final_value_overrides_20USA.csv", index=False)
    monkeypatch.setattr(builder, "FINAL_VALUE_OVERRIDE_DIR", tmp_path)
    monkeypatch.setattr(builder, "_projection_scenario_labels", lambda: ["Target"])
    monkeypatch.setattr(
        builder,
        "_load_projected_sales_share_for_scenario",
        lambda economy, scenario: pd.DataFrame([
            _row(
                Economy=economy,
                Scenario=scenario,
                **{
                    "Branch Path": "Demand\\Passenger road\\LPVs\\BEV",
                    "Variable": "Sales Share",
                    "Year": 2030,
                    "Value": 10.0,
                },
            )
        ])[builder.MODULE1_LONG_COLUMNS],
    )

    rows = builder._load_projected_sales_share_long_rows("20USA")
    assert list(rows.columns) == builder.MODULE1_LONG_COLUMNS
    assert pd.isna(rows.iloc[0]["Source Data Year"])
    assert rows.iloc[0]["Source"] == "module1_final_value_overrides_20USA.csv"
    assert rows.iloc[0]["Value"] == 20.0


@pytest.mark.parametrize(
    "economy, expected",
    [("02BD", "02_BD"), ("02_BD", "02_BD"), ("20USA", "20_USA")],
)
def test_transport_export_token_normalises_short_and_canonical_economy_codes(economy, expected):
    import core.road_module1_defaults as defaults

    assert defaults._economy_to_leap_import_token(economy) == expected


def test_projected_sales_share_workbook_is_filtered_to_requested_economy(monkeypatch, tmp_path):
    import build_road_model_static_defaults as builder

    workbook = tmp_path / "transport_leap_export_combined_ALL_ECONS_Reference_20260615.xlsx"
    workbook.touch()
    monkeypatch.setattr(builder, "find_transport_leap_export_path", lambda **kwargs: workbook)
    monkeypatch.setattr(
        builder.pd,
        "read_excel",
        lambda *args, **kwargs: pd.DataFrame([
            {
                "Branch Path": r"Demand\Passenger road\LPVs\BEV",
                "Variable": "Sales Share",
                "Scenario": "Reference",
                "Region": "Brunei Darussalam",
                "Scale": "%",
                "Units": "Share",
                "2023": 10.0,
            },
            {
                "Branch Path": r"Demand\Passenger road\LPVs\BEV",
                "Variable": "Sales Share",
                "Scenario": "Reference",
                "Region": "Australia",
                "Scale": "%",
                "Units": "Share",
                "2023": 90.0,
            },
        ]),
    )

    rows = builder._load_projected_sales_share_for_scenario("02BD", "Reference")

    assert len(rows) == 1
    assert rows.iloc[0]["Value"] == 10.0
    assert rows.iloc[0]["Source"] == workbook.name


def test_projected_sales_share_loader_can_request_explicit_2022_seed(monkeypatch, tmp_path):
    import build_road_model_static_defaults as builder

    workbook = tmp_path / "transport_leap_export_combined_20_USA_Reference_20260615.xlsx"
    workbook.touch()
    monkeypatch.setattr(builder, "find_transport_leap_export_path", lambda **kwargs: workbook)
    monkeypatch.setattr(
        builder.pd,
        "read_excel",
        lambda *args, **kwargs: pd.DataFrame([{
            "Branch Path": r"Demand\Passenger road\LPVs\BEV",
            "Variable": "Sales Share",
            "Scenario": "Reference",
            "Region": "United States of America",
            "Scale": "%",
            "Units": "Share",
            "2022": 7.0,
            "2023": 8.0,
        }]),
    )

    rows = builder._load_projected_sales_share_for_scenario(
        "20USA", "Reference", years=(2022,)
    )

    assert len(rows) == 1
    assert rows.iloc[0]["Year"] == 2022
    assert rows.iloc[0]["Value"] == 7.0
    assert rows.iloc[0]["Source"] == workbook.name


@pytest.mark.parametrize(
    ("economy_code", "expected_region"),
    [
        ("05PRC", "People's Republic of China"),
        ("15PHL", "Philippines"),
        ("20USA", "United States of America"),
    ],
)
def test_transport_leap_source_regions_include_explicit_workbook_aliases(
    economy_code, expected_region
):
    import core.road_module1_defaults as defaults

    assert expected_region in defaults._transport_leap_source_regions(
        defaults.get_economy_info(economy_code)
    )


def test_current_accounts_static_normalisation_collapses_only_identical_source_scenarios():
    import build_road_model_static_defaults as builder

    common = {
        "Branch Path": r"Demand\Passenger road\Cars",
        "Variable": "Mileage",
        "Region": "Russia",
        "Scale": "",
        "Units": "Kilometres",
        "source_name": "source.csv",
        "notes": "same evidence",
        "2022": 10.0,
    }
    defaults = pd.DataFrame([
        {**common, "Scenario": "Current Accounts"},
        {**common, "Scenario": "Reference"},
    ])

    rows = builder._normalise_current_accounts_defaults(defaults, economy="16RUS")

    assert len(rows) == 1
    assert rows.iloc[0]["Scenario"] == "Current Accounts"


def test_current_accounts_static_normalisation_prefers_current_accounts_source_scenario():
    import build_road_model_static_defaults as builder

    common = {
        "Branch Path": r"Demand\Passenger road\Cars",
        "Variable": "Mileage",
        "Region": "Russia",
        "Scale": "",
        "Units": "Kilometres",
        "source_name": "source.csv",
        "notes": "same evidence",
    }
    defaults = pd.DataFrame([
        {**common, "Scenario": "Current Accounts", "2022": 10.0},
        {**common, "Scenario": "Reference", "2022": 20.0},
    ])

    rows = builder._normalise_current_accounts_defaults(defaults, economy="16RUS")

    assert len(rows) == 1
    assert rows.iloc[0]["Value"] == 10.0


def test_current_accounts_static_normalisation_rejects_disagreeing_fallback_scenarios():
    import build_road_model_static_defaults as builder

    common = {
        "Branch Path": r"Demand\Passenger road\Cars",
        "Variable": "Mileage",
        "Region": "Russia",
        "Scale": "",
        "Units": "Kilometres",
        "source_name": "source.csv",
        "notes": "same evidence",
    }
    defaults = pd.DataFrame([
        {**common, "Scenario": "Reference", "2022": 10.0},
        {**common, "Scenario": "Target", "2022": 20.0},
    ])

    with pytest.raises(ValueError, match="cannot collapse disagreeing source scenarios"):
        builder._normalise_current_accounts_defaults(defaults, economy="16RUS")


def test_values_keys_order_and_results_are_unchanged_and_idempotent():
    source = pd.DataFrame([
        _row(),
        _row(**{"Branch Path": "Demand\\Freight road\\Trucks"}),
    ]).iloc[[1, 0]].reset_index(drop=True)
    before_keys = source[KEY_COLUMNS].copy(deep=True)
    before_values = source["Value"].copy(deep=True)
    once = enrich_module1_provenance(
        source, package_version=CURRENT_SOURCE_PACKAGE_VERSION, target_base_year=2022
    )
    twice = enrich_module1_provenance(
        once, package_version=CURRENT_SOURCE_PACKAGE_VERSION, target_base_year=2022
    )
    pd.testing.assert_frame_equal(once, twice)
    pd.testing.assert_frame_equal(before_keys, once[KEY_COLUMNS])
    pd.testing.assert_series_equal(before_values, once["Value"])


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("Source Data Year", "2022-ish", "integer year"),
        ("Source Data Year", 1800, "supported range"),
        ("Source Classification", "observed-ish", "Unsupported Source Classification"),
        ("Base Year Treatment", "moved_somehow", "Unsupported Base Year Treatment"),
    ],
)
def test_malformed_metadata_is_rejected(field, value, message):
    with pytest.raises(ValueError, match=message):
        _enrich([_row(**{field: value})])


def test_malformed_or_ambiguous_lineage_rules_are_rejected():
    duplicate_rules = (
        LineageRule("a", "*.csv", frozenset({"v"}), "9th_outlook", 2022),
        LineageRule("b", "road_*.csv", frozenset({"v"}), "9th_outlook", 2022),
    )
    with pytest.raises(ValueError, match="multiple provenance lineage rules"):
        enrich_module1_provenance(
            pd.DataFrame([_row(Source="road_source.csv")]),
            package_version="v",
            target_base_year=2022,
            lineage_rules=duplicate_rules,
        )


def test_canonical_long_round_trip_preserves_all_provenance_fields():
    import core.road_module1_defaults as defaults

    enriched = _enrich([_row(**{"Source Data Year": 2020, "Source Classification": "projection"})])
    wide = defaults._long_defaults_to_ui_wide(enriched, "20USA", "United States")
    restored = defaults._wide_defaults_to_long(wide, "20USA")
    provenance_columns = [
        "Source", "Comment", "Source Data Year", "Source Classification",
        "Base Year Treatment", "Derivation Method",
    ]
    expected = enriched.loc[0, provenance_columns]
    actual = restored.loc[0, provenance_columns]
    assert actual.tolist() == expected.tolist()


def test_legacy_long_rows_without_source_year_survive_wide_conversion():
    import core.road_module1_defaults as defaults

    legacy = pd.DataFrame([{
        key: value for key, value in _row().items()
        if key not in {
            "Source Data Year", "Source Classification", "Base Year Treatment", "Derivation Method",
        }
    }])

    wide = defaults._long_defaults_to_ui_wide(legacy, "20USA", "United States")

    assert len(wide) == 1
    assert wide.iloc[0]["2022"] == 12_500_000.0
    assert wide.iloc[0]["source_data_year"] == ""


def test_source_quality_audit_counts_and_optional_temp_output(tmp_path):
    enriched = _enrich([
        _row(
            Source="National transport survey",
            Comment="Published observed stock table.",
            **{"Source Data Year": 2022, "Source Classification": "native_observation"},
        ),
        _row(**{"Branch Path": "Demand\\Freight road\\Trucks", "Source": "unmapped.csv"}),
        _row(
            **{"Branch Path": "Demand\\Passenger road\\Buses"},
            Source="road_module1_source_20USA.csv",
        ),
        _row(
            Variable="Mileage Correction Factor",
            Scenario="Target",
            Source="generated_default_correction_factor",
            Comment="Default generated factor.",
        ),
    ])
    output = tmp_path / "audit" / "source_quality.csv"
    report = audit_module1_source_quality(enriched, output)
    counts = dict(report.itertuples(index=False, name=None))
    assert counts["total"] == 4
    assert counts["complete"] == 1
    assert counts["operationally_complete"] == 2
    assert counts["archived_reference_available"] == 1
    assert counts["legacy_detail_needed"] == 1
    assert counts["derived_generated"] == 1
    assert counts["missing_date"] == 2
    assert output.exists()
    pd.testing.assert_frame_equal(pd.read_csv(output), report)
