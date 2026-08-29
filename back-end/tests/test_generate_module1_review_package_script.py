from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from core.supplemental_provenance_inventory import SupplementalInventory
from scripts import generate_module1_review_package as script
from scripts import review_researcher_submission_batch as batch_review


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
                "candidate_extraction": {
                    "source_rows_total": 3,
                    "matched_rows": 1,
                    "candidate_count": 0,
                    "status_counts": {},
                },
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


def test_manual_candidate_override_csv_has_small_strict_reviewer_schema(tmp_path):
    path = tmp_path / "manual_overrides.csv"
    pd.DataFrame([{
        "Economy": "20USA",
        "Scenario": "Current Accounts",
        "Branch Path": r"Demand\Passenger road\LPVs\ICE",
        "Variable": "Mileage",
        "Requested Base Year": 2024,
        "Source Package": "v_source",
        "Candidate ID": "candidate-2022",
        "Reviewer Reason": "The older survey is more representative.",
        "Reviewer": "model-manager",
    }], columns=script.MANUAL_OVERRIDE_COLUMNS).to_csv(path, index=False)

    assert script._read_manual_candidate_overrides(path) == [{
        "row_key": ["20USA", "Current Accounts", r"Demand\Passenger road\LPVs\ICE", "Mileage"],
        "requested_base_year": 2024,
        "source_package": "v_source",
        "candidate_id": "candidate-2022",
        "reason": "The older survey is more representative.",
        "reviewer": "model-manager",
    }]


def test_manual_candidate_override_csv_rejects_extra_or_missing_columns(tmp_path):
    path = tmp_path / "manual_overrides.csv"
    path.write_text("Economy,Candidate ID\n20USA,candidate\n", encoding="utf-8")

    with pytest.raises(ValueError, match="columns must be exactly"):
        script._read_manual_candidate_overrides(path)


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
        "candidate_extraction_audit_csv", "supplemental_inventory_csv", "run_summary_json",
    }
    assert (output / "supplemental_provenance_inventory.csv").exists()
    assert (output / "review_run_summary.json").exists()
    assert summary["researcher_submission_review"]["included"] is False


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


def test_output_validation_refuses_protected_tree_before_creating_directory():
    output = script.REPO_ROOT / "back-end" / "data" / "cli_review_should_never_exist"
    assert not output.exists()

    with pytest.raises(ValueError, match="protected path"):
        script._unused_output_dir(output)

    assert not output.exists()


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
    assert "no promotion/index update" in output.out
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


def test_generate_staged_review_runs_submission_review_only_when_explicitly_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "generate_checked_in_source_review_package", _fake_package_generator)
    monkeypatch.setattr(script, "build_supplemental_provenance_inventory", _fake_supplemental_inventory)
    calls = []

    def fake_submission_review(
        *, destination, include_researcher_submissions, researcher_submissions_folder_id,
    ):
        calls.append((destination, include_researcher_submissions, researcher_submissions_folder_id))
        return {
            "included": True,
            "reviewed_submission_count": 2,
            "quarantined_submission_count": 1,
            "artifacts": {
                "decisions_csv": str(destination / "researcher_submission_review" / "decisions.csv")
            },
        }

    monkeypatch.setattr(script, "_review_researcher_submissions", fake_submission_review)
    output = tmp_path / "review"
    summary = script.generate_staged_review(
        economy="20USA",
        base_year=2022,
        output_dir=output,
        package_version="review_only_test",
        include_researcher_submissions=True,
        researcher_submissions_folder_id="explicit-folder",
    )

    assert calls == [(output.resolve(), True, "explicit-folder")]
    assert summary["researcher_submission_review"]["included"] is True
    assert summary["researcher_submission_review"]["reviewed_submission_count"] == 2


def test_submission_review_adapter_uses_existing_read_only_batch_workflow(tmp_path, monkeypatch):
    calls = []

    def fake_batch_review(**kwargs):
        calls.append(kwargs)
        return {
            "manifest": tmp_path / "manifest.csv",
            "decisions": tmp_path / "decisions.csv",
            "override_candidates": [tmp_path / "candidate.csv"],
            "message": "reviewed",
            "reviewed_submission_count": 1,
            "quarantined_submission_count": 0,
        }

    monkeypatch.setattr(batch_review, "review_new_archived_submissions", fake_batch_review)
    summary = script._review_researcher_submissions(
        destination=tmp_path,
        include_researcher_submissions=True,
        researcher_submissions_folder_id="explicit-folder",
    )

    assert calls == [{
        "output_dir": tmp_path / "researcher_submission_review",
        "static_bundle_dir": script.STATIC_BUNDLE_ROOT,
        "drive_folder_id": "explicit-folder",
    }]
    assert summary["included"] is True
    assert summary["artifacts"]["manifest"] == str(tmp_path / "manifest.csv")
    assert summary["artifacts"]["override_candidates"] == [str(tmp_path / "candidate.csv")]


def test_generate_all_economies_stages_each_package_and_aggregates_summaries(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "_checked_in_economies", lambda source_package_version: ["01AUS", "20USA"])
    monkeypatch.setattr(script, "build_supplemental_provenance_inventory", _fake_supplemental_inventory)
    package_calls = []

    def fake_economy_package(**kwargs):
        package_calls.append(kwargs)
        return {
            "economy": kwargs["economy"],
            "base_year": kwargs["base_year"],
            "resolution_summary": {"total_rows": 2, "resolved": 1, "fallback": 1, "derived": 0},
            "candidate_extraction_summary": {
                "source_rows_total": 5,
                "matched_rows": 2,
                "candidate_count": 1,
            },
            "artifacts": {"resolved_csv": str(kwargs["output_dir"] / f"{kwargs['economy']}.csv")},
        }

    monkeypatch.setattr(script, "_generate_economy_package", fake_economy_package)
    output = tmp_path / "all"
    summary = script.generate_all_economies_staged_review(
        base_year=2022,
        output_dir=output,
        package_version="review_only_all",
    )

    assert [call["economy"] for call in package_calls] == ["01AUS", "20USA"]
    assert [call["output_dir"] for call in package_calls] == [
        output.resolve() / "packages" / "01AUS",
        output.resolve() / "packages" / "20USA",
    ]
    assert summary["economy_count"] == 2
    assert summary["generated_economy_count"] == 2
    assert summary["failed_economy_count"] == 0
    assert summary["economy_failures"] == []
    assert summary["resolution_summary"] == {
        "derived": 0, "fallback": 2, "resolved": 2, "total_rows": 4,
    }
    assert summary["candidate_extraction_summary"] == {
        "candidate_count": 2, "matched_rows": 4, "source_rows_total": 10,
    }
    assert (output / "review_run_summary.json").exists()


def test_generate_all_economies_records_one_failure_and_continues(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "_checked_in_economies", lambda source_package_version: ["16RUS", "20USA"])
    monkeypatch.setattr(script, "build_supplemental_provenance_inventory", _fake_supplemental_inventory)

    def fake_economy_package(**kwargs):
        if kwargs["economy"] == "16RUS":
            raise ValueError("duplicate canonical key")
        return {
            "economy": "20USA",
            "base_year": kwargs["base_year"],
            "resolution_summary": {"total_rows": 1},
            "candidate_extraction_summary": {
                "source_rows_total": 1, "matched_rows": 0, "candidate_count": 0,
            },
            "artifacts": {},
        }

    monkeypatch.setattr(script, "_generate_economy_package", fake_economy_package)
    monkeypatch.setattr(script, "_write_economy_conflict_report", lambda **kwargs: None)
    summary = script.generate_all_economies_staged_review(
        base_year=2022,
        output_dir=tmp_path / "all",
        package_version="review_only_all",
    )

    assert summary["economy_count"] == 2
    assert summary["generated_economy_count"] == 1
    assert summary["failed_economy_count"] == 1
    assert summary["economy_failures"] == [
        {"economy": "16RUS", "error": "duplicate canonical key"},
    ]


def test_generate_all_economies_links_conflict_report_for_failed_economy(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "_checked_in_economies", lambda source_package_version: ["16RUS"])
    monkeypatch.setattr(script, "build_supplemental_provenance_inventory", _fake_supplemental_inventory)
    monkeypatch.setattr(
        script,
        "_generate_economy_package",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("duplicate canonical key")),
    )
    report_details = {
        "conflict_review_csv": str(tmp_path / "conflict_review.csv"),
        "conflict_review_sha256": "review-sha",
        "conflict_evidence_csv": str(tmp_path / "conflict_evidence.csv"),
        "conflict_evidence_sha256": "evidence-sha",
        "conflict_group_count": 66,
        "conflict_row_count": 132,
    }
    monkeypatch.setattr(
        script,
        "_write_economy_conflict_report",
        lambda **kwargs: report_details,
    )

    summary = script.generate_all_economies_staged_review(
        base_year=2022,
        output_dir=tmp_path / "all",
        package_version="review_only_all",
    )

    assert summary["economy_failures"] == [{
        "economy": "16RUS",
        "error": "duplicate canonical key",
        "quarantine_artifacts": report_details,
    }]


def test_economy_conflict_artifacts_are_compact_and_formula_safe(tmp_path, monkeypatch):
    evidence = pd.DataFrame([{
        "Conflict Group": "conflict-0001",
        "Package Component": "Current Accounts template",
        "Scenario": "Current Accounts",
        "Branch Path": r"Demand\Passenger road\Cars",
        "Variable": "Mileage",
        "Year": 2022,
        "Candidate Value": 10.0,
        "Source": "=unsafe-source",
        "Source Data Year": 2022,
        "Comment": "+unsafe-comment",
        "Conflict Reason": "Duplicate key.",
        "Reviewer Choice (select/correct)": "",
        "Reviewer Note (cite source/reason)": "",
    }])
    monkeypatch.setattr(script, "build_static_package_conflict_report", lambda **kwargs: evidence)

    details = script._write_economy_conflict_report(
        destination=tmp_path,
        economy="20USA",
        base_year=2022,
        source_package_version="test-version",
    )

    assert details["conflict_group_count"] == 1
    assert len(details["conflict_review_sha256"]) == 64
    assert len(details["conflict_evidence_sha256"]) == 64
    review = pd.read_csv(details["conflict_review_csv"], keep_default_na=False)
    assert list(review.columns) == [
        "Conflict Group", "Package Component", "Scenario", "Branch Path", "Variable", "Year",
        "Candidate Options", "Reviewer Choice (value/correction)", "Reviewer Source",
        "Reviewer Note (reason)",
    ]
    assert len(review) == 1
    evidence_text = Path(details["conflict_evidence_csv"]).read_text(encoding="utf-8")
    assert "'=unsafe-source" in evidence_text
    assert "'+unsafe-comment" in evidence_text


def test_main_all_economies_passes_explicit_researcher_submission_option(tmp_path, monkeypatch, capsys):
    captured = {}

    def fake_all(**kwargs):
        captured.update(kwargs)
        return {"mode": "all_economies_staging_only_no_promotion"}

    monkeypatch.setattr(script, "generate_all_economies_staged_review", fake_all)
    exit_code = script.main([
        "--all-economies",
        "--base-year", "2022",
        "--output-dir", str(tmp_path / "all"),
        "--package-version", "review_only_all",
        "--include-researcher-submissions",
        "--researcher-submissions-folder-id", "explicit-folder",
    ])

    assert exit_code == 0
    assert captured["include_researcher_submissions"] is True
    assert captured["researcher_submissions_folder_id"] == "explicit-folder"
    assert '"mode": "all_economies_staging_only_no_promotion"' in capsys.readouterr().out


def test_main_rejects_fallback_csv_for_all_economies(tmp_path, capsys):
    exit_code = script.main([
        "--all-economies",
        "--base-year", "2022",
        "--output-dir", str(tmp_path / "all"),
        "--package-version", "review_only_all",
        "--fallback-csv", str(tmp_path / "fallback.csv"),
    ])

    assert exit_code == 2
    assert "available only with --economy" in capsys.readouterr().err


def test_main_rejects_submission_folder_without_explicit_submission_opt_in(tmp_path, capsys):
    exit_code = script.main([
        "--economy", "20USA",
        "--base-year", "2022",
        "--output-dir", str(tmp_path / "review"),
        "--package-version", "review_only_test",
        "--researcher-submissions-folder-id", "explicit-folder",
    ])

    assert exit_code == 2
    assert "requires --include-researcher-submissions" in capsys.readouterr().err


def test_main_returns_nonzero_after_all_economy_partial_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        script,
        "generate_all_economies_staged_review",
        lambda **kwargs: {
            "mode": "all_economies_staging_only_no_promotion",
            "failed_economy_count": 1,
        },
    )

    exit_code = script.main([
        "--all-economies",
        "--base-year", "2022",
        "--output-dir", str(tmp_path / "all"),
        "--package-version", "review_only_all",
    ])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "attempted every economy" in captured.err
    assert '"failed_economy_count": 1' in captured.out
