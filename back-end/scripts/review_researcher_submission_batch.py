#%%
"""Download and prepare newly archived Module 1 submissions for batch review.

This notebook-friendly tool is for the model manager/developer at the end of a
modelling iteration. It downloads only Drive submissions absent from its local
checkpoint, compares each to its recorded static baseline, and writes a
consolidated review package. It never changes source data or website defaults.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.researcher_submission_review import (
    KEY_COLUMNS,
    build_final_value_overrides,
    canonical_economy_code,
    compare_submission_to_baseline,
    normalise_module1_csv,
    _build_drive_service,
)


FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
CSV_SUFFIX_RE = re.compile(r"^(?P<submission_id>.+)_module1_.+\.csv$")
METADATA_SUFFIX = "_metadata.json"


def _list_drive_files(service: Any, query: str) -> list[dict[str, Any]]:
    """Return all matching Drive files, including paginated results."""
    files: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        response = service.files().list(
            q=query,
            fields="nextPageToken,files(id,name,mimeType,createdTime,modifiedTime)",
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def _download_drive_bytes(service: Any, file_id: str) -> bytes:
    """Download a non-native Drive file using the configured archive credentials."""
    payload = service.files().get_media(fileId=file_id).execute()
    return payload if isinstance(payload, bytes) else bytes(payload)


def _load_checkpoint(checkpoint_path: Path) -> dict[str, Any]:
    if not checkpoint_path.exists():
        return {"processed_submission_ids": []}
    return json.loads(checkpoint_path.read_text(encoding="utf-8"))


def _write_checkpoint(checkpoint_path: Path, processed_submission_ids: set[str]) -> None:
    checkpoint_path.write_text(
        json.dumps({"processed_submission_ids": sorted(processed_submission_ids)}, indent=2),
        encoding="utf-8",
    )


def download_new_archived_submissions(
    *, output_dir: Path, drive_folder_id: str, service: Any | None = None,
    checkpoint_filename: str = "batch_review_checkpoint.json",
) -> list[dict[str, Any]]:
    """Download unseen archive CSV/metadata pairs and return their local descriptors."""
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / checkpoint_filename
    processed_ids = set(_load_checkpoint(checkpoint_path).get("processed_submission_ids", []))
    drive_service = service or _build_drive_service()
    economy_folders = _list_drive_files(
        drive_service,
        f"'{drive_folder_id}' in parents and mimeType = '{FOLDER_MIME_TYPE}' and trashed = false",
    )
    downloaded: list[dict[str, Any]] = []
    for economy_folder in economy_folders:
        children = _list_drive_files(
            drive_service, f"'{economy_folder['id']}' in parents and trashed = false",
        )
        metadata_by_submission_id = {
            item["name"][: -len(METADATA_SUFFIX)]: item
            for item in children
            if item.get("name", "").endswith(METADATA_SUFFIX)
        }
        for csv_item in children:
            match = CSV_SUFFIX_RE.match(str(csv_item.get("name", "")))
            if not match:
                continue
            submission_id = match.group("submission_id")
            if submission_id in processed_ids:
                continue
            metadata_item = metadata_by_submission_id.get(submission_id)
            if not metadata_item:
                raise ValueError(f"Archive CSV {csv_item['name']} has no matching metadata JSON.")
            metadata = json.loads(_download_drive_bytes(drive_service, metadata_item["id"]).decode("utf-8"))
            economy = canonical_economy_code(metadata.get("economy") or economy_folder["name"])
            download_dir = output_dir / "downloads" / economy
            download_dir.mkdir(parents=True, exist_ok=True)
            csv_path = download_dir / csv_item["name"]
            metadata_path = download_dir / metadata_item["name"]
            csv_path.write_bytes(_download_drive_bytes(drive_service, csv_item["id"]))
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            downloaded.append({
                "submission_id": submission_id,
                "economy": economy,
                "csv_path": csv_path,
                "metadata_path": metadata_path,
                "metadata": metadata,
            })
    return downloaded


def _classify_batch_rows(changes: pd.DataFrame) -> pd.DataFrame:
    """Label each proposed row for review without choosing between conflicts."""
    if changes.empty:
        return changes.assign(**{"Batch Status": pd.Series(dtype=str)})
    rows: list[pd.DataFrame] = []
    group_columns = ["Economy", *KEY_COLUMNS[1:]]
    for _, group in changes.groupby(group_columns, dropna=False, sort=False):
        group = group.copy()
        actions = set(group["Action"])
        proposed_values = pd.to_numeric(group["Submitted Value"], errors="coerce").dropna().round(10).unique()
        baseline_versions = set(group["Baseline Version"].astype(str))
        if "added" in actions or "removed" in actions:
            status = "new_or_removed_row_requires_source_review"
        elif len(baseline_versions) > 1:
            status = "baseline_version_mismatch_requires_review"
        elif len(proposed_values) > 1:
            status = "conflicting_replacement_values"
        elif len(group) > 1:
            status = "same_replacement_proposed_multiple_times"
        else:
            status = "replacement_candidate"
        group["Batch Status"] = status
        rows.append(group)
    return pd.concat(rows, ignore_index=True)


def review_new_archived_submissions(
    *, output_dir: Path, static_bundle_dir: Path, drive_folder_id: str,
    service: Any | None = None,
) -> dict[str, Any]:
    """Download unseen submissions and write consolidated review/candidate/checkpoint files."""
    downloaded = download_new_archived_submissions(
        output_dir=output_dir, drive_folder_id=drive_folder_id, service=service,
    )
    change_frames: list[pd.DataFrame] = []
    manifest_rows: list[dict[str, Any]] = []
    for item in downloaded:
        metadata = item["metadata"]
        version = str(metadata.get("module1_defaults_version") or "").strip()
        compact_economy = item["economy"].replace("_", "")
        baseline_path = static_bundle_dir / version / f"{compact_economy}.csv"
        if not version or not baseline_path.exists():
            raise FileNotFoundError(
                f"Baseline for {item['submission_id']} is unavailable: {baseline_path}"
            )
        review = compare_submission_to_baseline(
            normalise_module1_csv(item["csv_path"]),
            normalise_module1_csv(baseline_path, legacy_values_are_internal=False),
        )
        review.insert(0, "Submission ID", item["submission_id"])
        review.insert(1, "Baseline Version", version)
        review.insert(2, "Archive CSV", item["csv_path"].name)
        change_frames.append(review)
        manifest_rows.append({
            "Submission ID": item["submission_id"], "Economy": item["economy"],
            "Baseline Version": version, "Archive CSV": item["csv_path"].name,
            "Archive metadata": item["metadata_path"].name, "Changed rows": len(review),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    changes = pd.concat(change_frames, ignore_index=True) if change_frames else pd.DataFrame()
    classified = _classify_batch_rows(changes)
    manifest = pd.DataFrame(manifest_rows)
    review_path = output_dir / "batch_review_rows.csv"
    manifest_path = output_dir / "batch_review_manifest.csv"
    classified.to_csv(review_path, index=False)
    manifest.to_csv(manifest_path, index=False)

    candidate_rows = classified.loc[classified.get("Batch Status", pd.Series(dtype=str)).isin([
        "replacement_candidate", "same_replacement_proposed_multiple_times",
    ])].copy()
    candidate_paths: list[Path] = []
    if not candidate_rows.empty:
        for economy, economy_rows in candidate_rows.groupby("Economy", sort=True):
            unique_rows = economy_rows.drop_duplicates(subset=KEY_COLUMNS, keep="first")
            overrides = build_final_value_overrides(
                unique_rows, note_prefix="Approved batch researcher submission",
            )
            candidate_path = output_dir / f"module1_final_value_overrides_{economy.replace('_', '')}_candidate.csv"
            overrides.to_csv(candidate_path, index=False)
            candidate_paths.append(candidate_path)

    processed_ids = set(_load_checkpoint(output_dir / "batch_review_checkpoint.json").get("processed_submission_ids", []))
    processed_ids.update(item["submission_id"] for item in downloaded)
    _write_checkpoint(output_dir / "batch_review_checkpoint.json", processed_ids)
    return {
        "manifest": manifest_path,
        "review_rows": review_path,
        "checkpoint": output_dir / "batch_review_checkpoint.json",
        "override_candidates": candidate_paths,
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
