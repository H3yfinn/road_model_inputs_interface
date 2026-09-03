from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from core.supplemental_provenance_inventory import (
    ROAD_MODEL_DATA_DIR,
    build_supplemental_provenance_inventory,
)


def _write_config(path: Path, sources: list[str]) -> Path:
    path.write_text(json.dumps({"numeric_sources": sources}), encoding="utf-8")
    return path


def _phev_row(*, year: object = 2024, rate: float = 0.5) -> dict:
    return {
        "project_code": "20_USA",
        "economy": "United States",
        "vehicle_type": "LPVs",
        "data_year": year,
        "phev_utilisation_rate": rate,
        "lower_rate": 0.4,
        "upper_rate": 0.6,
        "evidence_grade": "B",
        "estimation_status": "synthetic_estimate",
    }


def test_checked_in_inventory_tracks_active_supplements_without_review_flags():
    source_paths = sorted((ROAD_MODEL_DATA_DIR / "supplemental_source_files").glob("*"))
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}

    inventory = build_supplemental_provenance_inventory()

    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    assert before == after
    assert inventory.summary == {
        "active_source_count": 7,
        "inventory_record_count": 94,
        "review_required_count": 0,
        "status_counts": {"tracked_complete": 90, "tracked_metadata_limited": 4},
    }
    assert set(inventory.rows["Source Classification"]) == {"model_assumption", "structural_assumption"}
    assert not inventory.rows["review_required"].any()
    lifecycle = inventory.rows[inventory.rows["tracking_status"].eq("tracked_metadata_limited")]
    assert lifecycle["Source Data Year"].isna().all()
    assert lifecycle["Comment"].str.contains("ChatGPT-assisted", regex=False).all()
    assert lifecycle["Comment"].str.contains("original external evidence and source year unknown", regex=False).all()


def test_inventory_is_deterministic_and_optionally_writes_only_to_caller_path(tmp_path):
    first_output = tmp_path / "supplemental_inventory_first.csv"
    second_output = tmp_path / "supplemental_inventory_second.csv"
    first = build_supplemental_provenance_inventory(output_path=first_output)
    second = build_supplemental_provenance_inventory(output_path=second_output)

    pd.testing.assert_frame_equal(first.rows, second.rows)
    assert first.summary == second.summary
    assert first_output.read_bytes() == second_output.read_bytes()


def test_invalid_year_is_tracked_as_attention_without_crashing_inventory(tmp_path):
    relative = "supplemental_source_files/apec_phev_utilisation_rates.csv"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    pd.DataFrame([_phev_row(year="not-a-year")]).to_csv(source, index=False)
    config = _write_config(tmp_path / "parameters.json", [relative])

    inventory = build_supplemental_provenance_inventory(
        data_dir=tmp_path,
        parameters_path=config,
    )

    assert inventory.summary["review_required_count"] == 1
    assert inventory.rows.loc[0, "tracking_status"] == "attention_required"
    assert inventory.rows.loc[0, "review_reason"].startswith("malformed_data_year:")


def test_missing_source_identity_requires_attention(tmp_path):
    relative = "supplemental_source_files/apec_phev_utilisation_rates.csv"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    row = _phev_row()
    row["project_code"] = ""
    pd.DataFrame([row]).to_csv(source, index=False)
    config = _write_config(tmp_path / "parameters.json", [relative])

    inventory = build_supplemental_provenance_inventory(
        data_dir=tmp_path,
        parameters_path=config,
    )

    assert inventory.summary["review_required_count"] == 1
    assert inventory.rows.loc[0, "review_reason"] == "missing_source_identity"


def test_missing_and_unconfigured_active_sources_require_attention(tmp_path):
    paths = [
        "supplemental_source_files/apec_reconciliation_factors.csv",
        "supplemental_source_files/new_unmapped_source.csv",
    ]
    config = _write_config(tmp_path / "parameters.json", paths)

    inventory = build_supplemental_provenance_inventory(
        data_dir=tmp_path,
        parameters_path=config,
    )

    assert inventory.summary["review_required_count"] == 2
    assert set(inventory.rows["review_reason"]) == {"missing_active_source", "unconfigured_active_source"}


def test_duplicate_source_identity_requires_attention(tmp_path):
    relative = "supplemental_source_files/apec_phev_utilisation_rates.csv"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    pd.DataFrame([_phev_row(rate=0.4), _phev_row(rate=0.6)]).to_csv(source, index=False)
    config = _write_config(tmp_path / "parameters.json", [relative])

    inventory = build_supplemental_provenance_inventory(
        data_dir=tmp_path,
        parameters_path=config,
    )

    assert inventory.summary["review_required_count"] == 2
    assert set(inventory.rows["review_reason"]) == {"conflicting_or_duplicate_source_identity"}


def test_malformed_workbook_profile_requires_attention(tmp_path, monkeypatch):
    relative = "supplemental_source_files/vehicle_survival_modified_00_APEC.xlsx"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic fixture")
    config = _write_config(tmp_path / "parameters.json", [relative])
    monkeypatch.setattr(
        "core.supplemental_provenance_inventory.pd.read_excel",
        lambda *args, **kwargs: pd.DataFrame([["Area:", "Synthetic"], ["Profile:", "Bad"]]),
    )

    inventory = build_supplemental_provenance_inventory(
        data_dir=tmp_path,
        parameters_path=config,
    )

    assert inventory.summary["review_required_count"] == 1
    assert inventory.rows.loc[0, "review_reason"] == "malformed_profile_sheet"


def test_protected_production_output_paths_are_refused():
    with pytest.raises(ValueError, match="cannot be written under protected path"):
        build_supplemental_provenance_inventory(
            output_path=ROAD_MODEL_DATA_DIR / "supplemental_inventory.csv"
        )
