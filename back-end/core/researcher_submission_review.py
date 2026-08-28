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
    "Source Data Year", "Source Classification", "Base Year Treatment", "Derivation Method",
]
LEGACY_LONG_COLUMNS = LONG_COLUMNS[:12]
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
ECONOMY_CODE_RE = re.compile(r"^(?P<number>\d{2})_?(?P<letters>[A-Za-z]{2,3})$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,199}$")
SOURCE_CLASSIFICATIONS = {"native_observation", "projection", "structural_assumption", "model_assumption", "legacy_unknown"}
BASE_YEAR_TREATMENTS = {"native", "carried_forward", "carried_backward", "transformed", "legacy_unrecorded"}


def canonical_economy_code(value: object) -> str:
    """Normalise compact economy codes, e.g. 20USA -> 20_USA."""
    text = str(value or "").strip()
    match = ECONOMY_CODE_RE.fullmatch(text)
    if not match:
        raise ValueError(f"Invalid economy code: {text!r}.")
    return f"{match.group('number')}_{match.group('letters').upper()}"


def validate_version(value: object) -> str:
    """Return a version that is safe to use as one path/filename component."""
    text = str(value or "").strip()
    if not VERSION_RE.fullmatch(text) or text in {".", ".."}:
        raise ValueError(f"Invalid Module 1 defaults version: {text!r}.")
    return text


def validate_identifier(value: object, field_name: str) -> str:
    """Validate an audit identifier without allowing path separators/control text."""
    text = str(value or "").strip()
    if not IDENTIFIER_RE.fullmatch(text) or text in {".", ".."}:
        raise ValueError(f"Invalid {field_name}: {text!r}.")
    return text


def path_within(root: str | Path, *parts: str) -> Path:
    """Build a descendant path and reject traversal outside its configured root."""
    root_path = Path(root).resolve()
    candidate = root_path.joinpath(*parts).resolve()
    if candidate != root_path and root_path not in candidate.parents:
        raise ValueError(f"Derived path escapes configured directory: {candidate}")
    return candidate


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
        "source data year": "Source Data Year", "source classification": "Source Classification",
        "base year treatment": "Base Year Treatment", "derivation method": "Derivation Method",
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
    for column in ["Scenario", "Branch Path", "Variable", "Scale", "Units", "Source", "Comment", "Input Status", "Shown In Interface", "Source Classification", "Base Year Treatment", "Derivation Method"]:
        _coerce_text(df, column)
    df["Source Classification"] = df["Source Classification"].replace("", "legacy_unknown")
    df["Base Year Treatment"] = df["Base Year Treatment"].replace("", "legacy_unrecorded")
    df["Derivation Method"] = df["Derivation Method"].replace("", "legacy_unrecorded")
    unknown_classifications = set(df["Source Classification"]) - SOURCE_CLASSIFICATIONS
    unknown_treatments = set(df["Base Year Treatment"]) - BASE_YEAR_TREATMENTS
    if unknown_classifications or unknown_treatments:
        raise ValueError(f"Unknown provenance values: classifications={sorted(unknown_classifications)}, treatments={sorted(unknown_treatments)}")
    raw_source_year = df["Source Data Year"]
    source_year = pd.to_numeric(raw_source_year, errors="coerce")
    has_source_year = raw_source_year.notna() & ~raw_source_year.astype(str).str.strip().isin({"", "nan", "<NA>"})
    invalid_source_year = has_source_year & source_year.isna()
    if invalid_source_year.any():
        raise ValueError("Module 1 submission contains a non-numeric Source Data Year.")
    df["Source Data Year"] = source_year.astype("Int64")
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    if df["Year"].isna().any():
        raise ValueError("Module 1 submission contains a non-numeric Year.")
    df["Year"] = df["Year"].astype(int)
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    if legacy_values_are_internal:
        df["Value"] = df["Value"] / df["Scale"].map(_scale_multiplier)
    return _collapse_duplicate_keys(df[LONG_COLUMNS].copy())


def canonical_archive_rows(rows: list[dict[str, Any]], expected_economy: str) -> pd.DataFrame:
    """Validate request rows and return a complete canonical-long archive table."""
    if not rows:
        raise ValueError("A changed submission cannot be archived without Module 1 rows.")
    raw = pd.DataFrame(rows)
    headers = {str(column).strip().lower() for column in raw.columns}
    if not {"year", "value"}.issubset(headers):
        raise ValueError("Changed submissions must use canonical-long Year/Value rows.")
    canonical = normalise_module1_rows(raw, legacy_values_are_internal=False)
    if canonical.empty:
        raise ValueError("A changed submission cannot archive an empty Module 1 table.")
    if canonical["Value"].isna().any():
        raise ValueError("Module 1 archive rows contain a non-numeric Value.")
    economy = canonical_economy_code(expected_economy)
    found = set(canonical["Economy"])
    if found != {economy}:
        raise ValueError(f"Archive row economies {sorted(found)} do not match request economy {economy}.")
    return canonical[LONG_COLUMNS].copy()


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


def _escape_spreadsheet_formula(value: Any) -> Any:
    """Neutralise strings that spreadsheet applications could execute as formulas."""
    if isinstance(value, str) and re.match(r"^[\t\r ]*[=+\-@]", value):
        return "'" + value
    return value


def write_reviewer_csv(rows: pd.DataFrame, path: str | Path) -> None:
    """Write a review artefact with formula-like text rendered inert."""
    safe = rows.copy()
    for column in safe.columns:
        safe[column] = safe[column].map(_escape_spreadsheet_formula)
    safe.to_csv(path, index=False)


def _csv_bytes(rows: pd.DataFrame | list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=LONG_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    records = rows.to_dict(orient="records") if isinstance(rows, pd.DataFrame) else rows
    writer.writerows(records)
    return buffer.getvalue().encode("utf-8")


DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def get_drive_archive_status(drive_folder_id: str | None = None) -> dict[str, str | bool]:
    """Check archive availability without creating, updating, or deleting Drive data."""
    root_folder = drive_folder_id or os.getenv("ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID", "")
    if not root_folder:
        return {"available": False, "message": "The researcher archive is not configured."}
    try:
        service = _build_drive_service()
        folder = service.files().get(
            fileId=root_folder,
            fields="id,mimeType,trashed,capabilities(canAddChildren)",
            supportsAllDrives=True,
        ).execute()
        if folder.get("mimeType") != "application/vnd.google-apps.folder" or folder.get("trashed"):
            raise ValueError("Configured archive folder is unavailable.")
        if (folder.get("capabilities") or {}).get("canAddChildren") is False:
            raise ValueError("Configured archive folder cannot accept submissions.")
    except Exception:
        return {"available": False, "message": "The researcher archive cannot currently be reached."}
    return {"available": True, "message": "The researcher archive is available."}


def _ensure_link_viewer_permission(service: Any, folder_id: str, permissions: list[dict[str, Any]]) -> None:
    """Ensure anonymous/link access is viewer-only, matching the documented archive policy."""
    anyone_permissions = [item for item in permissions if item.get("type") == "anyone"]
    if any(item.get("role") != "reader" for item in anyone_permissions):
        raise ValueError("Archive folder has non-viewer public/link access; correct it before connecting.")
    if not anyone_permissions:
        service.permissions().create(
            fileId=folder_id,
            body={"type": "anyone", "role": "reader"},
            fields="id,type,role",
            supportsAllDrives=True,
        ).execute()


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
            fileId=existing_folder_id, fields="id,mimeType,permissions(id,type,role)",
        ).execute()
        if existing.get("mimeType") != "application/vnd.google-apps.folder":
            raise ValueError("Configured Drive archive ID is not a folder.")
        _ensure_link_viewer_permission(service, str(existing["id"]), existing.get("permissions", []))
        return str(existing["id"])
    created = service.files().create(
        body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()
    _ensure_link_viewer_permission(service, str(created["id"]), [])
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
            json.loads(credential_json), scopes=[DRIVE_FILE_SCOPE],
        )
    else:
        credentials = Credentials.from_service_account_file(
            credential_file, scopes=[DRIVE_FILE_SCOPE],
        )
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def archive_submission_to_drive(
    *, rows: list[dict[str, Any]], economy: str, version: str, run_id: str,
    researcher_identity: str = "", original_filename: str = "", drive_folder_id: str | None = None,
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    """Publish a validated immutable CSV/metadata pair to Drive."""
    root_folder = drive_folder_id or os.getenv("ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID", "")
    if not root_folder:
        return {"attempted": True, "success": False, "message": "Drive archive is not configured (ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID)."}
    try:
        canonical_economy = canonical_economy_code(economy)
        version = validate_version(version)
        run_id = validate_identifier(run_id, "model run ID")
        canonical_rows = canonical_archive_rows(rows, canonical_economy)
        csv_payload = _csv_bytes(canonical_rows)
        baseline_file = Path(baseline_path) if baseline_path else None
        if not baseline_file or not baseline_file.is_file():
            raise ValueError("The exact baseline CSV is required before a changed submission can be archived.")
        expected_baseline_name = f"{canonical_economy.replace('_', '')}.csv"
        if baseline_file.name != expected_baseline_name:
            raise ValueError(
                f"Baseline filename must be {expected_baseline_name!r}, got {baseline_file.name!r}."
            )
        baseline_bytes = baseline_file.read_bytes()

        service = _build_drive_service()
        from googleapiclient.http import MediaIoBaseUpload

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
        metadata = {
            "archive_format_version": "2.0",
            "submission_id": submission_id, "economy": canonical_economy, "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "module1_defaults_version": version, "researcher_or_session_identity": researcher_identity,
            "model_run_id": run_id, "original_filename_or_submission_identifier": original_filename or submission_id,
            "archive_csv_filename": csv_name, "archive_metadata_filename": metadata_name,
            "row_count": len(canonical_rows), "csv_sha256": hashlib.sha256(csv_payload).hexdigest(),
            "baseline_filename": baseline_file.name,
            "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
            "canonical_long_columns": LONG_COLUMNS,
            "pair_state": "complete",
        }
        staged_suffix = f".pending-{uuid.uuid4().hex}"
        created_ids: list[str] = []
        try:
            csv_file = service.files().create(
                body={"name": csv_name + staged_suffix, "parents": [economy_folder]},
                media_body=MediaIoBaseUpload(io.BytesIO(csv_payload), mimetype="text/csv", resumable=False),
                fields="id,webViewLink", supportsAllDrives=True,
            ).execute()
            created_ids.append(str(csv_file["id"]))
            staging_metadata = {**metadata, "pair_state": "staging", "archive_csv_file_id": csv_file["id"]}
            metadata_file = service.files().create(
                body={"name": metadata_name + staged_suffix, "parents": [economy_folder]},
                media_body=MediaIoBaseUpload(io.BytesIO(json.dumps(staging_metadata, indent=2).encode("utf-8")), mimetype="application/json", resumable=False),
                fields="id,webViewLink", supportsAllDrives=True,
            ).execute()
            created_ids.append(str(metadata_file["id"]))
            metadata.update({
                "archive_csv_file_id": str(csv_file["id"]),
                "archive_metadata_file_id": str(metadata_file["id"]),
            })
            service.files().update(
                fileId=metadata_file["id"],
                media_body=MediaIoBaseUpload(io.BytesIO(json.dumps(metadata, indent=2).encode("utf-8")), mimetype="application/json", resumable=False),
                fields="id", supportsAllDrives=True,
            ).execute()
            service.files().update(fileId=csv_file["id"], body={"name": csv_name}, fields="id,name", supportsAllDrives=True).execute()
            service.files().update(fileId=metadata_file["id"], body={"name": metadata_name}, fields="id,name", supportsAllDrives=True).execute()
        except Exception:
            for file_id in reversed(created_ids):
                try:
                    service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
                except Exception:
                    pass
            raise
        return {"attempted": True, "success": True, "message": "Submission archived to Google Drive.", "submission_id": submission_id, "csv_file_id": csv_file["id"], "metadata_file_id": metadata_file["id"]}
    except Exception as exc:  # Archive failures must never prevent a model run.
        return {"attempted": True, "success": False, "message": f"Drive archive failed: {exc}"}
