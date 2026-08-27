"""Archive and review researcher Module 1 submissions without changing source data.

The browser submits canonical long website values.  Review tools normalize old
wide packages to that same display representation, then make explicit override
or source-promotion review artefacts.  This module deliberately never edits a
source folder or a generated defaults version.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


LONG_COLUMNS = [
    "Economy", "Scenario", "Branch Path", "Variable", "Year", "Value",
    "Scale", "Units", "Source", "Comment", "Input Status", "Shown In Interface",
]
KEY_COLUMNS = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]
OVERRIDE_COLUMNS = [
    "Branch Path", "Variable", "Scenario", "Year", "Value", "Units",
    "share_decreased_from", "note", "DO_NOT_USE",
]
SCALE_MULTIPLIERS = {
    "": 1.0, "%": 1.0, "thousand": 1_000.0, "thousands": 1_000.0,
    "million": 1_000_000.0, "millions": 1_000_000.0,
    "billion": 1_000_000_000.0, "billions": 1_000_000_000.0,
}


def canonical_economy_code(value: object) -> str:
    """Normalise compact economy codes, e.g. 20USA -> 20_USA."""
    text = str(value or "").strip()
    if "_" in text:
        return text
    match = re.fullmatch(r"(\d+)([A-Za-z].*)", text)
    return f"{match.group(1)}_{match.group(2)}" if match else text


def _scale_multiplier(value: object) -> float:
    return SCALE_MULTIPLIERS.get(str(value or "").strip().lower(), 1.0)


def _coerce_text(df: pd.DataFrame, column: str, default: str = "") -> None:
    if column not in df:
        df[column] = default
    df[column] = df[column].fillna(default).astype(str).str.strip()


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "economy": "Economy", "scenario": "Scenario", "branch path": "Branch Path",
        "variable": "Variable", "year": "Year", "value": "Value", "scale": "Scale",
        "units": "Units", "source": "Source", "comment": "Comment",
        "input status": "Input Status", "shown in interface": "Shown In Interface",
        "region": "Economy",
    }
    renamed = {column: aliases.get(str(column).strip().lower(), column) for column in df.columns}
    return df.rename(columns=renamed).copy()


def _collapse_duplicate_keys(df: pd.DataFrame) -> pd.DataFrame:
    duplicate_rows = []
    for key, group in df.groupby(KEY_COLUMNS, dropna=False, sort=False):
        values = pd.to_numeric(group["Value"], errors="coerce")
        comparable = values.dropna().round(10).unique()
        raw = group["Value"].fillna("").astype(str).str.strip().unique()
        if len(comparable) > 1 or (len(comparable) == 0 and len(raw) > 1):
            duplicate_rows.append(dict(zip(KEY_COLUMNS, key)))
    if duplicate_rows:
        raise ValueError(f"Conflicting duplicate Module 1 keys: {duplicate_rows[:5]}")
    return df.drop_duplicates(subset=KEY_COLUMNS, keep="first").reset_index(drop=True)


def normalise_module1_rows(
    rows: pd.DataFrame,
    *,
    legacy_values_are_internal: bool,
) -> pd.DataFrame:
    """Convert canonical-long or legacy-wide rows to canonical display values."""
    df = _normalise_columns(rows)
    is_long = "Year" in df.columns and "Value" in df.columns
    if not is_long:
        year_columns = [column for column in df.columns if re.fullmatch(r"\d{4}", str(column).strip())]
        if not year_columns:
            raise ValueError("Module 1 submission has neither canonical Year/Value columns nor legacy year columns.")
        id_columns = [column for column in df.columns if column not in year_columns]
        df = df.melt(id_vars=id_columns, value_vars=year_columns, var_name="Year", value_name="Value")
        df = df[df["Value"].notna() & df["Value"].astype(str).str.strip().ne("")].copy()
    for column in LONG_COLUMNS:
        if column not in df:
            df[column] = ""
    _coerce_text(df, "Economy")
    df["Economy"] = df["Economy"].map(canonical_economy_code)
    for column in ["Scenario", "Branch Path", "Variable", "Scale", "Units", "Source", "Comment", "Input Status", "Shown In Interface"]:
        _coerce_text(df, column)
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    if df["Year"].isna().any():
        raise ValueError("Module 1 submission contains a non-numeric Year.")
    df["Year"] = df["Year"].astype(int)
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    if legacy_values_are_internal:
        df["Value"] = df["Value"] / df["Scale"].map(_scale_multiplier)
    return _collapse_duplicate_keys(df[LONG_COLUMNS].copy())


def normalise_module1_csv(path: str | Path, *, legacy_values_are_internal: bool | None = None) -> pd.DataFrame:
    """Read a CSV and infer whether values are canonical display or legacy internal."""
    raw = pd.read_csv(path)
    normalised_headers = {str(column).strip().lower() for column in raw.columns}
    is_canonical = {"year", "value"}.issubset(normalised_headers)
    internal = (not is_canonical) if legacy_values_are_internal is None else legacy_values_are_internal
    return normalise_module1_rows(raw, legacy_values_are_internal=internal)


def compare_submission_to_baseline(submission: pd.DataFrame, baseline: pd.DataFrame, tolerance: float = 1e-9) -> pd.DataFrame:
    """Return changed, added, and removed rows using canonical display units."""
    submitted = normalise_module1_rows(submission, legacy_values_are_internal=False)
    defaults = normalise_module1_rows(baseline, legacy_values_are_internal=False)
    merged = defaults.merge(
        submitted, on=KEY_COLUMNS, how="outer", suffixes=(" Baseline", " Submitted"), indicator=True,
    )
    records: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        action = ""
        old_value = row.get("Value Baseline")
        new_value = row.get("Value Submitted")
        if row["_merge"] == "left_only":
            action = "removed"
        elif row["_merge"] == "right_only":
            action = "added"
        elif pd.isna(old_value) != pd.isna(new_value) or (pd.notna(old_value) and abs(float(new_value) - float(old_value)) > tolerance):
            action = "changed"
        if action:
            record = {column: row[column] for column in KEY_COLUMNS}
            record.update({
                "Baseline Value": old_value, "Submitted Value": new_value,
                "Delta": (float(new_value) - float(old_value)) if pd.notna(old_value) and pd.notna(new_value) else pd.NA,
                "Action": action, "Scale": row.get("Scale Submitted") or row.get("Scale Baseline") or "",
                "Units": row.get("Units Submitted") or row.get("Units Baseline") or "",
                "Comment": row.get("Comment Submitted") or "",
            })
            records.append(record)
    return pd.DataFrame(records, columns=[*KEY_COLUMNS, "Baseline Value", "Submitted Value", "Delta", "Action", "Scale", "Units", "Comment"])


def build_final_value_overrides(review: pd.DataFrame, note_prefix: str = "Approved researcher submission") -> pd.DataFrame:
    """Convert approved changed display values back to override-engine internal units."""
    changed = review.loc[review["Action"].eq("changed")].copy()
    rows: list[dict[str, Any]] = []
    for _, row in changed.iterrows():
        submitted_value = float(row["Submitted Value"])
        rows.append({
            "Branch Path": row["Branch Path"], "Variable": row["Variable"], "Scenario": row["Scenario"],
            "Year": int(row["Year"]), "Value": submitted_value * _scale_multiplier(row.get("Scale", "")),
            "Units": row.get("Units", ""), "share_decreased_from": "",
            "note": f"{note_prefix}. Baseline={row['Baseline Value']}; submitted={submitted_value}. {row.get('Comment', '')}".strip(),
            "DO_NOT_USE": "",
        })
    return pd.DataFrame(rows, columns=OVERRIDE_COLUMNS)


def build_source_promotion_plan(review: pd.DataFrame, baseline_version: str, submission_id: str) -> pd.DataFrame:
    """Create a reviewer-owned source-promotion plan; it never changes source files."""
    plan = review.copy()
    plan["Baseline Version"] = baseline_version
    plan["Submission ID"] = submission_id
    plan["Recommended Source Owner"] = "review manually: Source/provenance determines owner"
    plan["Promotion Status"] = "pending reviewer approval"
    return plan


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=LONG_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def create_my_drive_archive_folder(
    *, refresh_token: str, client_id: str, client_secret: str,
    folder_name: str = "Road model researcher submissions", existing_folder_id: str = "",
) -> str:
    """Create the archive root or verify and retain it during an OAuth reconnection."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not all([refresh_token, client_id, client_secret]):
        raise ValueError("OAuth Drive credentials are incomplete.")
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[DRIVE_FILE_SCOPE],
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    if existing_folder_id:
        existing = service.files().get(
            fileId=existing_folder_id, fields="id,mimeType",
        ).execute()
        if existing.get("mimeType") != "application/vnd.google-apps.folder":
            raise ValueError("Configured Drive archive ID is not a folder.")
        return str(existing["id"])
    created = service.files().create(
        body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()
    return str(created["id"])


def _build_drive_service():
    """Return Drive API client, preferring the scoped My Drive OAuth route."""
    oauth_refresh_token = os.getenv("GOOGLE_DRIVE_ARCHIVE_REFRESH_TOKEN", "")
    oauth_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    oauth_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    if oauth_refresh_token or oauth_client_id or oauth_client_secret:
        if not all([oauth_refresh_token, oauth_client_id, oauth_client_secret]):
            raise ValueError("OAuth Drive archive credentials are incomplete.")
        from google.oauth2.credentials import Credentials

        credentials = Credentials(
            token=None,
            refresh_token=oauth_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=oauth_client_id,
            client_secret=oauth_client_secret,
            scopes=[DRIVE_FILE_SCOPE],
        )
        from googleapiclient.discovery import build
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    credential_file = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", "")
    credential_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "")
    if not credential_file and not credential_json:
        raise ValueError(
            "Drive archive is not configured (OAuth secrets or "
            "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON/GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE)."
        )
    from google.oauth2.service_account import Credentials

    if credential_json:
        credentials = Credentials.from_service_account_info(
            json.loads(credential_json), scopes=["https://www.googleapis.com/auth/drive"],
        )
    else:
        credentials = Credentials.from_service_account_file(
            credential_file, scopes=["https://www.googleapis.com/auth/drive"],
        )
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def archive_submission_to_drive(
    *, rows: list[dict[str, Any]], economy: str, version: str, run_id: str,
    researcher_identity: str = "", original_filename: str = "", drive_folder_id: str | None = None,
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    """Write immutable CSV + metadata to Drive. Missing credentials returns a clear failure result."""
    root_folder = drive_folder_id or os.getenv("ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID", "")
    if not root_folder:
        return {"attempted": True, "success": False, "message": "Drive archive is not configured (ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID)."}
    try:
        service = _build_drive_service()
        from googleapiclient.http import MediaIoBaseUpload

        canonical_economy = canonical_economy_code(economy)
        query = f"name = '{canonical_economy}' and '{root_folder}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        matches = service.files().list(
            q=query, fields="files(id,name)", pageSize=1,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute().get("files", [])
        economy_folder = matches[0]["id"] if matches else service.files().create(
            body={"name": canonical_economy, "mimeType": "application/vnd.google-apps.folder", "parents": [root_folder]},
            fields="id", supportsAllDrives=True,
        ).execute()["id"]
        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds").replace(":", "-")
        submission_id = f"{timestamp}_{uuid.uuid4().hex[:8]}"
        csv_name = f"{submission_id}_module1_{version}.csv"
        metadata_name = f"{submission_id}_metadata.json"
        csv_payload = _csv_bytes(rows)
        baseline_file = Path(baseline_path) if baseline_path else None
        baseline_bytes = baseline_file.read_bytes() if baseline_file and baseline_file.exists() else b""
        metadata = {
            "archive_format_version": "1.0",
            "submission_id": submission_id, "economy": canonical_economy, "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "module1_defaults_version": version, "researcher_or_session_identity": researcher_identity,
            "model_run_id": run_id, "original_filename_or_submission_identifier": original_filename or submission_id,
            "archive_csv_filename": csv_name, "archive_metadata_filename": metadata_name,
            "row_count": len(rows), "csv_sha256": hashlib.sha256(csv_payload).hexdigest(),
            "baseline_filename": baseline_file.name if baseline_file and baseline_file.exists() else "",
            "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest() if baseline_bytes else "",
        }
        csv_file = service.files().create(body={"name": csv_name, "parents": [economy_folder]}, media_body=MediaIoBaseUpload(io.BytesIO(csv_payload), mimetype="text/csv", resumable=False), fields="id,webViewLink", supportsAllDrives=True).execute()
        metadata_file = service.files().create(body={"name": metadata_name, "parents": [economy_folder]}, media_body=MediaIoBaseUpload(io.BytesIO(json.dumps(metadata, indent=2).encode("utf-8")), mimetype="application/json", resumable=False), fields="id,webViewLink", supportsAllDrives=True).execute()
        return {"attempted": True, "success": True, "message": "Submission archived to Google Drive.", "submission_id": submission_id, "csv_file_id": csv_file["id"], "metadata_file_id": metadata_file["id"]}
    except Exception as exc:  # Archive failures must never prevent a model run.
        return {"attempted": True, "success": False, "message": f"Drive archive failed: {exc}"}
