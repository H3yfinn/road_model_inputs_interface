"""Deterministic provenance enrichment for canonical-long Road Module 1 rows.

The component is deliberately file-system independent.  Callers supply rows,
the package version, and (where relevant) the economy base year.  The default
lineage rules name only the checked-in legacy packages whose 9th Outlook origin
is documented; an unfamiliar filename or future package remains unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
import re
from typing import Iterable

import pandas as pd


PROVENANCE_COLUMNS = (
    "Source",
    "Comment",
    "Source Data Year",
    "Source Classification",
    "Base Year Treatment",
    "Derivation Method",
)
VALID_SOURCE_CLASSIFICATIONS = frozenset(
    {"native_observation", "projection", "structural_assumption", "model_assumption", "legacy_unknown"}
)
VALID_BASE_YEAR_TREATMENTS = frozenset(
    {"native", "carried_forward", "carried_backward", "transformed", "legacy_unrecorded"}
)
LEGACY_GUIDANCE = (
    "Legacy input — original source detail not yet recorded; please update when better evidence is available."
)
NINTH_OUTLOOK_ARCHIVE_URL = (
    "https://drive.google.com/file/d/103sIJ1L1mbQpGfL2shlB8nrIOTkbyFz3/view?usp=drive_link"
)
NINTH_OUTLOOK_GUIDANCE = (
    "9th Outlook legacy input — row-level provenance is preserved in the archived 9th-edition "
    f"transport data system and can be investigated on demand: {NINTH_OUTLOOK_ARCHIVE_URL}. "
    "The displayed value may also reflect subsequent aggregation, disaggregation, or model reconciliation."
)
CURRENT_SOURCE_PACKAGE_VERSION = "v2026_06_05_road_module1_sources"


@dataclass(frozen=True)
class LineageRule:
    """One explicit, reviewable source-name-to-lineage mapping."""

    rule_id: str
    source_glob: str
    package_versions: frozenset[str]
    lineage: str
    fallback_source_data_year: int | None = None


DEFAULT_LINEAGE_RULES = (
    LineageRule(
        rule_id="current_processed_source_from_9th_outlook_transport_bridge",
        source_glob="road_module1_source_*.csv",
        package_versions=frozenset({CURRENT_SOURCE_PACKAGE_VERSION}),
        lineage="9th_outlook",
        fallback_source_data_year=2022,
    ),
    LineageRule(
        rule_id="target_20260526_transport_export_from_9th_outlook_bridge",
        source_glob="transport_leap_export_combined_*_domestic_international_Target_20260526.xlsx",
        package_versions=frozenset({CURRENT_SOURCE_PACKAGE_VERSION}),
        lineage="9th_outlook",
        fallback_source_data_year=2022,
    ),
    LineageRule(
        rule_id="reference_20260615_transport_export_from_9th_outlook_bridge",
        source_glob="transport_leap_export_combined_*_domestic_international_Reference_20260615.xlsx",
        package_versions=frozenset({CURRENT_SOURCE_PACKAGE_VERSION}),
        lineage="9th_outlook",
        fallback_source_data_year=2022,
    ),
)


def _is_blank(value: object) -> bool:
    return value is None or pd.isna(value) or str(value).strip() in {"", "<NA>", "nan", "None"}


def _text(value: object) -> str:
    return "" if _is_blank(value) else str(value).strip()


def _normalise_year(value: object, field_name: str) -> int | None:
    if _is_blank(value):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer year, not a boolean.")
    text = str(value).strip()
    if not re.fullmatch(r"[+-]?\d+(?:\.0+)?", text):
        raise ValueError(f"{field_name} must be an integer year, got {value!r}.")
    year = int(float(text))
    if not 1900 <= year <= 2100:
        raise ValueError(f"{field_name} {year} is outside the supported range 1900–2100.")
    return year


def _matching_lineage_rule(
    source: str,
    package_version: str,
    rules: Iterable[LineageRule],
) -> LineageRule | None:
    source_parts = [part.strip() for part in source.split(";") if part.strip()]
    matches = [
        rule
        for rule in rules
        if package_version in rule.package_versions
        and any(fnmatchcase(part, rule.source_glob) for part in source_parts)
    ]
    if len(matches) > 1:
        raise ValueError(f"Source {source!r} matches multiple provenance lineage rules.")
    return matches[0] if matches else None


def _derived_kind(row: pd.Series) -> tuple[str, str, str] | None:
    source = _text(row.get("Source"))
    comment = _text(row.get("Comment"))
    variable = _text(row.get("Variable"))
    if source == "generated_default_correction_factor":
        return "model_assumption", "generated_default_correction_factor", "Generated Module 1 correction-factor default."
    if variable == "Stock Share" and "seeded from" in comment.lower():
        return "structural_assumption", "stock_share_seeded_from_base_year_stock", "Stock Share derived from resolved Stock."
    if variable == "Stock Share" and (
        source == "Module 1 base-year Stock rows" or "derived from" in comment.lower()
    ):
        return "structural_assumption", "stock_share_from_stock", "Stock Share derived from resolved Stock."
    if "specialist override package" in comment.lower():
        return "model_assumption", "survival_based_replacement_sales_share", "Generated specialist sales-share replacement assumption."
    if "cloned from" in comment.lower() or "cloned_from_" in source:
        return "projection", "scenario_clone", "Projected row cloned from another scenario."
    return None


def _append_guidance(existing: str, guidance: str, lineage_source: str) -> str:
    if guidance in existing:
        return existing
    lineage_note = f" Pipeline lineage: {lineage_source}." if lineage_source else ""
    return f"{existing} {guidance}{lineage_note}".strip()


def enrich_module1_provenance(
    rows: pd.DataFrame,
    *,
    package_version: str,
    target_base_year: int | None = None,
    lineage_rules: Iterable[LineageRule] = DEFAULT_LINEAGE_RULES,
) -> pd.DataFrame:
    """Return canonical-long rows with conservative, idempotent provenance.

    Numeric values and canonical row keys are never changed.  Explicit source
    metadata wins.  A missing source year is filled only by a matching lineage
    rule or an identified derived/generated rule.
    """
    df = rows.copy(deep=True)
    for column in PROVENANCE_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA if column == "Source Data Year" else ""

    base_year = _normalise_year(target_base_year, "target_base_year")
    normalised_rules = tuple(lineage_rules)
    for rule in normalised_rules:
        if not isinstance(rule, LineageRule):
            raise ValueError("Each lineage rule must be a LineageRule.")
        if not rule.rule_id.strip() or not rule.source_glob.strip() or not rule.package_versions:
            raise ValueError("Lineage rules require an id, source glob, and package version.")
        if rule.lineage != "9th_outlook":
            raise ValueError(f"Unsupported provenance lineage {rule.lineage!r}.")
        _normalise_year(rule.fallback_source_data_year, f"{rule.rule_id}.fallback_source_data_year")

    enriched_rows: list[dict[str, object]] = []
    for _, raw_row in df.iterrows():
        row = raw_row.to_dict()
        source = _text(row.get("Source"))
        comment = _text(row.get("Comment"))
        explicit_year = _normalise_year(row.get("Source Data Year"), "Source Data Year")
        classification = _text(row.get("Source Classification"))
        treatment = _text(row.get("Base Year Treatment"))
        derivation = _text(row.get("Derivation Method"))
        if classification and classification not in VALID_SOURCE_CLASSIFICATIONS:
            raise ValueError(f"Unsupported Source Classification {classification!r}.")
        if treatment and treatment not in VALID_BASE_YEAR_TREATMENTS:
            raise ValueError(f"Unsupported Base Year Treatment {treatment!r}.")

        derived = _derived_kind(raw_row)
        lineage_rule = _matching_lineage_rule(source, package_version, normalised_rules)
        source_year = explicit_year

        if derived is not None:
            derived_classification, derived_method, derived_guidance = derived
            classification = classification or derived_classification
            derivation = derivation if derivation not in {"", "legacy_unrecorded"} else derived_method
            comment = _append_guidance(comment, derived_guidance, source)
            if treatment in {"", "legacy_unrecorded"} and _text(row.get("Scenario")) == "Current Accounts":
                treatment = "transformed"
        elif lineage_rule is not None and lineage_rule.lineage == "9th_outlook":
            if source_year is None:
                source_year = lineage_rule.fallback_source_data_year
            classification = classification or "legacy_unknown"
            comment = _append_guidance(comment, NINTH_OUTLOOK_GUIDANCE, source)
        else:
            classification = classification or "legacy_unknown"
            if not source or classification == "legacy_unknown":
                comment = _append_guidance(comment, LEGACY_GUIDANCE, source)

        if treatment in {"", "legacy_unrecorded"} and _text(row.get("Scenario")) == "Current Accounts":
            if source_year is not None and base_year is not None:
                if source_year < base_year:
                    treatment = "carried_forward"
                    derivation = derivation if derivation not in {"", "legacy_unrecorded"} else "prior_observation_seed"
                elif source_year > base_year:
                    treatment = "carried_backward"
                    derivation = derivation if derivation not in {"", "legacy_unrecorded"} else "future_year_seed"
                elif classification == "native_observation":
                    treatment = "native"
                elif derived is None:
                    treatment = "transformed"

        row["Source"] = source
        row["Comment"] = comment
        row["Source Data Year"] = pd.NA if source_year is None else source_year
        row["Source Classification"] = classification
        row["Base Year Treatment"] = treatment or "legacy_unrecorded"
        row["Derivation Method"] = derivation or "legacy_unrecorded"
        enriched_rows.append(row)

    enriched = pd.DataFrame(enriched_rows, columns=df.columns)
    if "Source Data Year" in enriched:
        enriched["Source Data Year"] = pd.to_numeric(enriched["Source Data Year"], errors="coerce").astype("Int64")
    return enriched


def audit_module1_source_quality(
    rows: pd.DataFrame,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Summarise source quality; write only when a caller supplies a path."""
    df = rows.copy()
    for column in PROVENANCE_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA if column == "Source Data Year" else ""
    source = df["Source"].fillna("").astype(str).str.strip()
    comment = df["Comment"].fillna("").astype(str)
    source_year = pd.to_numeric(df["Source Data Year"], errors="coerce")
    classification = df["Source Classification"].fillna("").astype(str).str.strip()
    treatment = df["Base Year Treatment"].fillna("").astype(str).str.strip()
    derivation = df["Derivation Method"].fillna("").astype(str).str.strip()
    derived_generated = ~derivation.isin({"", "legacy_unrecorded"}) & derivation.ne("prior_observation_seed")
    legacy_detail_needed = (
        classification.eq("legacy_unknown")
        | comment.str.contains("original source detail not yet recorded", case=False, regex=False)
    ) & ~derived_generated
    missing_classification = classification.isin({"", "legacy_unknown"})
    complete = (
        source.ne("")
        & source_year.notna()
        & ~missing_classification
        & ~treatment.isin({"", "legacy_unrecorded"})
        & ~derived_generated
    )
    metrics = pd.DataFrame(
        [
            ("total", len(df)),
            ("complete", int(complete.sum())),
            ("legacy_detail_needed", int(legacy_detail_needed.sum())),
            ("derived_generated", int(derived_generated.sum())),
            ("missing_date", int(source_year.isna().sum())),
            ("missing_classification", int(missing_classification.sum())),
        ],
        columns=["metric", "count"],
    )
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        metrics.to_csv(path, index=False)
    return metrics
