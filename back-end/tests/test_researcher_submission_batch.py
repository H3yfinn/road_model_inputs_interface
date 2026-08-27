from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from core.researcher_submission_review import LONG_COLUMNS, write_reviewer_csv
from scripts import review_researcher_submission_batch as batch


def _row(value: float, **updates) -> dict[str, object]:
    row = {
        "Economy": "20_USA", "Scenario": "Target",
        "Branch Path": "Demand\\Passenger road\\LPVs", "Variable": "Stock",
        "Year": 2030, "Value": value, "Scale": "Millions", "Units": "Vehicles",
        "Source": "Test", "Comment": "Batch test", "Input Status": "provided",
        "Shown In Interface": True,
    }
    row.update(updates)
    return row


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    return pd.DataFrame(rows, columns=LONG_COLUMNS).to_csv(index=False).encode("utf-8")


def _metadata(
    submission_id: str, csv_payload: bytes, baseline_payload: bytes,
    *, version: str = "v1", csv_id: str | None = None, metadata_id: str | None = None,
) -> dict[str, object]:
    csv_id = csv_id or f"csv-{submission_id}"
    metadata_id = metadata_id or f"metadata-{submission_id}"
    return {
        "archive_format_version": "2.0", "submission_id": submission_id,
        "economy": "20_USA", "timestamp": "2026-08-27T10:00:00+09:00",
        "module1_defaults_version": version, "model_run_id": f"run-{submission_id}",
        "archive_csv_filename": f"{submission_id}_module1_{version}.csv",
        "archive_metadata_filename": f"{submission_id}_metadata.json",
        "row_count": len(pd.read_csv(__import__("io").BytesIO(csv_payload))),
        "csv_sha256": hashlib.sha256(csv_payload).hexdigest(),
        "baseline_filename": "20USA.csv",
        "baseline_sha256": hashlib.sha256(baseline_payload).hexdigest(),
        "canonical_long_columns": LONG_COLUMNS, "pair_state": "complete",
        "archive_csv_file_id": csv_id, "archive_metadata_file_id": metadata_id,
    }


def _descriptor(
    tmp_path: Path, submission_id: str, submitted_value: float,
    baseline_path: Path, *, baseline_checksum: str | None = None,
) -> dict[str, object]:
    csv_payload = _csv_bytes([_row(submitted_value)])
    metadata = _metadata(submission_id, csv_payload, baseline_path.read_bytes())
    if baseline_checksum is not None:
        metadata["baseline_sha256"] = baseline_checksum
    download_dir = tmp_path / "downloads" / "20_USA"
    download_dir.mkdir(parents=True, exist_ok=True)
    csv_path = download_dir / str(metadata["archive_csv_filename"])
    metadata_path = download_dir / str(metadata["archive_metadata_filename"])
    csv_path.write_bytes(csv_payload)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return {
        "submission_id": submission_id, "economy": "20_USA",
        "csv_path": csv_path, "metadata_path": metadata_path, "metadata": metadata,
        "canonical_rows": pd.read_csv(csv_path),
        "csv_item": {"id": metadata["archive_csv_file_id"], "name": csv_path.name},
        "metadata_item": {"id": metadata["archive_metadata_file_id"], "name": metadata_path.name},
    }


def test_batch_classification_exposes_all_reasons_and_safe_duplicates():
    changes = pd.DataFrame([
        {**_row(3.0), "Submission ID": "one", "Archive CSV": "one.csv", "Baseline Value": 2.0, "Submitted Value": 3.0, "Delta": 1.0, "Action": "changed", "Baseline Version": "v1"},
        {**_row(4.0), "Submission ID": "two", "Archive CSV": "two.csv", "Baseline Value": 2.5, "Submitted Value": 4.0, "Delta": 1.5, "Action": "changed", "Baseline Version": "v2"},
        {**_row(7.0, Variable="New item"), "Submission ID": "three", "Archive CSV": "three.csv", "Baseline Value": pd.NA, "Submitted Value": 7.0, "Delta": pd.NA, "Action": "added", "Baseline Version": "v1"},
        {**_row(5.0, Variable="Duplicate"), "Submission ID": "four", "Archive CSV": "four.csv", "Baseline Value": 2.0, "Submitted Value": 5.0, "Delta": 3.0, "Action": "changed", "Baseline Version": "v1"},
        {**_row(5.0, Variable="Duplicate"), "Submission ID": "five", "Archive CSV": "five.csv", "Baseline Value": 2.0, "Submitted Value": 5.0, "Delta": 3.0, "Action": "changed", "Baseline Version": "v1"},
        {**_row(6.0, Variable="Versioned"), "Submission ID": "six", "Archive CSV": "six.csv", "Baseline Value": 2.0, "Submitted Value": 6.0, "Delta": 4.0, "Action": "changed", "Baseline Version": "v1"},
        {**_row(6.0, Variable="Versioned"), "Submission ID": "seven", "Archive CSV": "seven.csv", "Baseline Value": 2.5, "Submitted Value": 6.0, "Delta": 3.5, "Action": "changed", "Baseline Version": "v2"},
    ])

    classified = batch._classify_batch_rows(changes)
    stock = classified[classified["Variable"].eq("Stock")]
    assert set(stock["Batch Status"]) == {"multiple_review_reasons"}
    assert set(stock["Review Reasons"]) == {"baseline_version_mismatch;conflicting_proposed_values"}
    assert not stock["Safe Replacement"].any()
    added = classified[classified["Variable"].eq("New item")].iloc[0]
    assert added["Batch Status"] == "new_or_removed_row_requires_source_review"
    duplicate = classified[classified["Variable"].eq("Duplicate")]
    assert set(duplicate["Batch Status"]) == {"same_replacement_proposed_multiple_times"}
    assert duplicate["Safe Replacement"].all()
    versioned = classified[classified["Variable"].eq("Versioned")]
    assert set(versioned["Batch Status"]) == {"baseline_version_mismatch_requires_review"}
    assert set(versioned["Review Reasons"]) == {"baseline_version_mismatch"}


def test_validate_archive_pair_checks_checksum_filenames_ids_and_row_count():
    csv_payload = _csv_bytes([_row(3.0)])
    baseline_payload = _csv_bytes([_row(2.0)])
    metadata = _metadata("submission-1", csv_payload, baseline_payload)
    csv_item = {"id": "csv-submission-1", "name": "submission-1_module1_v1.csv"}
    metadata_item = {"id": "metadata-submission-1", "name": "submission-1_metadata.json"}

    validated, canonical = batch._validate_metadata_pair(
        metadata=metadata, metadata_bytes=json.dumps(metadata).encode(), csv_bytes=csv_payload,
        csv_item=csv_item, metadata_item=metadata_item, economy_folder_name="20_USA",
    )
    assert validated["row_count"] == 1
    assert len(canonical) == 1
    legacy_metadata = {
        key: value for key, value in metadata.items()
        if key not in {"pair_state", "archive_csv_file_id", "archive_metadata_file_id", "canonical_long_columns"}
    }
    legacy_metadata["archive_format_version"] = "1.0"
    legacy_validated, _ = batch._validate_metadata_pair(
        metadata=legacy_metadata, metadata_bytes=json.dumps(legacy_metadata).encode(),
        csv_bytes=csv_payload, csv_item=csv_item, metadata_item=metadata_item,
        economy_folder_name="20_USA",
    )
    assert legacy_validated["archive_format_version"] == "1.0"

    mutations = [
        ("csv_sha256", "0" * 64, "CSV SHA-256"),
        ("archive_csv_filename", "wrong.csv", "archive_csv_filename"),
        ("archive_csv_file_id", "wrong-id", "Drive CSV ID"),
        ("row_count", 2, "row_count"),
        ("baseline_filename", "../20USA.csv", "baseline_filename"),
    ]
    for field, value, message in mutations:
        changed = {**metadata, field: value}
        with pytest.raises(ValueError, match=message):
            batch._validate_metadata_pair(
                metadata=changed, metadata_bytes=json.dumps(changed).encode(), csv_bytes=csv_payload,
                csv_item=csv_item, metadata_item=metadata_item, economy_folder_name="20_USA",
            )
    non_integer_count = {**metadata, "row_count": 1.5}
    with pytest.raises(ValueError, match="row_count must be an integer"):
        batch._validate_metadata_pair(
            metadata=non_integer_count, metadata_bytes=json.dumps(non_integer_count).encode(),
            csv_bytes=csv_payload, csv_item=csv_item, metadata_item=metadata_item,
            economy_folder_name="20_USA",
        )


def test_archive_filename_pattern_accepts_generated_timezone_submission_ids():
    name = "2026-08-27T10-00-00+09-00_ab12cd34_module1_v1.csv"
    match = batch.CSV_SUFFIX_RE.fullmatch(name)
    assert match
    assert match.group("submission_id") == "2026-08-27T10-00-00+09-00_ab12cd34"


def test_batch_review_processes_valid_and_quarantines_bad_baseline(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    baseline_path = static_dir / "v1" / "20USA.csv"
    baseline_path.parent.mkdir(parents=True)
    baseline_path.write_bytes(_csv_bytes([_row(2.0)]))
    valid = _descriptor(tmp_path, "submission-1", 3.0, baseline_path)
    invalid = _descriptor(tmp_path, "submission-2", 4.0, baseline_path, baseline_checksum="0" * 64)
    monkeypatch.setattr(batch, "download_new_archived_submissions", lambda **_: {
        "submissions": [invalid, valid], "failures": [],
    })

    artefacts = batch.review_new_archived_submissions(
        output_dir=tmp_path / "review", static_bundle_dir=static_dir, drive_folder_id="not-used",
    )

    assert artefacts["reviewed_submission_count"] == 1
    assert artefacts["quarantined_submission_count"] == 1
    review = pd.read_csv(artefacts["review_rows"])
    assert review.loc[0, "Batch Status"] == "replacement_candidate"
    assert pd.read_csv(artefacts["override_candidates"][0]).loc[0, "Value"] == 3_000_000.0
    quarantine = pd.read_csv(artefacts["quarantine"])
    assert "baseline SHA-256" in quarantine.loc[0, "Failure Reason"]
    checkpoint = json.loads(Path(artefacts["checkpoint"]).read_text(encoding="utf-8"))
    assert checkpoint["processed_submission_ids"] == ["submission-1"]
    assert checkpoint["quarantined_files"][0]["submission_id"] == "submission-2"


def test_zero_new_submissions_is_clear_and_writes_header_only_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "download_new_archived_submissions", lambda **_: {
        "submissions": [], "failures": [],
    })
    artefacts = batch.review_new_archived_submissions(
        output_dir=tmp_path / "review", static_bundle_dir=tmp_path / "static",
        drive_folder_id="not-used",
    )
    assert artefacts["message"].startswith("No new archived submissions")
    assert list(pd.read_csv(artefacts["review_rows"]).columns) == batch.REVIEW_COLUMNS
    assert list(pd.read_csv(artefacts["manifest"]).columns) == batch.MANIFEST_COLUMNS
    assert list(pd.read_csv(artefacts["quarantine"]).columns) == batch.FAILURE_COLUMNS


def test_formula_like_reviewer_text_is_written_inert(tmp_path):
    path = tmp_path / "review.csv"
    write_reviewer_csv(pd.DataFrame([{"Comment": "=HYPERLINK(\"bad\")", "Value": -2.0}]), path)
    written = pd.read_csv(path, keep_default_na=False)
    assert written.loc[0, "Comment"].startswith("'=")
    assert written.loc[0, "Value"] == -2.0


def test_drive_listing_paginates_with_large_page_size():
    calls = []
    class Request:
        def __init__(self, result):
            self.result = result
        def execute(self):
            return self.result
    class Files:
        def list(self, **kwargs):
            calls.append(kwargs)
            if kwargs["pageToken"] is None:
                return Request({"files": [{"id": "1"}], "nextPageToken": "next"})
            return Request({"files": [{"id": "2"}]})
    class Service:
        def files(self):
            return Files()

    assert [item["id"] for item in batch._list_drive_files(Service(), "q")] == ["1", "2"]
    assert calls[0]["pageSize"] == 1000


def test_fake_drive_download_keeps_valid_pair_when_an_orphan_is_quarantined(tmp_path):
    baseline_payload = _csv_bytes([_row(2.0)])
    csv_payload = _csv_bytes([_row(3.0)])
    metadata = _metadata("good", csv_payload, baseline_payload)
    children = [
        {"id": "csv-good", "name": "good_module1_v1.csv", "modifiedTime": "1"},
        {"id": "metadata-good", "name": "good_metadata.json", "modifiedTime": "1"},
        {"id": "csv-orphan", "name": "orphan_module1_v1.csv", "modifiedTime": "1"},
    ]
    payloads = {
        "csv-good": csv_payload,
        "metadata-good": json.dumps(metadata).encode("utf-8"),
    }

    class Request:
        def __init__(self, result):
            self.result = result
        def execute(self):
            return self.result
    class Files:
        def list(self, **kwargs):
            if "mimeType" in kwargs["q"]:
                return Request({"files": [{"id": "folder", "name": "20_USA"}]})
            return Request({"files": children})
        def get_media(self, fileId):
            return Request(payloads[fileId])
    class Service:
        def files(self):
            return Files()

    result = batch.download_new_archived_submissions(
        output_dir=tmp_path, drive_folder_id="root", service=Service(),
    )
    assert [item["submission_id"] for item in result["submissions"]] == ["good"]
    assert result["failures"][0]["Submission ID"] == "orphan"
    assert "exactly one CSV and one metadata" in result["failures"][0]["Failure Reason"]
    assert result["submissions"][0]["csv_path"].is_file()
    batch._write_checkpoint(tmp_path / "batch_review_checkpoint.json", {
        "processed_submission_ids": ["good"],
        "quarantined_files": [{
            "fingerprint": result["failures"][0]["Quarantine Fingerprint"],
            "submission_id": "orphan", "reason": "test", "recorded_at": "now",
        }],
    })
    repeated = batch.download_new_archived_submissions(
        output_dir=tmp_path, drive_folder_id="root", service=Service(),
    )
    assert repeated == {"submissions": [], "failures": []}


def test_atomic_checkpoint_and_lock(tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    with batch._checkpoint_lock(checkpoint):
        batch._write_checkpoint(checkpoint, {
            "processed_submission_ids": ["submission-1"], "quarantined_files": [],
        })
        with pytest.raises(RuntimeError, match="Another batch review"):
            with batch._checkpoint_lock(checkpoint):
                pass
    assert batch._load_checkpoint(checkpoint)["processed_submission_ids"] == ["submission-1"]
    assert not list(tmp_path.glob("*.tmp"))
