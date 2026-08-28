from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from core.base_year_candidate_extraction import (
    CONFLICT_REPORT_COLUMNS,
    CONFLICT_REVIEW_COLUMNS,
    build_static_package_conflict_report,
    extract_original_candidates,
    generate_checked_in_source_review_package,
    load_static_package_components,
    load_static_fallback,
    summarise_static_package_conflicts,
)
from core.base_year_package_generation import CANONICAL_LONG_COLUMNS
from core.researcher_submission_review import normalise_module1_rows
from core.road_module1_provenance import CURRENT_SOURCE_PACKAGE_VERSION, NINTH_OUTLOOK_ARCHIVE_URL


def _fallback_row(branch: str, variable: str, value: float, *, source: str = "current.csv") -> dict:
    return {
        "Economy": "20USA",
        "Scenario": "Current Accounts",
        "Branch Path": branch,
        "Variable": variable,
        "Year": 2022,
        "Value": value,
        "Scale": "%" if variable == "Stock Share" else "",
        "Units": "Percent" if variable == "Stock Share" else "Value",
        "Source": source,
        "Comment": "Current authoritative fallback.",
        "Input Status": "default",
        "Shown In Interface": True,
        "Source Data Year": "",
        "Source Classification": "legacy_unknown",
        "Base Year Treatment": "legacy_unrecorded",
        "Derivation Method": "legacy_unrecorded",
    }


def _fallback() -> pd.DataFrame:
    rows = [
        _fallback_row(r"Demand\Passenger road\Cars", "Mileage", 12.0),
        _fallback_row(r"Demand\Passenger road\Cars\bev", "Stock", 30.0),
        _fallback_row(r"Demand\Passenger road\2W\ice_g", "Stock", 70.0),
        _fallback_row(r"Demand\Passenger road\Cars", "Stock Share", 20.0),
        _fallback_row(r"Demand\Passenger road\2W", "Stock Share", 80.0),
    ]
    frame = pd.DataFrame(rows, columns=CANONICAL_LONG_COLUMNS)
    shares = frame["Variable"].eq("Stock Share")
    frame.loc[shares, "Source"] = "Module 1 base-year Stock rows"
    frame.loc[shares, "Comment"] = "Stock Share derived from resolved Stock."
    frame.loc[shares, "Source Classification"] = "structural_assumption"
    frame.loc[shares, "Base Year Treatment"] = "transformed"
    frame.loc[shares, "Derivation Method"] = "stock_share_from_stock"
    return frame


def _source_row(
    branch: str,
    variable: str,
    year: int,
    value: float,
    *,
    source_name: str = "reviewed.csv",
    priority: int = 10,
    classification: str = "native_observation",
    source_year: int | str = "",
) -> dict:
    return {
        "Branch Path": branch,
        "Variable": variable,
        "Scenario": "Current Accounts",
        "Year": year,
        "Value": value,
        "Units": "Value",
        "Source Data Year": source_year,
        "Source Classification": classification,
        "Base Year Treatment": "native" if classification == "native_observation" else "legacy_unrecorded",
        "Derivation Method": "direct_observation" if classification == "native_observation" else "legacy_unrecorded",
        "_source_type": "processed_source",
        "_source_name": source_name,
        "_source_note": "Reviewed original source row.",
        "_priority": priority,
    }


def _extract(rows: list[dict]) -> object:
    return extract_original_candidates(
        fallback_rows=_fallback(),
        ranked_source_rows=pd.DataFrame(rows),
        economy="20USA",
        requested_base_year=2022,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
    )


def test_static_fallback_is_read_only_enriched_and_requires_exact_year(tmp_path):
    raw = _fallback().drop(
        columns=["Source Data Year", "Source Classification", "Base Year Treatment", "Derivation Method"]
    )
    raw.loc[0, "Source"] = "road_module1_source_20USA.csv"
    path = tmp_path / "20USA.csv"
    raw.to_csv(path, index=False)

    loaded = load_static_fallback(
        fallback_csv=path,
        economy="20USA",
        requested_base_year=2022,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
    )

    assert len(loaded) == len(raw)
    assert loaded.loc[loaded["Variable"].eq("Mileage"), "Source Data Year"].iloc[0] == 2022
    assert NINTH_OUTLOOK_ARCHIVE_URL in loaded.loc[loaded["Variable"].eq("Mileage"), "Comment"].iloc[0]
    assert list(pd.read_csv(path).columns) == list(raw.columns)
    with pytest.raises(ValueError, match="no rows.*2021"):
        load_static_fallback(
            fallback_csv=path,
            economy="20USA",
            requested_base_year=2021,
            source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
        )


def test_static_fallback_collapses_only_identical_explicit_derived_stock_share(tmp_path):
    raw = _fallback()
    legacy = raw[raw["Variable"].eq("Stock Share")].iloc[[0]].copy()
    derived = legacy.copy()
    legacy["Source"] = "road_module1_source_20USA.csv"
    legacy["Comment"] = "Loaded from preprocessed Road Module 1 source."
    legacy["Source Classification"] = "legacy_unknown"
    legacy["Base Year Treatment"] = "legacy_unrecorded"
    legacy["Derivation Method"] = "legacy_unrecorded"
    derived["Source"] = "Module 1 base-year Stock rows"
    derived["Comment"] = "Stock Share derived from resolved Stock."
    path = tmp_path / "20USA.csv"
    pd.concat([raw[~raw.index.isin(legacy.index)], legacy, derived], ignore_index=True).to_csv(path, index=False)

    loaded = load_static_fallback(
        fallback_csv=path,
        economy="20USA",
        requested_base_year=2022,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
    )

    key = loaded[loaded["Branch Path"].eq(r"Demand\Passenger road\Cars") & loaded["Variable"].eq("Stock Share")]
    assert len(key) == 1
    assert key.iloc[0]["Derivation Method"] == "stock_share_from_stock"


def test_static_fallback_rejects_conflicting_stock_share_duplicates(tmp_path):
    raw = _fallback()
    duplicate = raw[raw["Variable"].eq("Stock Share")].iloc[[0]].copy()
    duplicate["Value"] = 99.0
    duplicate["Source"] = "Module 1 base-year Stock rows"
    duplicate["Comment"] = "Stock Share derived from resolved Stock."
    path = tmp_path / "20USA.csv"
    pd.concat([raw, duplicate], ignore_index=True).to_csv(path, index=False)

    with pytest.raises(ValueError, match="duplicates disagree"):
        load_static_fallback(
            fallback_csv=path,
            economy="20USA",
            requested_base_year=2022,
            source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
        )


def test_static_components_rebase_complete_current_accounts_and_keep_only_future_projections(tmp_path):
    current_accounts = _fallback()
    projection_2023 = _fallback_row(r"Demand\Passenger road\Cars", "Sales Share", 10.0)
    projection_2023.update(Scenario="Reference", Year=2023)
    projection_2024 = dict(projection_2023, Year=2024, Value=20.0)
    projection_2024_target = dict(projection_2024, Scenario="Target")
    path = tmp_path / "20USA.csv"
    pd.concat(
        [current_accounts, pd.DataFrame([projection_2023, projection_2024, projection_2024_target])],
        ignore_index=True,
    ).to_csv(path, index=False)

    components = load_static_package_components(
        fallback_csv=path,
        economy="20USA",
        requested_base_year=2023,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
    )

    assert components.source_template_year == 2022
    assert set(components.current_accounts_template["Year"]) == {2023}
    assert set(components.current_accounts_template["Scenario"]) == {"Current Accounts"}
    assert set(components.projection_series["Year"]) == {2024}
    shifted = components.current_accounts_template[
        components.current_accounts_template["Derivation Method"].eq("base_year_template_fallback")
    ]
    assert not shifted.empty
    assert shifted["Source Data Year"].isna().all()
    assert set(shifted["Base Year Treatment"]) == {"transformed"}
    assert set(shifted["Derivation Method"]) == {"base_year_template_fallback"}
    assert shifted["Comment"].str.contains("reviewed 2022 Current Accounts template").all()
    stock_shares = components.current_accounts_template[
        components.current_accounts_template["Variable"].eq("Stock Share")
    ]
    assert set(stock_shares["Derivation Method"]) == {"stock_share_from_stock"}


def test_static_components_reject_conflicting_projection_duplicates(tmp_path):
    projection = _fallback_row(r"Demand\Passenger road\Cars", "Sales Share", 10.0)
    projection.update(Scenario="Reference", Year=2024)
    conflicting = dict(projection, Value=20.0)
    path = tmp_path / "20USA.csv"
    pd.concat([_fallback(), pd.DataFrame([projection, conflicting])], ignore_index=True).to_csv(
        path, index=False
    )

    with pytest.raises(ValueError, match="Projection rows contain conflicting duplicate canonical key"):
        load_static_package_components(
            fallback_csv=path,
            economy="20USA",
            requested_base_year=2023,
            source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
        )


def test_static_conflict_report_lists_every_candidate_with_simple_review_fields(tmp_path):
    projection = _fallback_row(r"Demand\Passenger road\Cars", "Sales Share", 10.0)
    projection.update(Scenario="Reference", Year=2024, Source="source-a.csv")
    conflicting = dict(projection, Value=20.0, Source="source-b.csv")
    path = tmp_path / "20USA.csv"
    pd.concat([_fallback(), pd.DataFrame([projection, conflicting])], ignore_index=True).to_csv(
        path, index=False
    )

    report = build_static_package_conflict_report(
        fallback_csv=path,
        economy="20USA",
        requested_base_year=2023,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
    )

    assert list(report.columns) == CONFLICT_REPORT_COLUMNS
    assert len(report) == 2
    assert report["Conflict Group"].nunique() == 1
    assert set(report["Candidate Value"]) == {10.0, 20.0}
    assert set(report["Source"]) == {"source-a.csv", "source-b.csv"}
    assert report["Reviewer Choice (select/correct)"].eq("").all()
    assert report["Reviewer Note (cite source/reason)"].eq("").all()


def test_static_conflict_report_omits_safe_stock_share_duplicate(tmp_path):
    path = tmp_path / "20USA.csv"
    _fallback().to_csv(path, index=False)

    report = build_static_package_conflict_report(
        fallback_csv=path,
        economy="20USA",
        requested_base_year=2022,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
    )

    assert report.empty
    assert list(report.columns) == CONFLICT_REPORT_COLUMNS


def test_static_conflict_summary_has_one_simple_row_per_decision(tmp_path):
    evidence = pd.DataFrame([
        {
            "Conflict Group": "conflict-0001",
            "Package Component": "Reference/Target projection",
            "Scenario": "Reference",
            "Branch Path": r"Demand\Passenger road\Cars",
            "Variable": "Sales Share",
            "Year": 2025,
            "Candidate Value": 10.0,
            "Source": "source-a.csv",
            "Source Data Year": 2022,
            "Comment": "first",
            "Conflict Reason": "Projection rows disagree for the same canonical key.",
            "Reviewer Choice (select/correct)": "",
            "Reviewer Note (cite source/reason)": "",
        },
        {
            "Conflict Group": "conflict-0001",
            "Package Component": "Reference/Target projection",
            "Scenario": "Reference",
            "Branch Path": r"Demand\Passenger road\Cars",
            "Variable": "Sales Share",
            "Year": 2025,
            "Candidate Value": 20.0,
            "Source": "source-b.csv",
            "Source Data Year": pd.NA,
            "Comment": "second",
            "Conflict Reason": "Projection rows disagree for the same canonical key.",
            "Reviewer Choice (select/correct)": "",
            "Reviewer Note (cite source/reason)": "",
        },
    ], columns=CONFLICT_REPORT_COLUMNS)

    review = summarise_static_package_conflicts(evidence)

    assert list(review.columns) == CONFLICT_REVIEW_COLUMNS
    assert len(review) == 1
    assert review.iloc[0]["Candidate Options"] == (
        "10.0 [source-a.csv; data year 2022] | 20.0 [source-b.csv]"
    )
    assert review.iloc[0]["Reviewer Choice (value/correction)"] == ""
    assert review.iloc[0]["Reviewer Source"] == ""
    assert review.iloc[0]["Reviewer Note (reason)"] == ""


def test_static_components_reject_projection_gap_after_earlier_base_year(tmp_path):
    rows = []
    for scenario in ("Reference", "Target"):
        row = _fallback_row(r"Demand\Passenger road\Cars", "Sales Share", 10.0)
        row.update(Scenario=scenario, Year=2023)
        rows.append(row)
    path = tmp_path / "20USA.csv"
    pd.concat([_fallback(), pd.DataFrame(rows)], ignore_index=True).to_csv(path, index=False)

    with pytest.raises(ValueError, match="requires coverage from 2022"):
        load_static_package_components(
            fallback_csv=path,
            economy="20USA",
            requested_base_year=2021,
            source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
        )


def test_static_components_reject_fractional_requested_base_year(tmp_path):
    path = tmp_path / "20USA.csv"
    _fallback().to_csv(path, index=False)

    with pytest.raises(ValueError, match="integer year"):
        load_static_package_components(
            fallback_csv=path,
            economy="20USA",
            requested_base_year=2022.5,
            source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
        )


def test_static_components_reject_non_numeric_projection_value(tmp_path):
    rows = []
    for scenario in ("Reference", "Target"):
        row = _fallback_row(r"Demand\Passenger road\Cars", "Sales Share", "not-a-number")
        row.update(Scenario=scenario, Year=2023)
        rows.append(row)
    path = tmp_path / "20USA.csv"
    pd.concat([_fallback(), pd.DataFrame(rows)], ignore_index=True).to_csv(path, index=False)

    with pytest.raises(ValueError, match="non-finite numeric values"):
        load_static_package_components(
            fallback_csv=path,
            economy="20USA",
            requested_base_year=2022,
            source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
        )


def test_static_components_collapse_identical_explicit_derived_projection_stock_share(tmp_path):
    source_copy = _fallback_row(r"Demand\Passenger road\Cars", "Stock Share", 40.0)
    source_copy.update(Scenario="Reference", Year=2040, Source="road_module1_source_20USA.csv")
    derived_copy = dict(source_copy)
    derived_copy.update(
        Source="Module 1 base-year Stock rows",
        Comment="Stock Share derived from resolved Stock.",
        **{
            "Source Classification": "structural_assumption",
            "Base Year Treatment": "transformed",
            "Derivation Method": "stock_share_from_stock",
        },
    )
    target_copy = dict(derived_copy, Scenario="Target")
    path = tmp_path / "20USA.csv"
    pd.concat([_fallback(), pd.DataFrame([source_copy, derived_copy, target_copy])], ignore_index=True).to_csv(
        path, index=False
    )

    components = load_static_package_components(
        fallback_csv=path,
        economy="20USA",
        requested_base_year=2039,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
    )

    assert len(components.projection_series) == 2
    assert set(components.projection_series["Derivation Method"]) == {"stock_share_from_stock"}


def test_extracts_explicit_original_native_candidate_and_preserves_source_year():
    result = _extract([
        _source_row(r"Demand\Passenger road\Cars", "Mileage", 2020, 10.0, source_year=2020)
    ])

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate["candidate_origin"] == "original"
    assert candidate["source_data_year"] == 2020
    assert candidate["payload"]["Year"] == 2020
    assert candidate["payload"]["Value"] == 10.0
    assert result.summary["status_counts"] == {"candidate": 1}


def test_known_9th_row_is_extracted_with_verified_lineage_but_remains_legacy_unknown():
    row = _source_row(
        r"Demand\Passenger road\Cars",
        "Mileage",
        2022,
        12.0,
        source_name="road_module1_source_20USA.csv",
        classification="",
        source_year="",
    )
    result = _extract([row])

    assert len(result.candidates) == 1
    assert result.candidates[0]["source_data_year"] == 2022
    assert result.candidates[0]["source_classification"] == "legacy_unknown"
    assert result.candidates[0]["source_lineage"] == "verified_9th_outlook"


def test_excludes_missing_year_shifted_rows_and_derived_stock_share():
    rows = [
        _source_row(
            r"Demand\Passenger road\Cars", "Mileage", 2022, 12.0,
            source_name="manual.csv", classification="legacy_unknown", source_year="",
        ),
        _source_row(
            r"Demand\Passenger road\Cars", "Mileage", 2023, 13.0,
            source_name="road_module1_source_20USA.csv", classification="", source_year="",
        ),
        _source_row(
            r"Demand\Passenger road\Cars", "Stock Share", 2022, 20.0, source_year=2022,
        ),
    ]
    result = _extract(rows)

    assert result.candidates == ()
    assert set(result.audit["reason"]) == {
        "missing_source_data_year",
        "source_row_year_differs_from_source_data_year",
        "derived_variable_not_a_candidate",
    }


def test_priority_selection_prefers_eligible_native_and_is_order_independent():
    rows = [
        _source_row(
            r"Demand\Passenger road\Cars", "Mileage", 2020, 9.0,
            source_name="legacy.csv", priority=1, classification="legacy_unknown", source_year=2020,
        ),
        _source_row(
            r"Demand\Passenger road\Cars", "Mileage", 2020, 10.0,
            source_name="native.csv", priority=20, source_year=2020,
        ),
        _source_row(
            r"Demand\Passenger road\Cars", "Mileage", 2019, 8.0,
            source_name="older.csv", priority=30, source_year=2019,
        ),
    ]
    first = _extract(rows)
    second = _extract(list(reversed(rows)))

    assert first.candidates == second.candidates
    native = [item for item in first.candidates if item["source_data_year"] == 2020][0]
    assert native["source_id"].endswith("native.csv")
    assert native["payload"]["Value"] == 10.0
    assert {item["source_data_year"] for item in first.candidates} == {2019, 2020}
    legacy_audit = first.audit[first.audit["source_name"].eq("legacy.csv")].iloc[0]
    assert legacy_audit["reason"] == "ineligible_source_classification"


def test_equal_source_tie_with_different_metadata_is_deterministic():
    first_row = _source_row(
        r"Demand\Passenger road\Cars", "Mileage", 2020, 10.0,
        source_name="same.csv", source_year=2020,
    )
    second_row = dict(first_row)
    first_row["Comment"] = "First source note."
    second_row["Comment"] = "Second source note."

    first = _extract([first_row, second_row])
    second = _extract([second_row, first_row])

    assert first.candidates == second.candidates
    assert first.candidates[0]["candidate_id"] == second.candidates[0]["candidate_id"]
    assert first.candidates[0]["payload"]["Comment"] == second.candidates[0]["payload"]["Comment"]
    pd.testing.assert_frame_equal(first.audit, second.audit)


def test_conflicting_eligible_rows_at_same_priority_fail():
    rows = [
        _source_row(r"Demand\Passenger road\Cars", "Mileage", 2020, 10.0, source_name="a.csv", source_year=2020),
        _source_row(r"Demand\Passenger road\Cars", "Mileage", 2020, 11.0, source_name="b.csv", source_year=2020),
    ]
    with pytest.raises(ValueError, match="conflict at the same source priority"):
        _extract(rows)


def test_review_package_writes_extraction_artifacts_and_checksums(tmp_path, monkeypatch):
    fallback_path = tmp_path / "fallback.csv"
    projection = _fallback_row(r"Demand\Passenger road\Cars", "Sales Share", 25.0)
    projection.update(Scenario="Reference", Year=2023)
    target_projection = dict(projection, Scenario="Target")
    pd.concat([_fallback(), pd.DataFrame([projection, target_projection])], ignore_index=True).to_csv(
        fallback_path, index=False
    )
    rows = pd.DataFrame([
        _source_row(r"Demand\Passenger road\Cars", "Mileage", 2020, 10.0, source_year=2020),
        _source_row(r"Demand\Passenger road\Cars\bev", "Stock", 2022, 40.0, source_year=2022),
        _source_row(r"Demand\Passenger road\2W\ice_g", "Stock", 2022, 60.0, source_year=2022),
    ])
    monkeypatch.setattr(
        "core.base_year_candidate_extraction.load_checked_in_ranked_source_rows",
        lambda economy: rows.copy(),
    )
    output_dir = tmp_path / "review"

    paths = generate_checked_in_source_review_package(
        economy="20USA",
        requested_base_year=2022,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
        package_version="review_only_v1",
        output_dir=output_dir,
        fallback_csv=fallback_path,
        generation_time="2026-08-28T00:00:00+00:00",
    )

    assert set(paths) == {
        "resolved_csv", "audit_csv", "manifest_json", "candidates_json",
        "candidate_extraction_audit_csv", "projection_csv", "complete_package_csv",
    }
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
    extraction = manifest["resolution"]["candidate_extraction"]
    assert extraction["candidate_count"] == 3
    assert extraction["candidates_sha256"] == hashlib.sha256(paths["candidates_json"].read_bytes()).hexdigest()
    assert extraction["audit_sha256"] == hashlib.sha256(paths["candidate_extraction_audit_csv"].read_bytes()).hexdigest()
    components = manifest["package_components"]
    assert components["current_accounts_template_source_year"] == 2022
    assert components["projection_row_count"] == 2
    assert components["projection_first_year"] == 2023
    assert components["complete_package_sha256"] == hashlib.sha256(
        paths["complete_package_csv"].read_bytes()
    ).hexdigest()
    resolved = pd.read_csv(paths["resolved_csv"])
    mileage = resolved[resolved["Variable"].eq("Mileage")].iloc[0]
    assert mileage["Value"] == 10.0
    shares = resolved[resolved["Variable"].eq("Stock Share")].set_index("Branch Path")["Value"]
    assert shares[r"Demand\Passenger road\Cars"] == 40.0
    assert shares[r"Demand\Passenger road\2W"] == 60.0
    complete = pd.read_csv(paths["complete_package_csv"])
    assert set(complete["Scenario"]) == {"Current Accounts", "Reference", "Target"}
    assert len(normalise_module1_rows(complete, legacy_values_are_internal=False)) == len(complete)


def test_extraction_does_not_mutate_inputs():
    fallback = _fallback()
    sources = pd.DataFrame([
        _source_row(r"Demand\Passenger road\Cars", "Mileage", 2020, 10.0, source_year=2020)
    ])
    fallback_before = fallback.copy(deep=True)
    sources_before = sources.copy(deep=True)

    _ = extract_original_candidates(
        fallback_rows=fallback,
        ranked_source_rows=sources,
        economy="20USA",
        requested_base_year=2022,
        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
    )

    pd.testing.assert_frame_equal(fallback, fallback_before)
    pd.testing.assert_frame_equal(sources, sources_before)
