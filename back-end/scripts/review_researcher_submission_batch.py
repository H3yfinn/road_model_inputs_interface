#%%
"""Prepare unreviewed archived Module 1 submissions as a validated batch.

This notebook-friendly tool treats every Drive CSV/metadata pair as untrusted.
It validates and downloads unseen pairs, compares each successful submission to
its recorded immutable baseline, and writes review-only artefacts. It never
changes Drive, source data, overrides, generated defaults, or website files.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.researcher_submission_review import (
    KEY_COLUMNS,
    LONG_COLUMNS,
    _build_drive_service,
    build_final_value_overrides,
    canonical_archive_rows,
    canonical_economy_code,
    compare_submission_to_baseline,
    normalise_module1_csv,
    path_within,
    validate_identifier,
    validate_version,
    write_reviewer_csv,
)


FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
METADATA_SUFFIX = "_metadata.json"
CSV_SUFFIX_RE = re.compile(
    r"^(?P<submission_id>[A-Za-z0-9][A-Za-z0-9._:+-]{0,199})"
    r"_module1_(?P<version>[A-Za-z0-9][A-Za-z0-9._-]{0,127})\.csv$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_COLUMNS = [
    "Submission ID", "Economy", "Baseline Version", "Archive CSV",
    "Archive metadata", "Archive CSV File ID", "Archive Metadata File ID",
    "Archive CSV SHA256", "Baseline Filename", "Baseline SHA256",
    "Row Count", "Changed Rows", "Outcome", "Failure Reason",
]
FAILURE_COLUMNS = [
    "Submission ID", "Economy Folder", "Archive CSV", "Archive metadata",
    "Archive CSV File ID", "Archive Metadata File ID", "Failure Reason",
    "Quarantine Fingerprint",
]
REVIEW_COLUMNS = [
    "Submission ID", "Baseline Version", "Archive CSV", *KEY_COLUMNS,
    "Baseline Value", "Submitted Value", "Delta", "Action", "Scale",
    "Units", "Comment", "Batch Status", "Review Reasons", "Safe Replacement",
    "Proposal Count", "Distinct Proposed Values", "Baseline Versions",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _list_drive_files(service: Any, query: str) -> list[dict[str, Any]]:
    """Return all matching Drive files, including paginated result sets."""
    files: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        response = service.files().list(
            q=query,
            fields="nextPageToken,files(id,name,mimeType,createdTime,modifiedTime,size,md5Checksum)",
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def _download_drive_bytes(service: Any, file_id: str) -> bytes:
    payload = service.files().get_media(fileId=file_id).execute()
    return payload if isinstance(payload, bytes) else bytes(payload)


def _default_checkpoint() -> dict[str, Any]:
    return {
        "checkpoint_format_version": 2,
        "updated_at": "",
        "processed_submission_ids": [],
        "quarantined_files": [],
    }


def _load_checkpoint(checkpoint_path: Path) -> dict[str, Any]:
    if not checkpoint_path.exists():
        return _default_checkpoint()
    try:
        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Checkpoint is unreadable: {checkpoint_path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("processed_submission_ids", []), list):
        raise ValueError(f"Checkpoint has an invalid schema: {checkpoint_path}")
    checkpoint = _default_checkpoint()
    checkpoint.update(data)
    if not isinstance(checkpoint.get("quarantined_files"), list):
        raise ValueError(f"Checkpoint quarantined_files must be a list: {checkpoint_path}")
    return checkpoint


def _write_checkpoint(checkpoint_path: Path, checkpoint: dict[str, Any]) -> None:
    """Atomically replace a checkpoint after all review artefacts are durable."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**checkpoint, "checkpoint_format_version": 2, "updated_at": _utc_now()}
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=checkpoint_path.parent,
            prefix=f".{checkpoint_path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, checkpoint_path)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


@contextmanager
def _checkpoint_lock(checkpoint_path: Path) -> Iterator[None]:
    """Hold a cross-platform non-blocking file lock for one batch run."""
    lock_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError(f"Another batch review is using {checkpoint_path}.") from exc
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _file_fingerprint(*items: dict[str, Any]) -> str:
    identity = [
        {
            "id": str(item.get("id", "")),
            "name": str(item.get("name", "")),
            "modifiedTime": str(item.get("modifiedTime", "")),
            "size": str(item.get("size", "")),
            "md5Checksum": str(item.get("md5Checksum", "")),
        }
        for item in items if item
    ]
    return _sha256(json.dumps(identity, sort_keys=True).encode("utf-8"))


def _failure(
    reason: str, *, submission_id: str = "", economy_folder: str = "",
    csv_item: dict[str, Any] | None = None, metadata_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    csv_item = csv_item or {}
    metadata_item = metadata_item or {}
    return {
        "Submission ID": submission_id,
        "Economy Folder": economy_folder,
        "Archive CSV": csv_item.get("name", ""),
        "Archive metadata": metadata_item.get("name", ""),
        "Archive CSV File ID": csv_item.get("id", ""),
        "Archive Metadata File ID": metadata_item.get("id", ""),
        "Failure Reason": reason,
        "Quarantine Fingerprint": _file_fingerprint(csv_item, metadata_item),
    }


def _validate_metadata_pair(
    *, metadata: Any, metadata_bytes: bytes, csv_bytes: bytes,
    csv_item: dict[str, Any], metadata_item: dict[str, Any], economy_folder_name: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Validate archive metadata, filenames, IDs, checksums, and canonical CSV."""
    if not isinstance(metadata, dict):
        raise ValueError("Metadata JSON must contain one object.")
    required = {
        "archive_format_version", "submission_id", "economy", "timestamp",
        "module1_defaults_version", "model_run_id", "archive_csv_filename",
        "archive_metadata_filename", "row_count", "csv_sha256",
        "baseline_filename", "baseline_sha256",
    }
    missing = sorted(required - set(metadata))
    if missing:
        raise ValueError(f"Metadata is missing required field(s): {', '.join(missing)}.")

    submission_id = validate_identifier(metadata["submission_id"], "submission ID")
    model_run_id = validate_identifier(metadata["model_run_id"], "model run ID")
    version = validate_version(metadata["module1_defaults_version"])
    economy = canonical_economy_code(metadata["economy"])
    folder_economy = canonical_economy_code(economy_folder_name)
    if economy != folder_economy:
        raise ValueError(f"Metadata economy {economy} does not match Drive folder {folder_economy}.")
    try:
        timestamp = datetime.fromisoformat(str(metadata["timestamp"]))
    except ValueError as exc:
        raise ValueError("Metadata timestamp is not ISO-8601.") from exc
    if timestamp.tzinfo is None:
        raise ValueError("Metadata timestamp must include a timezone.")

    expected_csv_name = f"{submission_id}_module1_{version}.csv"
    expected_metadata_name = f"{submission_id}{METADATA_SUFFIX}"
    for actual, expected, label in [
        (csv_item.get("name"), expected_csv_name, "Drive CSV filename"),
        (metadata_item.get("name"), expected_metadata_name, "Drive metadata filename"),
        (metadata.get("archive_csv_filename"), expected_csv_name, "metadata archive_csv_filename"),
        (metadata.get("archive_metadata_filename"), expected_metadata_name, "metadata archive_metadata_filename"),
    ]:
        if str(actual) != expected:
            raise ValueError(f"{label} must be {expected!r}, got {actual!r}.")

    archive_format = str(metadata["archive_format_version"])
    if archive_format not in {"1.0", "2.0"}:
        raise ValueError(f"Unsupported archive_format_version: {archive_format!r}.")
    if archive_format == "2.0":
        if metadata.get("pair_state") != "complete":
            raise ValueError("Archive v2 metadata pair_state must be 'complete'.")
        if metadata.get("canonical_long_columns") != LONG_COLUMNS:
            raise ValueError("Archive v2 canonical_long_columns does not match the required schema.")
        if str(metadata.get("archive_csv_file_id", "")) != str(csv_item.get("id", "")):
            raise ValueError("Metadata archive_csv_file_id does not match the Drive CSV ID.")
        if str(metadata.get("archive_metadata_file_id", "")) != str(metadata_item.get("id", "")):
            raise ValueError("Metadata archive_metadata_file_id does not match the Drive metadata ID.")

    csv_checksum = str(metadata["csv_sha256"]).lower()
    if not SHA256_RE.fullmatch(csv_checksum) or csv_checksum != _sha256(csv_bytes):
        raise ValueError("Archive CSV SHA-256 does not match metadata.")
    baseline_checksum = str(metadata["baseline_sha256"]).lower()
    if baseline_checksum and not SHA256_RE.fullmatch(baseline_checksum):
        raise ValueError("Metadata baseline_sha256 is not a valid SHA-256 value.")
    expected_baseline_name = f"{economy.replace('_', '')}.csv"
    if str(metadata["baseline_filename"]) != expected_baseline_name:
        raise ValueError(
            f"Metadata baseline_filename must be {expected_baseline_name!r} for {economy}."
        )
    if not baseline_checksum:
        raise ValueError("Metadata baseline_sha256 is required for reproducible review.")

    try:
        raw_csv = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as exc:
        raise ValueError(f"Archive CSV cannot be parsed: {exc}") from exc
    if list(raw_csv.columns) != LONG_COLUMNS:
        raise ValueError("Archive CSV columns/order do not match the canonical-long Module 1 schema.")
    raw_row_count = metadata["row_count"]
    if isinstance(raw_row_count, bool) or not isinstance(raw_row_count, int):
        raise ValueError("Metadata row_count must be an integer.")
    try:
        row_count = int(raw_row_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("Metadata row_count must be an integer.") from exc
    if row_count < 1 or row_count != len(raw_csv):
        raise ValueError(f"Metadata row_count {row_count} does not match CSV row count {len(raw_csv)}.")
    canonical = canonical_archive_rows(raw_csv.to_dict("records"), economy)
    if len(canonical) != row_count:
        raise ValueError("Archive CSV contains duplicate canonical Module 1 keys.")
    return {
        **metadata,
        "submission_id": submission_id,
        "model_run_id": model_run_id,
        "module1_defaults_version": version,
        "economy": economy,
        "csv_sha256": csv_checksum,
        "baseline_sha256": baseline_checksum,
        "row_count": row_count,
        "metadata_sha256": _sha256(metadata_bytes),
    }, canonical


def download_new_archived_submissions(
    *, output_dir: Path, drive_folder_id: str, service: Any | None = None,
    checkpoint_filename: str = "batch_review_checkpoint.json",
) -> dict[str, list[dict[str, Any]]]:
    """Validate and download unseen pairs; isolate malformed pairs as failures."""
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = _load_checkpoint(path_within(output_dir, checkpoint_filename))
    processed_ids = set(map(str, checkpoint.get("processed_submission_ids", [])))
    quarantined = {
        str(item.get("fingerprint", ""))
        for item in checkpoint.get("quarantined_files", []) if isinstance(item, dict)
    }
    drive_service = service or _build_drive_service()
    economy_folders = _list_drive_files(
        drive_service,
        f"'{drive_folder_id}' in parents and mimeType = '{FOLDER_MIME_TYPE}' and trashed = false",
    )
    downloaded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for economy_folder in economy_folders:
        folder_name = str(economy_folder.get("name", ""))
        folder_fingerprint = _file_fingerprint(economy_folder)
        if folder_fingerprint in quarantined:
            continue
        try:
            canonical_economy_code(folder_name)
        except ValueError as exc:
            failure = _failure(str(exc), economy_folder=folder_name)
            failure["Quarantine Fingerprint"] = folder_fingerprint
            failures.append(failure)
            continue
        children = _list_drive_files(
            drive_service, f"'{economy_folder['id']}' in parents and trashed = false",
        )
        csv_groups: dict[str, list[dict[str, Any]]] = {}
        metadata_groups: dict[str, list[dict[str, Any]]] = {}
        for item in children:
            name = str(item.get("name", ""))
            if ".pending-" in name:
                continue
            csv_match = CSV_SUFFIX_RE.fullmatch(name)
            if csv_match:
                csv_groups.setdefault(csv_match.group("submission_id"), []).append(item)
            elif name.endswith(METADATA_SUFFIX):
                metadata_groups.setdefault(name[:-len(METADATA_SUFFIX)], []).append(item)
            elif name.lower().endswith(".csv"):
                fingerprint = _file_fingerprint(item)
                if fingerprint not in quarantined:
                    failure = _failure(
                        "CSV filename does not match the archive naming contract.",
                        economy_folder=folder_name, csv_item=item,
                    )
                    failure["Quarantine Fingerprint"] = fingerprint
                    failures.append(failure)

        for submission_id in sorted(set(csv_groups) | set(metadata_groups)):
            if submission_id in processed_ids:
                continue
            csv_items = csv_groups.get(submission_id, [])
            metadata_items = metadata_groups.get(submission_id, [])
            fingerprint = _file_fingerprint(*(csv_items + metadata_items))
            if fingerprint in quarantined:
                continue
            if len(csv_items) != 1 or len(metadata_items) != 1:
                failure = _failure(
                    f"Expected exactly one CSV and one metadata JSON; found {len(csv_items)} CSV and {len(metadata_items)} metadata file(s).",
                    submission_id=submission_id, economy_folder=folder_name,
                    csv_item=csv_items[0] if csv_items else None,
                    metadata_item=metadata_items[0] if metadata_items else None,
                )
                failure["Quarantine Fingerprint"] = fingerprint
                failures.append(failure)
                continue
            csv_item, metadata_item = csv_items[0], metadata_items[0]
            try:
                metadata_bytes = _download_drive_bytes(drive_service, str(metadata_item["id"]))
                csv_bytes = _download_drive_bytes(drive_service, str(csv_item["id"]))
                metadata_raw = json.loads(metadata_bytes.decode("utf-8"))
                metadata, canonical = _validate_metadata_pair(
                    metadata=metadata_raw, metadata_bytes=metadata_bytes, csv_bytes=csv_bytes,
                    csv_item=csv_item, metadata_item=metadata_item,
                    economy_folder_name=folder_name,
                )
                economy = metadata["economy"]
                download_dir = path_within(output_dir, "downloads", economy)
                download_dir.mkdir(parents=True, exist_ok=True)
                csv_path = path_within(download_dir, str(csv_item["name"]))
                metadata_path = path_within(download_dir, str(metadata_item["name"]))
                csv_path.write_bytes(csv_bytes)
                metadata_path.write_bytes(metadata_bytes)
                downloaded.append({
                    "submission_id": submission_id, "economy": economy,
                    "csv_path": csv_path, "metadata_path": metadata_path,
                    "metadata": metadata, "canonical_rows": canonical,
                    "csv_item": csv_item, "metadata_item": metadata_item,
                })
            except Exception as exc:
                failures.append(_failure(
                    str(exc), submission_id=submission_id, economy_folder=folder_name,
                    csv_item=csv_item, metadata_item=metadata_item,
                ))
    return {"submissions": downloaded, "failures": failures}


def _classify_batch_rows(changes: pd.DataFrame) -> pd.DataFrame:
    """Add explicit, cumulative reasons and a conservative candidate decision."""
    if changes.empty:
        return pd.DataFrame(columns=REVIEW_COLUMNS)
    rows: list[pd.DataFrame] = []
    group_columns = ["Economy", *KEY_COLUMNS[1:]]
    for _, group in changes.groupby(group_columns, dropna=False, sort=False):
        group = group.copy()
        actions = set(group["Action"].astype(str))
        proposed_values = pd.to_numeric(group["Submitted Value"], errors="coerce").dropna().round(10).unique()
        baseline_versions = sorted(set(group["Baseline Version"].astype(str)))
        reasons: list[str] = []
        if "added" in actions:
            reasons.append("added_key_requires_source_review")
        if "removed" in actions:
            reasons.append("removed_key_requires_source_review")
        if len(baseline_versions) > 1:
            reasons.append("baseline_version_mismatch")
        if len(proposed_values) > 1:
            reasons.append("conflicting_proposed_values")
        if (
            len(group) > 1 and len(proposed_values) <= 1
            and len(baseline_versions) == 1 and actions == {"changed"}
        ):
            reasons.append("identical_duplicate_proposal")
        blocking = set(reasons) - {"identical_duplicate_proposal"}
        safe_replacement = actions == {"changed"} and not blocking
        if safe_replacement and "identical_duplicate_proposal" in reasons:
            status = "same_replacement_proposed_multiple_times"
        elif safe_replacement:
            status = "replacement_candidate"
        elif len(reasons) > 1:
            status = "multiple_review_reasons"
        elif reasons == ["conflicting_proposed_values"]:
            status = "conflicting_replacement_values"
        elif reasons == ["baseline_version_mismatch"]:
            status = "baseline_version_mismatch_requires_review"
        elif reasons and reasons[0] in {"added_key_requires_source_review", "removed_key_requires_source_review"}:
            status = "new_or_removed_row_requires_source_review"
        else:
            status = "requires_manual_review"
        group["Batch Status"] = status
        group["Review Reasons"] = ";".join(reasons) if reasons else "none"
        group["Safe Replacement"] = safe_replacement
        group["Proposal Count"] = len(group)
        group["Distinct Proposed Values"] = len(proposed_values)
        group["Baseline Versions"] = ";".join(baseline_versions)
        rows.append(group)
    return pd.concat(rows, ignore_index=True).reindex(columns=REVIEW_COLUMNS)


def _manifest_row(item: dict[str, Any], changed_rows: int) -> dict[str, Any]:
    metadata = item["metadata"]
    return {
        "Submission ID": item["submission_id"], "Economy": item["economy"],
        "Baseline Version": metadata["module1_defaults_version"],
        "Archive CSV": item["csv_path"].name,
        "Archive metadata": item["metadata_path"].name,
        "Archive CSV File ID": item.get("csv_item", {}).get("id", metadata.get("archive_csv_file_id", "")),
        "Archive Metadata File ID": item.get("metadata_item", {}).get("id", metadata.get("archive_metadata_file_id", "")),
        "Archive CSV SHA256": metadata["csv_sha256"],
        "Baseline Filename": metadata["baseline_filename"],
        "Baseline SHA256": metadata["baseline_sha256"],
        "Row Count": metadata["row_count"], "Changed Rows": changed_rows,
        "Outcome": "reviewed", "Failure Reason": "",
    }


def review_new_archived_submissions(
    *, output_dir: Path, static_bundle_dir: Path, drive_folder_id: str,
    service: Any | None = None,
) -> dict[str, Any]:
    """Write a resilient validated review batch and checkpoint successful/quarantined files."""
    output_dir = Path(output_dir).resolve()
    static_bundle_dir = Path(static_bundle_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = path_within(output_dir, "batch_review_checkpoint.json")
    with _checkpoint_lock(checkpoint_path):
        checkpoint = _load_checkpoint(checkpoint_path)
        result = download_new_archived_submissions(
            output_dir=output_dir, drive_folder_id=drive_folder_id, service=service,
        )
        downloaded = result["submissions"]
        failures = list(result["failures"])
        change_frames: list[pd.DataFrame] = []
        manifest_rows: list[dict[str, Any]] = []
        successful_ids: set[str] = set()

        for item in downloaded:
            metadata = item["metadata"]
            try:
                version = validate_version(metadata["module1_defaults_version"])
                compact_economy = item["economy"].replace("_", "")
                baseline_path = path_within(static_bundle_dir, version, f"{compact_economy}.csv")
                if not baseline_path.is_file():
                    raise FileNotFoundError(f"Recorded baseline is unavailable: {baseline_path}")
                baseline_bytes = baseline_path.read_bytes()
                if _sha256(baseline_bytes) != metadata["baseline_sha256"]:
                    raise ValueError("Recorded baseline SHA-256 does not match the local immutable baseline.")
                if baseline_path.name != metadata["baseline_filename"]:
                    raise ValueError("Recorded baseline filename does not match the expected economy baseline.")
                submission = item.get("canonical_rows")
                if submission is None:
                    submission = normalise_module1_csv(item["csv_path"], legacy_values_are_internal=False)
                review = compare_submission_to_baseline(
                    submission,
                    normalise_module1_csv(baseline_path, legacy_values_are_internal=False),
                )
                review.insert(0, "Submission ID", item["submission_id"])
                review.insert(1, "Baseline Version", version)
                review.insert(2, "Archive CSV", item["csv_path"].name)
                change_frames.append(review)
                manifest_rows.append(_manifest_row(item, len(review)))
                successful_ids.add(item["submission_id"])
            except Exception as exc:
                failures.append(_failure(
                    str(exc), submission_id=item["submission_id"], economy_folder=item["economy"],
                    csv_item=item.get("csv_item") or {"id": item["metadata"].get("archive_csv_file_id", ""), "name": item["csv_path"].name},
                    metadata_item=item.get("metadata_item") or {"id": item["metadata"].get("archive_metadata_file_id", ""), "name": item["metadata_path"].name},
                ))

        changes = pd.concat(change_frames, ignore_index=True) if change_frames else pd.DataFrame()
        classified = _classify_batch_rows(changes)
        failure_frame = pd.DataFrame(failures, columns=FAILURE_COLUMNS)
        for failure in failures:
            manifest_rows.append({
                "Submission ID": failure["Submission ID"], "Economy": failure["Economy Folder"],
                "Baseline Version": "", "Archive CSV": failure["Archive CSV"],
                "Archive metadata": failure["Archive metadata"],
                "Archive CSV File ID": failure["Archive CSV File ID"],
                "Archive Metadata File ID": failure["Archive Metadata File ID"],
                "Archive CSV SHA256": "", "Baseline Filename": "", "Baseline SHA256": "",
                "Row Count": "", "Changed Rows": "", "Outcome": "quarantined",
                "Failure Reason": failure["Failure Reason"],
            })
        manifest = pd.DataFrame(manifest_rows, columns=MANIFEST_COLUMNS)

        review_path = path_within(output_dir, "batch_review_rows.csv")
        manifest_path = path_within(output_dir, "batch_review_manifest.csv")
        quarantine_path = path_within(output_dir, "batch_review_quarantine.csv")
        write_reviewer_csv(classified, review_path)
        write_reviewer_csv(manifest, manifest_path)
        write_reviewer_csv(failure_frame, quarantine_path)

        candidate_rows = classified.loc[classified["Safe Replacement"].eq(True)].copy()
        candidate_paths: list[Path] = []
        if not candidate_rows.empty:
            for economy, economy_rows in candidate_rows.groupby("Economy", sort=True):
                unique_rows = economy_rows.drop_duplicates(subset=KEY_COLUMNS, keep="first")
                overrides = build_final_value_overrides(
                    unique_rows, note_prefix="Approved batch researcher submission",
                )
                candidate_path = path_within(
                    output_dir,
                    f"module1_final_value_overrides_{economy.replace('_', '')}_candidate.csv",
                )
                write_reviewer_csv(overrides, candidate_path)
                candidate_paths.append(candidate_path)

        processed_ids = set(map(str, checkpoint.get("processed_submission_ids", [])))
        processed_ids.update(successful_ids)
        quarantine_by_fingerprint = {
            str(item.get("fingerprint")): item
            for item in checkpoint.get("quarantined_files", []) if isinstance(item, dict)
        }
        for failure in failures:
            fingerprint = failure["Quarantine Fingerprint"]
            quarantine_by_fingerprint[fingerprint] = {
                "fingerprint": fingerprint,
                "submission_id": failure["Submission ID"],
                "reason": failure["Failure Reason"],
                "recorded_at": _utc_now(),
            }
        _write_checkpoint(checkpoint_path, {
            "processed_submission_ids": sorted(processed_ids),
            "quarantined_files": sorted(
                quarantine_by_fingerprint.values(), key=lambda item: (item.get("submission_id", ""), item["fingerprint"]),
            ),
        })

    if downloaded or failures:
        message = f"Reviewed {len(successful_ids)} submission(s); quarantined {len(failures)} invalid submission(s)."
    else:
        message = "No new archived submissions were found; review outputs contain headers only."
    return {
        "manifest": manifest_path, "review_rows": review_path,
        "quarantine": quarantine_path, "checkpoint": checkpoint_path,
        "override_candidates": candidate_paths, "message": message,
        "reviewed_submission_count": len(successful_ids),
        "quarantined_submission_count": len(failures),
    }


# --- Edit these values in a Jupyter/VS Code interactive cell before running. ---
RUN_BATCH_REVIEW = False
OUTPUT_DIR = Path("outputs/researcher_submission_batch_reviews")
STATIC_BUNDLE_DIR = BACKEND_DIR.parent / "front-end" / "road-module1-static"
DRIVE_FOLDER_ID = ""

if __name__ == "__main__" and RUN_BATCH_REVIEW:
    print(review_new_archived_submissions(
        output_dir=OUTPUT_DIR,
        static_bundle_dir=STATIC_BUNDLE_DIR,
        drive_folder_id=DRIVE_FOLDER_ID,
    ))
#%%
