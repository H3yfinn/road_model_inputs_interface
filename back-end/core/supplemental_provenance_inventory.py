"""Separate, low-touch provenance inventory for active Module 1 supplements.

Supplemental inputs continue through their existing loaders.  This module only
describes their provenance and health; it never creates resolver candidates or
changes source/default values.  Reports are in memory unless a caller supplies
an output path outside protected production trees.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from core.road_module1_provenance import PROVENANCE_COLUMNS


ROAD_MODEL_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "road_model"
DEFAULT_PARAMETERS_PATH = ROAD_MODEL_DATA_DIR / "road_module1_default_parameters.json"
INVENTORY_COLUMNS = [
    "supplemental_path",
    "source_record_id",
    "source_scope",
    "canonical_variables",
    *PROVENANCE_COLUMNS,
    "evidence_grade",
    "estimation_status",
    "tracking_status",
    "review_required",
    "review_reason",
    "source_record_count",
]


@dataclass(frozen=True)
class SupplementalSourceSpec:
    relative_path: str
    canonical_variables: tuple[str, ...]
    required_columns: tuple[str, ...]
    identity_columns: tuple[str, ...]
    source_classification: str
    derivation_method: str
    metadata_limited: bool = False
    workbook_profile: bool = False


@dataclass
class SupplementalInventory:
    rows: pd.DataFrame
    summary: dict[str, Any]


SUPPLEMENTAL_SOURCE_SPECS = (
    SupplementalSourceSpec(
        "supplemental_source_files/apec_phev_utilisation_rates.csv",
        ("PHEV Electric Driving Share",),
        (
            "project_code", "economy", "vehicle_type", "data_year",
            "phev_utilisation_rate", "lower_rate", "upper_rate",
            "evidence_grade", "estimation_status",
        ),
        ("project_code", "vehicle_type"),
        "model_assumption",
        "supplemental_synthetic_estimate",
    ),
    SupplementalSourceSpec(
        "supplemental_source_files/apec_reconciliation_factors.csv",
        (
            "Reconciliation Weight Stock", "Reconciliation Weight Mileage",
            "Reconciliation Weight Efficiency", "Reconciliation Bound Lower Mileage",
            "Reconciliation Bound Upper Mileage", "Reconciliation Bound Lower Efficiency",
            "Reconciliation Bound Upper Efficiency",
        ),
        (
            "transport_type", "weight_stock", "weight_mileage", "weight_efficiency",
            "bound_lower_mileage", "bound_upper_mileage", "bound_lower_efficiency",
            "bound_upper_efficiency", "data_year", "source_note", "estimation_status",
        ),
        ("transport_type",),
        "model_assumption",
        "supplemental_synthetic_estimate",
    ),
    SupplementalSourceSpec(
        "supplemental_source_files/apec_vehicle_equivalent_weights.csv",
        (
            "Vehicle Equivalent Weight", "Vehicle Equivalent Weight Lower Bound",
            "Vehicle Equivalent Weight Upper Bound",
        ),
        (
            "vehicle_type", "vehicle_equivalent_weight", "lower_bound", "upper_bound",
            "data_year", "source_note", "estimation_status",
        ),
        ("vehicle_type",),
        "model_assumption",
        "supplemental_synthetic_estimate",
    ),
    SupplementalSourceSpec(
        "supplemental_source_files/apec_passenger_vehicle_saturation.csv",
        ("Passenger Vehicle Saturation", "Passenger Saturation Reached"),
        (
            "project_code", "economy", "data_year", "saturation_vehicles_per_1000",
            "lower_bound", "upper_bound", "evidence_grade", "estimation_status",
            "reached_saturation_lenient",
        ),
        ("project_code",),
        "model_assumption",
        "supplemental_synthetic_estimate",
    ),
    SupplementalSourceSpec(
        "supplemental_source_files/apec_lifecycle_profile_factors.csv",
        ("Turnover Rate Bound Lower", "Turnover Rate Bound Upper"),
        (
            "transport_type", "data_year", "turnover_rate_lower", "turnover_rate_upper",
            "fit_mode", "evidence_grade", "estimation_status", "source_note",
        ),
        ("transport_type",),
        "model_assumption",
        "supplemental_apec_default",
        metadata_limited=True,
    ),
    SupplementalSourceSpec(
        "supplemental_source_files/vehicle_survival_modified_00_APEC.xlsx",
        ("Survival Rate",),
        (),
        (),
        "model_assumption",
        "supplemental_lifecycle_profile",
        metadata_limited=True,
        workbook_profile=True,
    ),
    SupplementalSourceSpec(
        "supplemental_source_files/vintage_modelled_from_survival_00_APEC.xlsx",
        ("Vintage Profile Share",),
        (),
        (),
        "structural_assumption",
        "vintage_profile_from_survival",
        metadata_limited=True,
        workbook_profile=True,
    ),
)
SPECS_BY_PATH = {spec.relative_path: spec for spec in SUPPLEMENTAL_SOURCE_SPECS}


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _year(value: object) -> int | None:
    if _text(value) == "":
        return None
    if isinstance(value, bool):
        raise ValueError("data_year must be an integer year, not a boolean.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"data_year must be an integer year, got {value!r}.") from exc
    if not math.isfinite(numeric) or not numeric.is_integer() or not 1900 <= numeric <= 2100:
        raise ValueError(f"data_year must be an integer year from 1900 to 2100, got {value!r}.")
    return int(numeric)


def _record_id(relative_path: str, row_number: int) -> str:
    return f"{relative_path}#row={row_number}"


def _base_record(spec: SupplementalSourceSpec, row_number: int) -> dict[str, Any]:
    return {
        "supplemental_path": spec.relative_path,
        "source_record_id": _record_id(spec.relative_path, row_number),
        "source_scope": "",
        "canonical_variables": "; ".join(spec.canonical_variables),
        "Source": Path(spec.relative_path).name,
        "Comment": "",
        "Source Data Year": pd.NA,
        "Source Classification": spec.source_classification,
        "Base Year Treatment": "legacy_unrecorded",
        "Derivation Method": spec.derivation_method,
        "evidence_grade": "",
        "estimation_status": "",
        "tracking_status": "tracked_metadata_limited" if spec.metadata_limited else "tracked_complete",
        "review_required": False,
        "review_reason": "",
        "source_record_count": 1,
    }


def _attention_record(
    relative_path: str,
    reason: str,
    *,
    spec: SupplementalSourceSpec | None = None,
    row_number: int = 0,
) -> dict[str, Any]:
    record = _base_record(spec, row_number) if spec is not None else {
        column: "" for column in INVENTORY_COLUMNS
    }
    record.update(
        {
            "supplemental_path": relative_path,
            "source_record_id": _record_id(relative_path, row_number),
            "Source": Path(relative_path).name,
            "tracking_status": "attention_required",
            "review_required": True,
            "review_reason": reason,
            "source_record_count": 0,
        }
    )
    return record


def _csv_records(path: Path, spec: SupplementalSourceSpec) -> list[dict[str, Any]]:
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        return [_attention_record(spec.relative_path, f"unreadable_source: {exc}", spec=spec)]
    missing = [column for column in spec.required_columns if column not in frame.columns]
    if missing:
        return [_attention_record(
            spec.relative_path,
            f"missing_required_columns: {', '.join(missing)}",
            spec=spec,
        )]
    records: list[dict[str, Any]] = []
    for offset, source_row in enumerate(frame.to_dict("records"), start=2):
        record = _base_record(spec, offset)
        scope_parts = [f"{column}={_text(source_row.get(column))}" for column in spec.identity_columns]
        record["source_scope"] = "; ".join(scope_parts)
        if any(_text(source_row.get(column)) == "" for column in spec.identity_columns):
            record.update(
                tracking_status="attention_required",
                review_required=True,
                review_reason="missing_source_identity",
            )
        record["evidence_grade"] = _text(source_row.get("evidence_grade"))
        record["estimation_status"] = _text(source_row.get("estimation_status"))
        note = _text(source_row.get("source_note"))
        metadata = "; ".join(
            part for part in (
                f"evidence_grade={record['evidence_grade']}" if record["evidence_grade"] else "",
                f"estimation_status={record['estimation_status']}" if record["estimation_status"] else "",
            ) if part
        )
        record["Comment"] = "; ".join(part for part in (note, metadata) if part)
        try:
            source_year = _year(source_row.get("data_year"))
        except ValueError as exc:
            record.update(
                tracking_status="attention_required",
                review_required=True,
                review_reason=f"malformed_data_year: {exc}",
            )
            source_year = None
        record["Source Data Year"] = pd.NA if source_year is None else source_year
        if source_year is None and record["tracking_status"] == "tracked_complete":
            record["tracking_status"] = "tracked_metadata_limited"
        records.append(record)
    return records


def _workbook_profile_record(path: Path, spec: SupplementalSourceSpec) -> dict[str, Any]:
    try:
        frame = pd.read_excel(path, sheet_name="Lifecycle Profiles", header=None)
    except Exception as exc:
        return _attention_record(spec.relative_path, f"unreadable_source: {exc}", spec=spec)
    if frame.shape[0] < 5 or frame.shape[1] < 2:
        return _attention_record(spec.relative_path, "malformed_profile_sheet", spec=spec)
    header = [_text(value) for value in frame.iloc[3, :2].tolist()]
    if header != ["Year", "Value"]:
        return _attention_record(spec.relative_path, "malformed_profile_header", spec=spec)
    profile = frame.iloc[4:, :2].copy()
    profile.columns = ["Year", "Value"]
    years = pd.to_numeric(profile["Year"], errors="coerce")
    values = pd.to_numeric(profile["Value"], errors="coerce")
    if profile.empty or years.isna().any() or values.isna().any():
        return _attention_record(spec.relative_path, "malformed_profile_values", spec=spec)
    record = _base_record(spec, 1)
    area = _text(frame.iloc[0, 1])
    profile_name = _text(frame.iloc[1, 1])
    record.update(
        source_scope=f"area={area}",
        Comment=f"Profile={profile_name}; structured source year/evidence grade not recorded in workbook.",
        source_record_count=len(profile),
    )
    return record


def _mark_duplicate_identities(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    result = rows.copy(deep=True)
    healthy = ~result["review_required"].astype(bool)
    identity_columns = ["supplemental_path", "source_scope", "Source Data Year"]
    duplicates = healthy & result.duplicated(identity_columns, keep=False)
    if duplicates.any():
        result.loc[duplicates, "tracking_status"] = "attention_required"
        result.loc[duplicates, "review_required"] = True
        result.loc[duplicates, "review_reason"] = "conflicting_or_duplicate_source_identity"
    return result


def _safe_output_path(output_path: str | Path) -> Path:
    path = Path(output_path).resolve()
    repo_root = Path(__file__).resolve().parents[2]
    protected = (
        repo_root / "back-end" / "data",
        repo_root / "back-end" / "outputs" / "road_module1_defaults",
        repo_root / "front-end" / "road-module1-static",
    )
    for root in protected:
        try:
            path.relative_to(root.resolve())
        except ValueError:
            continue
        raise ValueError(f"Supplemental provenance audits cannot be written under protected path {root}.")
    return path


def build_supplemental_provenance_inventory(
    *,
    data_dir: str | Path = ROAD_MODEL_DATA_DIR,
    parameters_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> SupplementalInventory:
    """Inventory active supplements without changing or resolving their values."""
    root = Path(data_dir)
    config_path = Path(parameters_path) if parameters_path is not None else root / DEFAULT_PARAMETERS_PATH.name
    config = json.loads(config_path.read_text(encoding="utf-8"))
    active_paths = sorted(
        str(path).replace("\\", "/")
        for path in config.get("numeric_sources", [])
        if str(path).replace("\\", "/").startswith("supplemental_source_files/")
    )
    records: list[dict[str, Any]] = []
    for relative_path in active_paths:
        spec = SPECS_BY_PATH.get(relative_path)
        if spec is None:
            records.append(_attention_record(relative_path, "unconfigured_active_source"))
            continue
        source_path = root / Path(relative_path)
        if not source_path.is_file():
            records.append(_attention_record(relative_path, "missing_active_source", spec=spec))
        elif spec.workbook_profile:
            records.append(_workbook_profile_record(source_path, spec))
        else:
            records.extend(_csv_records(source_path, spec))
    rows = _mark_duplicate_identities(pd.DataFrame(records, columns=INVENTORY_COLUMNS))
    rows = rows.sort_values(
        ["supplemental_path", "source_scope", "source_record_id"], kind="stable"
    ).reset_index(drop=True)
    status_counts = Counter(rows["tracking_status"].astype(str)) if not rows.empty else Counter()
    summary = {
        "active_source_count": len(active_paths),
        "inventory_record_count": len(rows),
        "review_required_count": int(rows["review_required"].astype(bool).sum()) if not rows.empty else 0,
        "status_counts": dict(sorted(status_counts.items())),
    }
    if output_path is not None:
        destination = _safe_output_path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        rows.to_csv(destination, index=False, lineterminator="\n")
    return SupplementalInventory(rows, summary)
