"""Opt-in backend generation of resolved Module 1 base-year packages.

The normal checked-in defaults build does not call this module.  Callers must
provide an authoritative canonical-long fallback and explicit original source
candidates, and must choose an output directory.  This keeps resolution away
from production/static packages until an operator reviews a future immutable
package.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from core.base_year_candidate_resolver import POLICIES_BY_ID, resolve_base_year_candidates
from core.base_year_variable_policy import DERIVED, policy_family_for_variable
from core.road_module1_provenance import source_lineage


CANONICAL_KEY_COLUMNS = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]
RESOLUTION_KEY_COLUMNS = ["Economy", "Scenario", "Branch Path", "Variable"]
CANONICAL_LONG_COLUMNS = [
    *CANONICAL_KEY_COLUMNS,
    "Value",
    "Scale",
    "Units",
    "Source",
    "Comment",
    "Input Status",
    "Shown In Interface",
    "Source Data Year",
    "Source Classification",
    "Base Year Treatment",
    "Derivation Method",
]
AUDIT_COLUMNS = [
    *RESOLUTION_KEY_COLUMNS,
    "requested_base_year",
    "status",
    "strategy",
    "resolver_policy_id",
    "policy_override_applied",
    "candidate_id",
    "source_id",
    "selected_source_data_year",
    "selected_source_classification",
    "base_year_treatment",
    "selection_reason",
    "rejection_count",
    "rejections",
]
SUPPORTED_STRATEGY = "prefer_earlier"


def _required_text(value: object, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


def _normalise_year(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer year.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer year.") from exc
    if not math.isfinite(numeric) or not numeric.is_integer() or not 1900 <= numeric <= 2100:
        raise ValueError(f"{field_name} must be an integer year from 1900 to 2100.")
    return int(numeric)


def _safe_output_dir(output_dir: str | Path) -> Path:
    path = Path(output_dir).resolve()
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
        raise ValueError(f"Opt-in resolved packages cannot be written under protected path {root}.")
    return path


def _canonical_fallback(
    fallback_rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    economy: str,
    requested_base_year: int,
) -> pd.DataFrame:
    frame = fallback_rows.copy(deep=True) if isinstance(fallback_rows, pd.DataFrame) else pd.DataFrame(fallback_rows)
    missing = [column for column in CANONICAL_LONG_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Fallback rows are missing canonical columns: {missing}.")
    frame = frame[CANONICAL_LONG_COLUMNS].copy()
    if frame.empty:
        raise ValueError("Fallback rows are required.")
    frame["Economy"] = frame["Economy"].map(lambda value: _required_text(value, "fallback Economy"))
    found_economies = sorted(set(frame["Economy"]))
    if found_economies != [economy]:
        raise ValueError(f"Fallback rows must contain only economy {economy!r}; found {found_economies}.")
    frame["Year"] = frame["Year"].map(lambda value: _normalise_year(value, "fallback Year"))
    found_years = sorted(set(frame["Year"]))
    if found_years != [requested_base_year]:
        raise ValueError(
            f"Fallback rows must contain only requested base year {requested_base_year}; found {found_years}."
        )
    frame["Value"] = pd.to_numeric(frame["Value"], errors="coerce")
    if frame["Value"].isna().any() or (~frame["Value"].map(math.isfinite)).any():
        raise ValueError("Fallback Value must be finite numeric data.")
    for column in ["Scenario", "Branch Path", "Variable"]:
        frame[column] = frame[column].map(lambda value: _required_text(value, f"fallback {column}"))
    duplicates = frame.duplicated(subset=CANONICAL_KEY_COLUMNS, keep=False)
    if duplicates.any():
        sample = frame.loc[duplicates, CANONICAL_KEY_COLUMNS].head(5).to_dict("records")
        raise ValueError(f"Fallback rows contain duplicate canonical keys. Sample: {sample}")
    return frame.sort_values(CANONICAL_KEY_COLUMNS, kind="stable").reset_index(drop=True)


def normalise_authoritative_fallback(
    fallback_rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    economy: str,
    requested_base_year: int,
) -> pd.DataFrame:
    """Validate and copy a complete canonical fallback without resolving it."""
    return _canonical_fallback(fallback_rows, economy, requested_base_year)


def _candidate_key(
    candidate: Mapping[str, Any],
    fallback_keys: set[tuple[str, ...]],
    source_package: str,
) -> tuple[str, ...]:
    if _required_text(candidate.get("candidate_origin"), "candidate_origin") != "original":
        raise ValueError("Candidates must declare candidate_origin='original'; shifted/generated rows are rejected.")
    row_key = candidate.get("row_key")
    if isinstance(row_key, str) or not isinstance(row_key, Sequence):
        raise ValueError("Candidate row_key must be a four-value canonical resolution key.")
    key = tuple(_required_text(value, "candidate row_key value") for value in row_key)
    if len(key) != len(RESOLUTION_KEY_COLUMNS):
        raise ValueError(f"Candidate row_key must contain {RESOLUTION_KEY_COLUMNS} in that order.")
    if key not in fallback_keys:
        raise ValueError(f"Candidate row_key is absent from the authoritative fallback: {key!r}.")
    payload = candidate.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("Candidate payload must be a canonical row mapping.")
    missing_payload = [column for column in CANONICAL_LONG_COLUMNS if column not in payload]
    if missing_payload:
        raise ValueError(f"Candidate payload is missing canonical columns: {missing_payload}.")
    payload_key = tuple(_required_text(payload.get(column), f"candidate payload {column}") for column in RESOLUTION_KEY_COLUMNS)
    if payload_key != key:
        raise ValueError(f"Candidate payload key {payload_key!r} does not match row_key {key!r}.")
    if key[-1] == "Stock Share":
        raise ValueError("Stock Share is derived from resolved Stock and cannot be supplied as a candidate.")
    value = pd.to_numeric(pd.Series([payload.get("Value")]), errors="coerce").iloc[0]
    if pd.isna(value) or not math.isfinite(float(value)):
        raise ValueError("Candidate payload Value must be finite numeric data.")
    candidate_source_year = _normalise_year(candidate.get("source_data_year"), "candidate source_data_year")
    if _normalise_year(payload.get("Year"), "candidate payload Year") != candidate_source_year:
        raise ValueError(
            "Candidate payload Year must equal source_data_year; a shifted/generated base-year row is not an original candidate."
        )
    payload_source_year = payload.get("Source Data Year")
    if payload_source_year not in (None, ""):
        if _normalise_year(payload_source_year, "candidate payload Source Data Year") != candidate_source_year:
            raise ValueError("Candidate payload Source Data Year must match candidate source_data_year.")
    payload_classification = _required_text(
        payload.get("Source Classification"), "candidate payload Source Classification"
    )
    candidate_classification = _required_text(
        candidate.get("source_classification"), "candidate source_classification"
    )
    if payload_classification != candidate_classification:
        raise ValueError("Candidate payload Source Classification must match candidate source_classification.")
    declared_lineage = str(candidate.get("source_lineage", "") or "").strip()
    expected_lineage = (
        "verified_9th_outlook"
        if source_lineage(payload.get("Source"), source_package) == "9th_outlook"
        else ""
    )
    if declared_lineage != expected_lineage:
        raise ValueError(
            "Candidate source_lineage does not match the explicit source/package lineage mapping."
        )
    return key


def _policy_overrides(overrides: Mapping[str, str] | None) -> dict[str, str]:
    normalised: dict[str, str] = {}
    for variable, policy_id in (overrides or {}).items():
        variable_name = _required_text(variable, "policy override variable")
        family = policy_family_for_variable(variable_name)
        if family.family_id == DERIVED:
            raise ValueError(f"Derived variable {variable_name!r} cannot have a resolver policy override.")
        policy_name = _required_text(policy_id, f"policy override for {variable_name!r}")
        if policy_name not in POLICIES_BY_ID:
            raise ValueError(f"Unknown resolver policy override {policy_name!r} for {variable_name!r}.")
        default_policy = family.resolver_policy_id
        if default_policy == "energy_balance_exact_year" and policy_name != default_policy:
            raise ValueError("A sparse override cannot broaden an exact-year-required variable policy.")
        normalised[variable_name] = policy_name
    return dict(sorted(normalised.items()))


def _selected_row(fallback_row: pd.Series, selected: Any, result: Any, requested_base_year: int) -> dict[str, Any]:
    payload = dict(selected.payload)
    row = fallback_row.to_dict()
    for column in CANONICAL_LONG_COLUMNS:
        if column in payload and column not in CANONICAL_KEY_COLUMNS:
            row[column] = payload[column]
    row["Year"] = requested_base_year
    row["Value"] = float(payload["Value"])
    row["Source Data Year"] = result.selected_source_data_year
    row["Source Classification"] = selected.source_classification
    row["Base Year Treatment"] = result.base_year_treatment
    row["Derivation Method"] = {
        "exact": "direct_observation",
        "earlier": "prior_observation_seed",
        "future": "future_year_seed",
    }[result.direction]
    return row


def _derive_stock_shares(rows: list[dict[str, Any]], fallback: pd.DataFrame, requested_base_year: int) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    output = pd.DataFrame(rows, columns=CANONICAL_LONG_COLUMNS)
    stock = output[output["Variable"].eq("Stock")].copy()
    stock["Value"] = pd.to_numeric(stock["Value"], errors="raise")
    derived: list[tuple[dict[str, Any], dict[str, Any]]] = []
    share_fallback = fallback[fallback["Variable"].eq("Stock Share")]
    for _, fallback_row in share_fallback.iterrows():
        branch = str(fallback_row["Branch Path"])
        scenario = str(fallback_row["Scenario"])
        if str(fallback_row["Derivation Method"]) != "stock_share_from_stock":
            row = fallback_row.to_dict()
            audit = {
                **{column: row[column] for column in RESOLUTION_KEY_COLUMNS},
                "requested_base_year": requested_base_year,
                "status": "fallback",
                "strategy": "authoritative_fallback",
                "resolver_policy_id": "",
                "policy_override_applied": False,
                "candidate_id": "",
                "source_id": "",
                "selected_source_data_year": "",
                "selected_source_classification": "",
                "base_year_treatment": row["Base Year Treatment"],
                "selection_reason": "stock_share_has_no_explicit_stock_derivation",
                "rejection_count": 0,
                "rejections": "[]",
            }
            derived.append((row, audit))
            continue
        parent = branch.rsplit("\\", 1)[0] if "\\" in branch else ""
        sibling_rows = share_fallback.loc[
            share_fallback["Scenario"].eq(scenario)
            & share_fallback["Branch Path"].astype(str).map(lambda value: value.rsplit("\\", 1)[0] if "\\" in value else "").eq(parent),
        ]
        if not sibling_rows["Derivation Method"].astype(str).eq("stock_share_from_stock").all():
            raise ValueError(
                f"Stock Share sibling group {scenario!r}/{parent!r} mixes explicit Stock derivation with fallback rows."
            )
        sibling_branches = sibling_rows["Branch Path"].astype(str).tolist()

        def branch_stock(target: str) -> float:
            mask = stock["Scenario"].eq(scenario) & (
                stock["Branch Path"].eq(target) | stock["Branch Path"].astype(str).str.startswith(target + "\\")
            )
            if not mask.any():
                raise ValueError(f"Stock Share derivation has no Stock row at or below {scenario!r}/{target!r}.")
            return float(stock.loc[mask, "Value"].sum())

        numerator = branch_stock(branch)
        denominator = sum(branch_stock(sibling) for sibling in sibling_branches)
        if denominator == 0:
            raise ValueError(f"Stock Share derivation has a zero Stock denominator for {scenario!r}/{parent!r}.")
        value = numerator / denominator * 100.0
        row = fallback_row.to_dict()
        row.update(
            {
                "Year": requested_base_year,
                "Value": value,
                "Source": "Module 1 base-year Stock rows",
                "Comment": "Stock Share derived from resolved Stock.",
                "Source Data Year": "",
                "Source Classification": "structural_assumption",
                "Base Year Treatment": "transformed",
                "Derivation Method": "stock_share_from_stock",
            }
        )
        audit = {
            **{column: row[column] for column in RESOLUTION_KEY_COLUMNS},
            "requested_base_year": requested_base_year,
            "status": "derived",
            "strategy": "derived_from_stock",
            "resolver_policy_id": "",
            "policy_override_applied": False,
            "candidate_id": "",
            "source_id": "Module 1 base-year Stock rows",
            "selected_source_data_year": "",
            "selected_source_classification": "structural_assumption",
            "base_year_treatment": "derived",
            "selection_reason": "stock_share_from_resolved_stock",
            "rejection_count": 0,
            "rejections": "[]",
        }
        derived.append((row, audit))
    return derived


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if pd.isna(value):
        return None
    return value


def generate_resolved_base_year_package(
    *,
    fallback_rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    economy: str,
    requested_base_year: int,
    source_package: str,
    package_version: str,
    output_dir: str | Path,
    strategy: str = SUPPORTED_STRATEGY,
    variable_policy_overrides: Mapping[str, str] | None = None,
    generation_time: str | None = None,
) -> dict[str, Path]:
    """Write one reviewed-candidate package without touching current defaults.

    ``fallback_rows`` defines the complete authoritative row/key set.  A valid
    selected original candidate may replace a fallback value.  An absent or
    ineligible candidate leaves the fallback row byte-for-value unchanged.
    """
    economy_name = _required_text(economy, "economy")
    year = _normalise_year(requested_base_year, "requested_base_year")
    source_package_name = _required_text(source_package, "source_package")
    version = _required_text(package_version, "package_version")
    if strategy != SUPPORTED_STRATEGY:
        raise ValueError(
            f"Unsupported strategy {strategy!r}; the existing resolver currently supports only {SUPPORTED_STRATEGY!r}."
        )
    overrides = _policy_overrides(variable_policy_overrides)
    fallback = _canonical_fallback(fallback_rows, economy_name, year)
    fallback_keys = set(fallback[RESOLUTION_KEY_COLUMNS].itertuples(index=False, name=None))

    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = {}
    candidate_ids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("Every candidate must be a mapping.")
        candidate_id = _required_text(candidate.get("candidate_id"), "candidate_id")
        if candidate_id in candidate_ids:
            raise ValueError(f"Duplicate candidate identity across package: {candidate_id!r}.")
        candidate_ids.add(candidate_id)
        key = _candidate_key(candidate, fallback_keys, source_package_name)
        grouped.setdefault(key, []).append(candidate)

    output_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for _, fallback_row in fallback[~fallback["Variable"].eq("Stock Share")].iterrows():
        key = tuple(str(fallback_row[column]) for column in RESOLUTION_KEY_COLUMNS)
        family = policy_family_for_variable(key[-1])
        if family.family_id == DERIVED:
            row = fallback_row.to_dict()
            output_rows.append(row)
            audit_rows.append(
                {
                    **{column: key[index] for index, column in enumerate(RESOLUTION_KEY_COLUMNS)},
                    "requested_base_year": year,
                    "status": "derived",
                    "strategy": "generated_authoritative_fallback",
                    "resolver_policy_id": "",
                    "policy_override_applied": False,
                    "candidate_id": "",
                    "source_id": str(row.get("Source", "")),
                    "selected_source_data_year": row.get("Source Data Year", ""),
                    "selected_source_classification": row.get("Source Classification", ""),
                    "base_year_treatment": row.get("Base Year Treatment", ""),
                    "selection_reason": "generated_derived_control_preserved",
                    "rejection_count": 0,
                    "rejections": "[]",
                }
            )
            continue
        policy_id = overrides.get(key[-1], family.resolver_policy_id)
        row_candidates = grouped.get(key, [])
        result = resolve_base_year_candidates(row_candidates, year, policy_id)
        rejections = [
            {"candidate_id": rejection.candidate_id, "reasons": list(rejection.reasons)}
            for rejection in result.rejections
        ]
        if result.selected is None:
            row = fallback_row.to_dict()
            status = "fallback"
            candidate_id = source_id = selected_year = selected_classification = treatment = ""
        else:
            row = _selected_row(fallback_row, result.selected, result, year)
            status = "resolved"
            candidate_id = result.selected.candidate_id
            source_id = result.selected.source_id
            selected_year = result.selected_source_data_year
            selected_classification = result.selected.source_classification
            treatment = result.base_year_treatment
        output_rows.append(row)
        audit_rows.append(
            {
                **{column: key[index] for index, column in enumerate(RESOLUTION_KEY_COLUMNS)},
                "requested_base_year": year,
                "status": status,
                "strategy": strategy,
                "resolver_policy_id": policy_id,
                "policy_override_applied": key[-1] in overrides,
                "candidate_id": candidate_id,
                "source_id": source_id,
                "selected_source_data_year": selected_year,
                "selected_source_classification": selected_classification,
                "base_year_treatment": treatment,
                "selection_reason": result.selection_reason,
                "rejection_count": len(rejections),
                "rejections": json.dumps(rejections, sort_keys=True, separators=(",", ":")),
            }
        )

    for row, audit in _derive_stock_shares(output_rows, fallback, year):
        output_rows.append(row)
        audit_rows.append(audit)

    output = pd.DataFrame(output_rows, columns=CANONICAL_LONG_COLUMNS).sort_values(CANONICAL_KEY_COLUMNS, kind="stable")
    if set(output[CANONICAL_KEY_COLUMNS].itertuples(index=False, name=None)) != set(
        fallback[CANONICAL_KEY_COLUMNS].itertuples(index=False, name=None)
    ):
        raise AssertionError("Resolved output changed the authoritative fallback canonical key set.")
    audit = pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS).sort_values(RESOLUTION_KEY_COLUMNS, kind="stable")

    destination = _safe_output_dir(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = f"{economy_name}_{year}"
    csv_path = destination / f"{stem}.csv"
    audit_path = destination / f"{stem}_resolution_audit.csv"
    manifest_path = destination / f"{stem}_resolution_manifest.json"
    output.to_csv(csv_path, index=False, lineterminator="\n", float_format="%.15g")
    audit.to_csv(audit_path, index=False, lineterminator="\n", float_format="%.15g")
    checksum = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    audit_checksum = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    status_counts = Counter(audit["status"].astype(str))
    rejection_counts: Counter[str] = Counter()
    for result in audit_rows:
        for rejection in json.loads(str(result["rejections"])):
            rejection_counts.update(rejection["reasons"])
    deterministic = {
        "economy": economy_name,
        "requested_base_year": year,
        "source_package": source_package_name,
        "package_version": version,
        "strategy": strategy,
        "variable_policy_overrides": overrides,
        "output_filename": csv_path.name,
        "output_sha256": checksum,
        "audit_filename": audit_path.name,
        "audit_sha256": audit_checksum,
        "summary_counts": {
            "total_rows": len(output),
            "resolved": status_counts["resolved"],
            "fallback": status_counts["fallback"],
            "derived": status_counts["derived"],
            "candidate_count": len(candidates),
            "rejected_candidate_decisions": int(audit["rejection_count"].sum()),
        },
        "rejection_reason_counts": dict(sorted(rejection_counts.items())),
    }
    timestamp = generation_time or datetime.now(timezone.utc).isoformat()
    manifest = {"generation_time": _required_text(timestamp, "generation_time"), "resolution": deterministic}
    manifest_path.write_text(
        json.dumps(_json_ready(manifest), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"resolved_csv": csv_path, "audit_csv": audit_path, "manifest_json": manifest_path}
