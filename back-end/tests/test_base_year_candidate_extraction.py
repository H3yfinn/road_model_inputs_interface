from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from core.base_year_candidate_extraction import (
    extract_original_candidates,
    generate_checked_in_source_review_package,
    load_static_fallback,
)
from core.base_year_package_generation import CANONICAL_LONG_COLUMNS
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
    _fallback().to_csv(fallback_path, index=False)
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
        "resolved_csv", "audit_csv", "manifest_json", "candidates_json", "candidate_extraction_audit_csv"
    }
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
    extraction = manifest["resolution"]["candidate_extraction"]
    assert extraction["candidate_count"] == 3
    assert extraction["candidates_sha256"] == hashlib.sha256(paths["candidates_json"].read_bytes()).hexdigest()
    assert extraction["audit_sha256"] == hashlib.sha256(paths["candidate_extraction_audit_csv"].read_bytes()).hexdigest()
    resolved = pd.read_csv(paths["resolved_csv"])
    mileage = resolved[resolved["Variable"].eq("Mileage")].iloc[0]
    assert mileage["Value"] == 10.0
    shares = resolved[resolved["Variable"].eq("Stock Share")].set_index("Branch Path")["Value"]
    assert shares[r"Demand\Passenger road\Cars"] == 40.0
    assert shares[r"Demand\Passenger road\2W"] == 60.0


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
