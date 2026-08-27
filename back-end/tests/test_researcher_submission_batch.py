from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import review_researcher_submission_batch as batch


def _row(value: float) -> dict[str, object]:
    return {
        "Economy": "20_USA",
        "Scenario": "Target",
        "Branch Path": "Demand\\Passenger road\\LPVs",
        "Variable": "Stock",
        "Year": 2030,
        "Value": value,
        "Scale": "Millions",
        "Units": "Vehicles",
        "Source": "Test",
        "Comment": "Batch test",
        "Input Status": "provided",
        "Shown In Interface": True,
    }


def test_batch_classification_marks_replacements_conflicts_and_new_rows():
    changes = pd.DataFrame([
        {**_row(3.0), "Baseline Value": 2.0, "Submitted Value": 3.0, "Delta": 1.0, "Action": "changed", "Baseline Version": "v1"},
        {**_row(4.0), "Baseline Value": 2.0, "Submitted Value": 4.0, "Delta": 2.0, "Action": "changed", "Baseline Version": "v1"},
        {**_row(7.0), "Variable": "New item", "Baseline Value": pd.NA, "Submitted Value": 7.0, "Delta": pd.NA, "Action": "added", "Baseline Version": "v1"},
    ])

    classified = batch._classify_batch_rows(changes)

    assert set(classified.loc[classified["Variable"].eq("Stock"), "Batch Status"]) == {"conflicting_replacement_values"}
    assert set(classified.loc[classified["Variable"].eq("New item"), "Batch Status"]) == {"new_or_removed_row_requires_source_review"}


def test_batch_review_writes_candidate_and_checkpoint_without_drive(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    baseline_path = static_dir / "v1" / "20USA.csv"
    baseline_path.parent.mkdir(parents=True)
    pd.DataFrame([_row(2.0)]).to_csv(baseline_path, index=False)

    download_dir = tmp_path / "downloads" / "20_USA"
    download_dir.mkdir(parents=True)
    submission_path = download_dir / "submission-1_module1_v1.csv"
    metadata_path = download_dir / "submission-1_metadata.json"
    pd.DataFrame([_row(3.0)]).to_csv(submission_path, index=False)
    metadata = {"economy": "20_USA", "module1_defaults_version": "v1"}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setattr(batch, "download_new_archived_submissions", lambda **_: [{
        "submission_id": "submission-1",
        "economy": "20_USA",
        "csv_path": submission_path,
        "metadata_path": metadata_path,
        "metadata": metadata,
    }])
    output_dir = tmp_path / "review"

    artefacts = batch.review_new_archived_submissions(
        output_dir=output_dir, static_bundle_dir=static_dir, drive_folder_id="not-used",
    )

    review = pd.read_csv(artefacts["review_rows"])
    assert review.loc[0, "Batch Status"] == "replacement_candidate"
    candidate = artefacts["override_candidates"][0]
    assert pd.read_csv(candidate).loc[0, "Value"] == 3_000_000.0
    checkpoint = json.loads(Path(artefacts["checkpoint"]).read_text(encoding="utf-8"))
    assert checkpoint["processed_submission_ids"] == ["submission-1"]
