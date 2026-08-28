from __future__ import annotations

import json

import pandas as pd
import pytest

from core.supplemental_provenance_inventory import SupplementalInventory
from scripts import generate_module1_review_package as script


def _fake_package_generator(**kwargs):
    destination = kwargs["output_dir"]
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "resolved_csv": destination / "20USA_2022.csv",
        "audit_csv": destination / "20USA_2022_resolution_audit.csv",
        "manifest_json": destination / "20USA_2022_resolution_manifest.json",
        "candidates_json": destination / "20USA_2022_original_candidates.json",
        "candidate_extraction_audit_csv": destination / "20USA_2022_candidate_extraction_audit.csv",
    }
    paths["resolved_csv"].write_text("Economy,Year\n20USA,2022\n", encoding="utf-8")
    paths["audit_csv"].write_text("status\nfallback\n", encoding="utf-8")
    paths["candidates_json"].write_text("[]\n", encoding="utf-8")
    paths["candidate_extraction_audit_csv"].write_text("status\n", encoding="utf-8")
    paths["manifest_json"].write_text(
        json.dumps({
            "resolution": {
                "summary_counts": {"total_rows": 1, "resolved": 0, "fallback": 1, "derived": 0},
                "candidate_extraction": {"candidate_count": 0, "status_counts": {}},
            }
        }),
        encoding="utf-8",
    )
    return paths


def _fake_supplemental_inventory(*, output_path):
    output_path.write_text("tracking_status\ntracked_complete\n", encoding="utf-8")
    return SupplementalInventory(
        pd.DataFrame([{"tracking_status": "tracked_complete"}]),
        {
            "active_source_count": 1,
            "inventory_record_count": 1,
            "review_required_count": 0,
            "status_counts": {"tracked_complete": 1},
        },
    )


def test_generate_staged_review_writes_only_to_new_output_and_returns_summaries(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "generate_checked_in_source_review_package", _fake_package_generator)
    monkeypatch.setattr(script, "build_supplemental_provenance_inventory", _fake_supplemental_inventory)
    output = tmp_path / "review"

    summary = script.generate_staged_review(
        economy="20USA",
        base_year=2022,
        output_dir=output,
        package_version="review_only_test",
    )

    assert summary["mode"] == "staging_only_no_promotion"
    assert summary["resolution_summary"]["fallback"] == 1
    assert summary["candidate_extraction_summary"]["candidate_count"] == 0
    assert summary["supplemental_summary"]["review_required_count"] == 0
    assert set(summary["artifacts"]) == {
        "resolved_csv", "audit_csv", "manifest_json", "candidates_json",
        "candidate_extraction_audit_csv", "supplemental_inventory_csv",
    }
    assert (output / "supplemental_provenance_inventory.csv").exists()


def test_generate_staged_review_refuses_nonempty_output_before_generation(tmp_path, monkeypatch):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep.txt").write_text("do not overwrite", encoding="utf-8")
    called = False

    def unexpected_generator(**kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(script, "generate_checked_in_source_review_package", unexpected_generator)
    with pytest.raises(ValueError, match="must be new or empty"):
        script.generate_staged_review(
            economy="20USA",
            base_year=2022,
            output_dir=output,
            package_version="review_only_test",
        )
    assert called is False
    assert (output / "keep.txt").read_text(encoding="utf-8") == "do not overwrite"


def test_main_prints_machine_readable_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(script, "generate_checked_in_source_review_package", _fake_package_generator)
    monkeypatch.setattr(script, "build_supplemental_provenance_inventory", _fake_supplemental_inventory)

    exit_code = script.main([
        "--economy", "20USA",
        "--base-year", "2022",
        "--output-dir", str(tmp_path / "review"),
        "--package-version", "review_only_test",
    ])

    output = capsys.readouterr()
    assert exit_code == 0
    assert "no promotion or index update" in output.out
    assert '"mode": "staging_only_no_promotion"' in output.out
    assert output.err == ""


def test_main_returns_nonzero_and_reports_safe_failure(tmp_path, capsys):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep.txt").write_text("keep", encoding="utf-8")

    exit_code = script.main([
        "--economy", "20USA",
        "--base-year", "2022",
        "--output-dir", str(output),
        "--package-version", "review_only_test",
    ])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "must be new or empty" in captured.err
