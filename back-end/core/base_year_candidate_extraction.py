"""Read-only extraction of original candidates from checked-in Module 1 sources.

This adapter deliberately stops before promotion.  It reads the priority-ranked
source rows before ``load_processed_source_inputs()`` creates base-year fallback
rows, maps only rows that already have a canonical fallback key, and writes
review artifacts only through the caller-owned opt-in package generator.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from core import road_module1_defaults as defaults
from core.base_year_candidate_resolver import POLICIES_BY_ID
from core.base_year_package_generation import (
    CANONICAL_LONG_COLUMNS,
    RESOLUTION_KEY_COLUMNS,
    generate_resolved_base_year_package,
    normalise_authoritative_fallback,
)
from core.base_year_variable_policy import DERIVED, policy_family_for_variable
from core.road_module1_provenance import enrich_module1_provenance, source_lineage


STATIC_ROOT = Path(__file__).resolve().parents[2] / "front-end" / "road-module1-static"
REQUIRED_PROJECTION_SCENARIOS = frozenset({"Reference", "Target"})
CONFLICT_REPORT_COLUMNS = [
    "Conflict Group",
    "Package Component",
    "Scenario",
    "Branch Path",
    "Variable",
    "Year",
    "Candidate Value",
    "Source",
    "Source Data Year",
    "Comment",
    "Conflict Reason",
    "Reviewer Choice (select/correct)",
    "Reviewer Note (cite source/reason)",
]
CONFLICT_REVIEW_COLUMNS = [
    "Conflict Group",
    "Package Component",
    "Scenario",
    "Branch Path",
    "Variable",
    "Year",
    "Candidate Options",
    "Reviewer Choice (value/correction)",
    "Reviewer Source",
    "Reviewer Note (reason)",
]
RAW_REQUIRED_COLUMNS = [
    "Branch Path",
    "Variable",
    "Scenario",
    "Year",
    "Value",
    "Units",
    "_source_type",
    "_source_name",
    "_source_note",
    "_priority",
]
EXTRACTION_AUDIT_COLUMNS = [
    *RESOLUTION_KEY_COLUMNS,
    "source_row_year",
    "source_data_year",
    "source_classification",
    "source_lineage",
    "source_type",
    "source_name",
    "source_priority",
    "status",
    "reason",
    "candidate_id",
]


@dataclass
class CandidateExtraction:
    candidates: tuple[dict[str, Any], ...]
    audit: pd.DataFrame
    summary: dict[str, Any]


@dataclass
class StaticPackageComponents:
    current_accounts_template: pd.DataFrame
    projection_series: pd.DataFrame
    source_template_year: int


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _year(value: object) -> int | None:
    if value is None or pd.isna(value) or _text(value) == "":
        return None
    if isinstance(value, bool):
        raise ValueError("Source years must be integer years, not booleans.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Source year must be an integer year, got {value!r}.") from exc
    if not math.isfinite(numeric) or not numeric.is_integer() or not 1900 <= numeric <= 2100:
        raise ValueError(f"Source year must be an integer year from 1900 to 2100, got {value!r}.")
    return int(numeric)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _candidate_id(record: Mapping[str, Any]) -> str:
    identity = {
        "row_key": [record[column] for column in RESOLUTION_KEY_COLUMNS],
        "source_type": record["_source_type"],
        "source_name": record["_source_name"],
        "source_priority": record["_priority"],
        "payload": {column: record[column] for column in CANONICAL_LONG_COLUMNS},
    }
    digest = hashlib.sha256(
        json.dumps(_json_ready(identity), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    return f"checked_in_source:{digest}"


def load_static_fallback(
    *,
    fallback_csv: str | Path,
    economy: str,
    requested_base_year: int,
    source_package_version: str,
) -> pd.DataFrame:
    """Load one explicit checked-in/static CSV as an authoritative fallback."""
    path = Path(fallback_csv)
    if not path.is_file():
        raise ValueError(f"Fallback CSV does not exist: {path}")
    rows = pd.read_csv(path)
    missing = [column for column in CANONICAL_LONG_COLUMNS[:12] if column not in rows.columns]
    if missing:
        raise ValueError(f"Fallback CSV is missing canonical columns: {missing}.")
    years = pd.to_numeric(rows["Year"], errors="coerce")
    selected = rows[rows["Economy"].astype(str).eq(economy) & years.eq(requested_base_year)].copy()
    if selected.empty:
        available = sorted(pd.to_numeric(rows["Year"], errors="coerce").dropna().astype(int).unique())
        raise ValueError(
            f"Fallback CSV has no rows for {economy} at requested base year {requested_base_year}; "
            f"available years begin {available[:5]}."
        )
    selected = enrich_module1_provenance(
        selected,
        package_version=source_package_version,
        target_base_year=requested_base_year,
    )
    selected = _collapse_duplicate_derived_stock_shares(selected)
    return normalise_authoritative_fallback(selected, economy, requested_base_year)


def _append_template_fallback_note(comment: object, source_template_year: int) -> str:
    note = (
        f"Value retained from the reviewed {source_template_year} Current Accounts template; "
        "original source-data year is not recorded."
    )
    existing = _text(comment)
    return existing if note in existing else f"{existing} {note}".strip()


def _read_static_rows(fallback_csv: str | Path, economy: str) -> pd.DataFrame:
    path = Path(fallback_csv)
    if not path.is_file():
        raise ValueError(f"Fallback CSV does not exist: {path}")
    rows = pd.read_csv(path)
    missing = [column for column in CANONICAL_LONG_COLUMNS[:12] if column not in rows.columns]
    if missing:
        raise ValueError(f"Fallback CSV is missing canonical columns: {missing}.")
    found_economies = sorted(rows["Economy"].dropna().astype(str).str.strip().unique())
    if found_economies != [economy]:
        raise ValueError(f"Fallback CSV must contain only economy {economy!r}; found {found_economies}.")
    parsed_years = rows["Year"].map(_year)
    if parsed_years.isna().any():
        raise ValueError("Fallback CSV contains a blank Year.")
    rows["Year"] = parsed_years.astype(int)
    return rows


def _strict_projection_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """Collapse identical duplicate projection rows and reject disagreements."""
    if rows.empty:
        return pd.DataFrame(columns=CANONICAL_LONG_COLUMNS)
    key_columns = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]
    duplicate_mask = rows.duplicated(key_columns, keep=False)
    if not duplicate_mask.any():
        return rows[CANONICAL_LONG_COLUMNS].sort_values(key_columns, kind="stable").reset_index(drop=True)
    keep_indices = list(rows.index[~duplicate_mask])
    for key, group in rows[duplicate_mask].groupby(key_columns, sort=True, dropna=False):
        comparable = group[CANONICAL_LONG_COLUMNS].astype(object)
        comparable = comparable.where(comparable.notna(), "<NA>").astype(str)
        if len(comparable.drop_duplicates()) != 1:
            raise ValueError(f"Projection rows contain conflicting duplicate canonical key {key!r}.")
        keep_indices.append(group.index[0])
    return rows.loc[keep_indices, CANONICAL_LONG_COLUMNS].sort_values(
        key_columns, kind="stable"
    ).reset_index(drop=True)


def _validate_projection_coverage(rows: pd.DataFrame, requested_base_year: int) -> None:
    if rows.empty:
        return
    scenarios = set(rows["Scenario"].astype(str))
    if scenarios != REQUIRED_PROJECTION_SCENARIOS:
        raise ValueError(
            "Projection series must contain exactly Reference and Target scenarios; "
            f"found {sorted(scenarios)}."
        )
    expected_start = requested_base_year + 1
    scenario_years = {
        scenario: tuple(sorted(group["Year"].astype(int).unique()))
        for scenario, group in rows.groupby("Scenario", sort=True)
    }
    reference_years = next(iter(scenario_years.values()))
    if any(years != reference_years for years in scenario_years.values()):
        raise ValueError(f"Projection scenarios have different year coverage: {scenario_years}.")
    if reference_years[0] != expected_start:
        raise ValueError(
            f"Projection series begins at {reference_years[0]}, but requested base year "
            f"{requested_base_year} requires coverage from {expected_start}."
        )
    expected_years = tuple(range(expected_start, reference_years[-1] + 1))
    if reference_years != expected_years:
        missing = sorted(set(expected_years) - set(reference_years))
        raise ValueError(f"Projection series has missing years: {missing[:10]}.")


def _validate_projection_values(rows: pd.DataFrame) -> None:
    if rows.empty:
        return
    values = pd.to_numeric(rows["Value"], errors="coerce")
    invalid = values.isna() | ~values.map(lambda value: math.isfinite(value) if pd.notna(value) else False)
    if invalid.any():
        sample = rows.loc[
            invalid, ["Economy", "Scenario", "Branch Path", "Variable", "Year", "Value"]
        ].head(5).to_dict("records")
        raise ValueError(f"Projection series contains non-finite numeric values. Sample: {sample}")
    rows["Value"] = values


def build_static_package_conflict_report(
    *,
    fallback_csv: str | Path,
    economy: str,
    requested_base_year: int,
    source_package_version: str,
) -> pd.DataFrame:
    """Return concise evidence for duplicate groups that strict package loading rejects."""
    normalised_requested_year = _year(requested_base_year)
    if normalised_requested_year is None:
        raise ValueError("Requested base year is required.")
    rows = _read_static_rows(fallback_csv, economy)
    rows = enrich_module1_provenance(
        rows,
        package_version=source_package_version,
        target_base_year=normalised_requested_year,
    )
    components = [
        (
            "Current Accounts template",
            rows[rows["Scenario"].astype(str).str.strip().eq("Current Accounts")].copy(),
        ),
        (
            "Reference/Target projection",
            rows[
                ~rows["Scenario"].astype(str).str.strip().eq("Current Accounts")
                & rows["Year"].gt(normalised_requested_year)
            ].copy(),
        ),
    ]
    key_columns = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]
    conflict_groups: list[tuple[str, tuple[object, ...], pd.DataFrame, str]] = []
    for component_name, component_rows in components:
        duplicate_rows = component_rows[component_rows.duplicated(key_columns, keep=False)]
        for key, group in duplicate_rows.groupby(key_columns, sort=True, dropna=False):
            try:
                _collapse_duplicate_derived_stock_shares(group)
            except ValueError:
                pass
            else:
                if group["Variable"].eq("Stock Share").all():
                    continue
            if component_name == "Reference/Target projection":
                comparable = group[CANONICAL_LONG_COLUMNS].astype(object)
                comparable = comparable.where(comparable.notna(), "<NA>").astype(str)
                if len(comparable.drop_duplicates()) == 1:
                    continue
            reason = (
                "Duplicate Current Accounts canonical key requires an authoritative source choice."
                if component_name == "Current Accounts template"
                else "Projection rows disagree for the same canonical key."
            )
            conflict_groups.append((component_name, key, group, reason))

    report_rows: list[dict[str, object]] = []
    for group_number, (component_name, _key, group, reason) in enumerate(conflict_groups, start=1):
        group_id = f"conflict-{group_number:04d}"
        for _, row in group.sort_values(["Source", "Value"], kind="stable").iterrows():
            report_rows.append({
                "Conflict Group": group_id,
                "Package Component": component_name,
                "Scenario": row["Scenario"],
                "Branch Path": row["Branch Path"],
                "Variable": row["Variable"],
                "Year": row["Year"],
                "Candidate Value": row["Value"],
                "Source": row["Source"],
                "Source Data Year": row["Source Data Year"],
                "Comment": row["Comment"],
                "Conflict Reason": reason,
                "Reviewer Choice (select/correct)": "",
                "Reviewer Note (cite source/reason)": "",
            })
    return pd.DataFrame(report_rows, columns=CONFLICT_REPORT_COLUMNS)


def summarise_static_package_conflicts(report: pd.DataFrame) -> pd.DataFrame:
    """Reduce detailed conflict evidence to one simple reviewer decision row per group."""
    if report.empty:
        return pd.DataFrame(columns=CONFLICT_REVIEW_COLUMNS)
    missing = [column for column in CONFLICT_REPORT_COLUMNS if column not in report.columns]
    if missing:
        raise ValueError(f"Conflict evidence is missing columns: {missing}.")
    summary_rows: list[dict[str, object]] = []
    for group_id, group in report.groupby("Conflict Group", sort=True):
        first = group.iloc[0]
        options: list[str] = []
        for _, row in group.iterrows():
            source = _text(row["Source"]) or "source not recorded"
            source_year = _year(row["Source Data Year"])
            year_note = "" if source_year is None else f"; data year {source_year}"
            option = f"{_text(row['Candidate Value'])} [{source}{year_note}]"
            if option not in options:
                options.append(option)
        summary_rows.append({
            "Conflict Group": group_id,
            "Package Component": first["Package Component"],
            "Scenario": first["Scenario"],
            "Branch Path": first["Branch Path"],
            "Variable": first["Variable"],
            "Year": first["Year"],
            "Candidate Options": " | ".join(options),
            "Reviewer Choice (value/correction)": "",
            "Reviewer Source": "",
            "Reviewer Note (reason)": "",
        })
    return pd.DataFrame(summary_rows, columns=CONFLICT_REVIEW_COLUMNS)


def load_static_package_components(
    *,
    fallback_csv: str | Path,
    economy: str,
    requested_base_year: int,
    source_package_version: str,
) -> StaticPackageComponents:
    """Load a complete Current Accounts template and separate future projections."""
    normalised_requested_year = _year(requested_base_year)
    if normalised_requested_year is None:
        raise ValueError("Requested base year is required.")
    requested_base_year = normalised_requested_year
    rows = _read_static_rows(fallback_csv, economy)

    current_accounts = rows[rows["Scenario"].astype(str).str.strip().eq("Current Accounts")].copy()
    template_years = sorted(current_accounts["Year"].unique())
    if len(template_years) != 1:
        raise ValueError(
            "Fallback CSV must contain exactly one Current Accounts template year; "
            f"found {template_years}."
        )
    source_template_year = int(template_years[0])
    current_accounts = enrich_module1_provenance(
        current_accounts,
        package_version=source_package_version,
        target_base_year=requested_base_year,
    )
    current_accounts = _collapse_duplicate_derived_stock_shares(current_accounts)
    current_accounts["Year"] = requested_base_year
    shifted_without_source_year = (
        current_accounts["Source Data Year"].isna()
        & current_accounts["Base Year Treatment"].eq("legacy_unrecorded")
        & (source_template_year != requested_base_year)
    )
    current_accounts.loc[shifted_without_source_year, "Comment"] = current_accounts.loc[
        shifted_without_source_year, "Comment"
    ].map(lambda value: _append_template_fallback_note(value, source_template_year))
    current_accounts.loc[shifted_without_source_year, "Base Year Treatment"] = "transformed"
    current_accounts.loc[shifted_without_source_year, "Derivation Method"] = "base_year_template_fallback"
    current_accounts = normalise_authoritative_fallback(current_accounts, economy, requested_base_year)

    projection_series = rows[
        ~rows["Scenario"].astype(str).str.strip().eq("Current Accounts")
        & rows["Year"].gt(requested_base_year)
    ].copy()
    projection_series = enrich_module1_provenance(
        projection_series,
        package_version=source_package_version,
        target_base_year=requested_base_year,
    )
    projection_stock_share = projection_series[projection_series["Variable"].eq("Stock Share")]
    projection_other = projection_series[~projection_series["Variable"].eq("Stock Share")]
    projection_series = pd.concat(
        [_collapse_duplicate_derived_stock_shares(projection_stock_share), projection_other],
        ignore_index=True,
    )
    projection_series = _strict_projection_rows(projection_series)
    _validate_projection_coverage(projection_series, requested_base_year)
    _validate_projection_values(projection_series)
    return StaticPackageComponents(current_accounts, projection_series, source_template_year)


def _collapse_duplicate_derived_stock_shares(rows: pd.DataFrame) -> pd.DataFrame:
    """Prefer the explicit derived Stock Share copy when its duplicate is identical."""
    key_columns = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]
    duplicate_mask = rows.duplicated(subset=key_columns, keep=False)
    if not duplicate_mask.any():
        return rows
    keep_indices = set(rows.index[~duplicate_mask])
    for key, group in rows[duplicate_mask].groupby(key_columns, sort=True, dropna=False):
        if key[3] != "Stock Share":
            raise ValueError(f"Fallback rows contain non-derived duplicate canonical key {key!r}.")
        comparable = ["Value", "Scale", "Units", "Input Status", "Shown In Interface"]
        if any(group[column].astype(str).nunique(dropna=False) != 1 for column in comparable):
            raise ValueError(f"Fallback Stock Share duplicates disagree for canonical key {key!r}.")
        derived = group[
            group["Source"].eq("Module 1 base-year Stock rows")
            & group["Derivation Method"].isin(
                {"stock_share_from_stock", "stock_share_seeded_from_base_year_stock"}
            )
        ]
        if len(derived) != 1:
            raise ValueError(
                f"Fallback Stock Share duplicate {key!r} must contain exactly one explicit Stock-derived source row."
            )
        keep_indices.add(derived.index[0])
    return rows.loc[sorted(keep_indices)].copy()


def extract_original_candidates(
    *,
    fallback_rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    ranked_source_rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    economy: str,
    requested_base_year: int,
    source_package_version: str,
) -> CandidateExtraction:
    """Map pre-fallback ranked source rows to deterministic resolver candidates."""
    fallback = normalise_authoritative_fallback(fallback_rows, economy, requested_base_year)
    templates = {
        tuple(row[column] for column in RESOLUTION_KEY_COLUMNS): row
        for row in fallback.to_dict("records")
    }
    raw = ranked_source_rows.copy(deep=True) if isinstance(ranked_source_rows, pd.DataFrame) else pd.DataFrame(ranked_source_rows)
    missing = [column for column in RAW_REQUIRED_COLUMNS if column not in raw.columns]
    if missing:
        raise ValueError(f"Ranked source rows are missing required extraction columns: {missing}.")
    if raw.empty:
        return CandidateExtraction((), pd.DataFrame(columns=EXTRACTION_AUDIT_COLUMNS), {
            "source_rows_total": 0,
            "matched_rows": 0,
            "candidate_count": 0,
            "status_counts": {},
        })

    records: list[dict[str, Any]] = []
    for raw_record in raw.to_dict("records"):
        key = (economy, _text(raw_record["Scenario"]), _text(raw_record["Branch Path"]), _text(raw_record["Variable"]))
        template = templates.get(key)
        if template is None:
            continue
        row_year = _year(raw_record["Year"])
        value = pd.to_numeric(pd.Series([raw_record["Value"]]), errors="coerce").iloc[0]
        if row_year is None or pd.isna(value) or not math.isfinite(float(value)):
            raise ValueError(f"Matched source row has invalid year/value for key {key!r}.")
        payload = dict(template)
        payload.update(
            {
                "Year": row_year,
                "Value": defaults._to_display_value(float(value), template.get("Scale", "")),
                "Units": _text(raw_record["Units"]) or template.get("Units", ""),
                "Source": _text(raw_record.get("Source")) or _text(raw_record["_source_name"]),
                "Comment": _text(raw_record.get("Comment")) or _text(raw_record["_source_note"]),
                "Source Data Year": raw_record.get("Source Data Year", pd.NA),
                "Source Classification": _text(raw_record.get("Source Classification")),
                "Base Year Treatment": _text(raw_record.get("Base Year Treatment")),
                "Derivation Method": _text(raw_record.get("Derivation Method")),
            }
        )
        payload = enrich_module1_provenance(
            pd.DataFrame([payload]),
            package_version=source_package_version,
            target_base_year=requested_base_year,
        ).iloc[0].to_dict()
        records.append(
            {
                **payload,
                "_source_type": _text(raw_record["_source_type"]),
                "_source_name": _text(raw_record["_source_name"]),
                "_priority": int(raw_record["_priority"]),
                "_source_lineage": (
                    "verified_9th_outlook"
                    if source_lineage(payload["Source"], source_package_version) == "9th_outlook"
                    else ""
                ),
            }
        )

    audit_rows: list[dict[str, Any]] = []
    usable: list[dict[str, Any]] = []
    for record in records:
        source_year = _year(record.get("Source Data Year"))
        family = policy_family_for_variable(_text(record["Variable"]))
        reason = ""
        if family.family_id == DERIVED:
            reason = "derived_variable_not_a_candidate"
        elif source_year is None:
            reason = "missing_source_data_year"
        elif int(record["Year"]) != source_year:
            reason = "source_row_year_differs_from_source_data_year"
        if reason:
            audit_rows.append(_audit_record(record, "excluded", reason, ""))
        else:
            usable.append(record)

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in usable:
        group_key = tuple(record[column] for column in RESOLUTION_KEY_COLUMNS) + (int(record["Year"]),)
        grouped.setdefault(group_key, []).append(record)

    candidates: list[dict[str, Any]] = []
    for group_key in sorted(grouped):
        group = grouped[group_key]
        family = policy_family_for_variable(str(group_key[-2]))
        eligible = POLICIES_BY_ID[family.resolver_policy_id].eligible_classifications
        eligible_lineages = POLICIES_BY_ID[family.resolver_policy_id].eligible_source_lineages
        eligible_rows = [
            row for row in group
            if row["Source Classification"] in eligible or row["_source_lineage"] in eligible_lineages
        ]
        priority_pool = eligible_rows or group
        selected_priority = min(int(row["_priority"]) for row in priority_pool)
        finalists = [row for row in priority_pool if int(row["_priority"]) == selected_priority]
        values = {round(float(row["Value"]), 12) for row in finalists}
        if len(values) > 1:
            sample = [
                {"source": row["_source_name"], "value": row["Value"], "priority": row["_priority"]}
                for row in finalists[:5]
            ]
            raise ValueError(f"Original candidates conflict at the same source priority for {group_key!r}: {sample}")
        winner = min(finalists, key=_candidate_id)
        candidate_id = _candidate_id(winner)
        candidate = {
            "candidate_id": candidate_id,
            "candidate_origin": "original",
            "row_key": [winner[column] for column in RESOLUTION_KEY_COLUMNS],
            "source_id": f"{winner['_source_type']}:{winner['_source_name']}",
            "source_data_year": int(winner["Source Data Year"]),
            "source_classification": winner["Source Classification"],
            "source_lineage": winner["_source_lineage"],
            "quality_tier": "default",
            "source_priority_id": "default",
            "payload": {column: winner[column] for column in CANONICAL_LONG_COLUMNS},
        }
        candidates.append(candidate)
        for row in group:
            if row is winner:
                audit_rows.append(_audit_record(row, "candidate", "priority_winner", candidate_id))
            else:
                if eligible_rows and not any(row is eligible_row for eligible_row in eligible_rows):
                    reason = "ineligible_source_classification"
                elif any(row is finalist for finalist in finalists):
                    reason = "duplicate_same_value"
                else:
                    reason = "lower_priority_source_row"
                audit_rows.append(_audit_record(row, "excluded", reason, ""))

    candidates.sort(key=lambda item: item["candidate_id"])
    audit = pd.DataFrame(audit_rows, columns=EXTRACTION_AUDIT_COLUMNS).sort_values(
        [
            *RESOLUTION_KEY_COLUMNS,
            "source_row_year",
            "source_name",
            "status",
            "reason",
            "candidate_id",
        ],
        kind="stable",
    ).reset_index(drop=True)
    status_counts = Counter(audit["status"].astype(str)) if not audit.empty else Counter()
    reason_counts = Counter(audit["reason"].astype(str)) if not audit.empty else Counter()
    summary = {
        "source_rows_total": len(raw),
        "matched_rows": len(records),
        "candidate_count": len(candidates),
        "status_counts": dict(sorted(status_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
    }
    return CandidateExtraction(tuple(candidates), audit, summary)


def _audit_record(record: Mapping[str, Any], status: str, reason: str, candidate_id: str) -> dict[str, Any]:
    return {
        **{column: record[column] for column in RESOLUTION_KEY_COLUMNS},
        "source_row_year": int(record["Year"]),
        "source_data_year": record.get("Source Data Year", ""),
        "source_classification": record.get("Source Classification", ""),
        "source_lineage": record.get("_source_lineage", ""),
        "source_type": record["_source_type"],
        "source_name": record["_source_name"],
        "source_priority": int(record["_priority"]),
        "status": status,
        "reason": reason,
        "candidate_id": candidate_id,
    }


def load_checked_in_ranked_source_rows(economy: str) -> pd.DataFrame:
    """Read the checked-in source pool before generated base-year fallback rows."""
    return defaults._load_ranked_source_rows(defaults.get_economy_info(economy)).copy(deep=True)


def generate_checked_in_source_review_package(
    *,
    economy: str,
    requested_base_year: int,
    source_package_version: str,
    package_version: str,
    output_dir: str | Path,
    fallback_csv: str | Path | None = None,
    generation_time: str | None = None,
) -> dict[str, Path]:
    """Extract checked-in candidates and write a review-only resolved package."""
    source_path = Path(fallback_csv) if fallback_csv is not None else (
        STATIC_ROOT / source_package_version / f"{economy}.csv"
    )
    components = load_static_package_components(
        fallback_csv=source_path,
        economy=economy,
        requested_base_year=requested_base_year,
        source_package_version=source_package_version,
    )
    fallback = components.current_accounts_template
    extraction = extract_original_candidates(
        fallback_rows=fallback,
        ranked_source_rows=load_checked_in_ranked_source_rows(economy),
        economy=economy,
        requested_base_year=requested_base_year,
        source_package_version=source_package_version,
    )
    paths = generate_resolved_base_year_package(
        fallback_rows=fallback,
        candidates=extraction.candidates,
        economy=economy,
        requested_base_year=requested_base_year,
        source_package=source_package_version,
        package_version=package_version,
        output_dir=output_dir,
        generation_time=generation_time,
    )
    destination = paths["resolved_csv"].parent
    stem = f"{economy}_{requested_base_year}"
    candidates_path = destination / f"{stem}_original_candidates.json"
    extraction_audit_path = destination / f"{stem}_candidate_extraction_audit.csv"
    candidates_path.write_text(
        json.dumps(_json_ready(extraction.candidates), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    extraction.audit.to_csv(extraction_audit_path, index=False, lineterminator="\n")
    projection_path = destination / f"{stem}_projection_series.csv"
    complete_path = destination / f"{stem}_complete_package.csv"
    components.projection_series.to_csv(
        projection_path, index=False, lineterminator="\n", float_format="%.15g"
    )
    resolved_current_accounts = pd.read_csv(paths["resolved_csv"])
    complete = pd.concat(
        [resolved_current_accounts, components.projection_series], ignore_index=True
    )[CANONICAL_LONG_COLUMNS]
    complete = complete.sort_values(
        ["Economy", "Scenario", "Branch Path", "Variable", "Year"], kind="stable"
    ).reset_index(drop=True)
    complete_keys = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]
    duplicate_complete = complete.duplicated(complete_keys, keep=False)
    if duplicate_complete.any():
        sample = complete.loc[duplicate_complete, complete_keys].head(5).to_dict("records")
        raise ValueError(f"Combined package contains duplicate canonical keys. Sample: {sample}")
    complete.to_csv(complete_path, index=False, lineterminator="\n", float_format="%.15g")
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
    manifest["resolution"]["candidate_extraction"] = {
        **extraction.summary,
        "candidates_filename": candidates_path.name,
        "candidates_sha256": hashlib.sha256(candidates_path.read_bytes()).hexdigest(),
        "audit_filename": extraction_audit_path.name,
        "audit_sha256": hashlib.sha256(extraction_audit_path.read_bytes()).hexdigest(),
    }
    manifest["package_components"] = {
        "current_accounts_template_source_year": components.source_template_year,
        "current_accounts_filename": paths["resolved_csv"].name,
        "current_accounts_sha256": hashlib.sha256(paths["resolved_csv"].read_bytes()).hexdigest(),
        "current_accounts_row_count": len(resolved_current_accounts),
        "projection_filename": projection_path.name,
        "projection_sha256": hashlib.sha256(projection_path.read_bytes()).hexdigest(),
        "projection_row_count": len(components.projection_series),
        "projection_first_year": (
            None if components.projection_series.empty else int(components.projection_series["Year"].min())
        ),
        "complete_package_filename": complete_path.name,
        "complete_package_sha256": hashlib.sha256(complete_path.read_bytes()).hexdigest(),
        "complete_package_row_count": len(complete),
    }
    paths["manifest_json"].write_text(
        json.dumps(_json_ready(manifest), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        **paths,
        "candidates_json": candidates_path,
        "candidate_extraction_audit_csv": extraction_audit_path,
        "projection_csv": projection_path,
        "complete_package_csv": complete_path,
    }
