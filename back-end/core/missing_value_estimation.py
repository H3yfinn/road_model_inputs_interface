"""Cross-validated, review-only estimation of missing Module 1 operating values.

The functions in this module are deliberately pure with respect to repository
data: callers supply canonical static rows and receive proposals, evidence and
cross-validation results.  Nothing is promoted or applied automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd


STRICTLY_POSITIVE_VARIABLES = frozenset({"Mileage", "Fuel Economy"})
DEFAULT_MIN_PEER_ECONOMIES = 5
DEFAULT_MIN_ADJUSTMENT_ROWS = 3
KEY_COLUMNS = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]
REQUIRED_COLUMNS = [*KEY_COLUMNS, "Value", "Scale", "Units"]
PROPOSAL_COLUMNS = [
    *KEY_COLUMNS,
    "Existing Value",
    "Proposed Value",
    "Scale",
    "Units",
    "Source",
    "Strategy",
    "Estimation Method",
    "Evidence Count",
    "Peer Economy Count",
    "Peer Median",
    "Economy Adjustment Factor",
    "Cross Validation Median APE",
    "Cross Validation P90 APE",
    "Source Data Year",
    "Source Classification",
    "Base Year Treatment",
    "Derivation Method",
    "Review Status",
    "Comment",
    "Proposal ID",
]
REVIEW_COLUMNS = [
    "Proposal ID",
    "Economy",
    "Branch Path",
    "Variable",
    "Year",
    "Existing Value",
    "Proposed Value",
    "Scale",
    "Units",
    "Estimation Method",
    "Evidence Count",
    "Cross Validation Median APE",
    "Source Data Year",
    "Review Status",
    "Comment",
    "Reviewer Decision",
    "Reviewer Note",
]
EVIDENCE_COLUMNS = [
    "Proposal ID",
    "Role",
    "Evidence Economy",
    "Evidence Branch Path",
    "Evidence Value",
    "Evidence Ratio",
]
CV_COLUMNS = [
    "Economy",
    "Branch Path",
    "Variable",
    "Actual Value",
    "Method",
    "Estimated Value",
    "Absolute Percentage Error",
]
CV_SUMMARY_COLUMNS = ["Variable", "Method", "Prediction Count", "Median APE", "Mean APE", "P90 APE"]


@dataclass(frozen=True)
class EstimationResult:
    proposals: pd.DataFrame
    evidence: pd.DataFrame
    cross_validation: pd.DataFrame
    cross_validation_summary: pd.DataFrame
    selected_strategies: Mapping[str, str]


def _integer_year(value: object, field_name: str = "Year") -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer year, not a boolean.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer year, got {value!r}.") from exc
    if not math.isfinite(numeric) or not numeric.is_integer() or not 1900 <= numeric <= 2100:
        raise ValueError(f"{field_name} must be an integer year from 1900 to 2100, got {value!r}.")
    return int(numeric)


def _branch_parts(branch_path: object) -> dict[str, str]:
    text = str(branch_path or "").strip()
    parts = text.split("\\")
    if len(parts) != 5 or parts[0] != "Demand":
        raise ValueError(f"Expected a five-level Demand fuel branch, got {text!r}.")
    drive_size = parts[3]
    size = ""
    for candidate in ("small", "medium", "large", "heavy", "light"):
        if candidate in drive_size.lower().split():
            size = candidate
            break
    return {
        "transport": parts[1],
        "vehicle": parts[2],
        "drive_size": drive_size,
        "fuel": parts[4],
        "size": size,
    }


def normalise_estimation_pool(
    rows: pd.DataFrame | Iterable[Mapping[str, Any]],
    *,
    base_year: int,
) -> pd.DataFrame:
    """Validate and select one Current Accounts base-year estimation pool."""
    year = _integer_year(base_year, "base_year")
    frame = rows.copy(deep=True) if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Estimation pool is missing required columns: {missing_columns}.")
    selected = frame[
        frame["Scenario"].astype(str).str.strip().eq("Current Accounts")
        & frame["Variable"].astype(str).str.strip().isin(STRICTLY_POSITIVE_VARIABLES)
    ].copy()
    if selected.empty:
        raise ValueError("Estimation pool contains no Current Accounts Mileage or Fuel Economy rows.")
    parsed_years = selected["Year"].map(_integer_year)
    selected = selected.loc[parsed_years.eq(year)].copy()
    selected["Year"] = year
    if selected.empty:
        raise ValueError(f"Estimation pool contains no eligible rows for base year {year}.")
    for column in ["Economy", "Scenario", "Branch Path", "Variable", "Scale", "Units"]:
        selected[column] = selected[column].fillna("").astype(str).str.strip()
    values = pd.to_numeric(selected["Value"], errors="coerce")
    invalid_numeric = values.isna() | ~values.map(math.isfinite)
    if invalid_numeric.any():
        sample = selected.loc[invalid_numeric, KEY_COLUMNS + ["Value"]].head(5).to_dict("records")
        raise ValueError(f"Estimation pool contains non-finite values. Sample: {sample}")
    selected["Value"] = values.astype(float)
    duplicate = selected.duplicated(KEY_COLUMNS, keep=False)
    if duplicate.any():
        sample = selected.loc[duplicate, KEY_COLUMNS].head(5).to_dict("records")
        raise ValueError(f"Estimation pool contains duplicate canonical keys. Sample: {sample}")
    economies = selected["Economy"].str.fullmatch(r"\d{2}[A-Z]{2,3}")
    if not economies.all():
        raise ValueError("Estimation pool Economy values must use compact canonical codes such as 20USA.")
    internal_columns = ["transport", "vehicle", "drive_size", "fuel", "size", "_row_id"]
    selected = selected.drop(columns=[column for column in internal_columns if column in selected.columns])
    parts = selected["Branch Path"].map(_branch_parts).apply(pd.Series)
    selected = pd.concat([selected.reset_index(drop=True), parts.reset_index(drop=True)], axis=1)
    selected["_row_id"] = range(len(selected))
    return selected


def load_static_estimation_pool(static_dir: str | Path, *, base_year: int) -> tuple[pd.DataFrame, list[Path]]:
    """Load canonical economy CSVs from one explicit static-version directory."""
    root = Path(static_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"Static version directory does not exist: {root}")
    paths = sorted(root.glob("*.csv"))
    if not paths:
        raise ValueError(f"Static version directory contains no economy CSVs: {root}")
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path, low_memory=False)
        if "Economy" not in frame.columns:
            raise ValueError(f"Static CSV is missing Economy: {path}")
        found = sorted(frame["Economy"].dropna().astype(str).str.strip().unique())
        if found != [path.stem]:
            raise ValueError(f"Static CSV {path.name} must contain only economy {path.stem!r}; found {found}.")
        frames.append(frame)
    return normalise_estimation_pool(pd.concat(frames, ignore_index=True), base_year=base_year), paths


def _median(records: list[dict[str, Any]]) -> float | None:
    values = sorted(float(record["Value"]) for record in records if float(record["Value"]) > 0)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def _deduplicate(records: list[dict[str, Any]], columns: tuple[str, ...]) -> list[dict[str, Any]]:
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in records:
        found.setdefault(tuple(record[column] for column in columns), record)
    return list(found.values())


def _proposal_id(row: Mapping[str, Any]) -> str:
    identity = "\u241f".join(str(row[column]) for column in KEY_COLUMNS)
    return "missing_value_proxy:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


class _Estimator:
    def __init__(self, pool: pd.DataFrame, min_peer_economies: int, min_adjustment_rows: int):
        self.pool = pool
        self.known = pool[pool["Value"].gt(0)].copy()
        self.min_peer_economies = min_peer_economies
        self.min_adjustment_rows = min_adjustment_rows
        self.by_branch: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.by_drive: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
        self.by_size: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
        for record in self.known.to_dict("records"):
            self.by_branch.setdefault((record["Variable"], record["Branch Path"]), []).append(record)
            self.by_drive.setdefault((
                record["Economy"], record["Variable"], record["transport"],
                record["vehicle"], record["drive_size"],
            ), []).append(record)
            self.by_size.setdefault((
                record["Economy"], record["Variable"], record["transport"],
                record["vehicle"], record["size"],
            ), []).append(record)
        self.peer_ratio_groups = self._build_peer_ratio_groups()

    def peer_records(self, row: Mapping[str, Any]) -> list[dict[str, Any]]:
        records = [
            record for record in self.by_branch.get((row["Variable"], row["Branch Path"]), [])
            if record["Economy"] != row["Economy"] and record["Value"] > 0
        ]
        return _deduplicate(records, ("Economy",))

    def drive_records(self, row: Mapping[str, Any]) -> list[dict[str, Any]]:
        records = self.by_drive.get((
            row["Economy"], row["Variable"], row["transport"], row["vehicle"], row["drive_size"],
        ), [])
        return _deduplicate(
            [record for record in records if record["Branch Path"] != row["Branch Path"]],
            ("Branch Path",),
        )

    def size_records(self, row: Mapping[str, Any]) -> list[dict[str, Any]]:
        records = self.by_size.get((
            row["Economy"], row["Variable"], row["transport"], row["vehicle"], row["size"],
        ), [])
        return _deduplicate(
            [record for record in records if record["Branch Path"] != row["Branch Path"]],
            ("Branch Path",),
        )

    def _build_peer_ratio_groups(self) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
        groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for record in self.known.to_dict("records"):
            peers = self.peer_records(record)
            peer_median = _median(peers)
            if peer_median is None or len(peers) < self.min_peer_economies:
                continue
            groups.setdefault((
                record["Economy"], record["transport"], record["vehicle"], record["size"],
            ), []).append({
                **record,
                "Ratio": float(record["Value"]) / peer_median,
            })
        return groups

    def adjustment_records(self, row: Mapping[str, Any]) -> list[dict[str, Any]]:
        records = self.peer_ratio_groups.get((
            row["Economy"], row["transport"], row["vehicle"], row["size"],
        ), [])
        return [record for record in records if record["_row_id"] != row.get("_row_id")]

    def estimate_peer(self, row: Mapping[str, Any]) -> tuple[float | None, list[dict[str, Any]]]:
        records = self.peer_records(row)
        if len(records) < self.min_peer_economies:
            return None, records
        return _median(records), records

    def estimate_mileage_hierarchy(
        self, row: Mapping[str, Any]
    ) -> tuple[float | None, str, list[dict[str, Any]], float | None]:
        drive = self.drive_records(row)
        value = _median(drive)
        if value is not None:
            return value, "same_economy_exact_drive_median", drive, None
        size = self.size_records(row)
        value = _median(size)
        if value is not None:
            return value, "same_economy_vehicle_size_median", size, None
        value, peers = self.estimate_peer(row)
        return value, "exact_branch_peer_median", peers, value

    def estimate_adjusted_fuel_economy(
        self, row: Mapping[str, Any]
    ) -> tuple[float | None, list[dict[str, Any]], list[dict[str, Any]], float, float | None]:
        peer_value, peers = self.estimate_peer(row)
        if peer_value is None:
            return None, peers, [], 1.0, None
        adjustments = self.adjustment_records(row)
        ratios = sorted(float(record["Ratio"]) for record in adjustments if float(record["Ratio"]) > 0)
        if len(ratios) < self.min_adjustment_rows:
            return peer_value, peers, adjustments, 1.0, peer_value
        middle = len(ratios) // 2
        factor = ratios[middle] if len(ratios) % 2 else (ratios[middle - 1] + ratios[middle]) / 2
        return peer_value * factor, peers, adjustments, factor, peer_value


def _summarise_cross_validation(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(columns=CV_SUMMARY_COLUMNS)
    summaries: list[dict[str, Any]] = []
    for (variable, method), group in rows.groupby(["Variable", "Method"], sort=True):
        errors = group["Absolute Percentage Error"].astype(float)
        summaries.append({
            "Variable": variable,
            "Method": method,
            "Prediction Count": len(group),
            "Median APE": float(errors.median()),
            "Mean APE": float(errors.mean()),
            "P90 APE": float(errors.quantile(0.9)),
        })
    return pd.DataFrame(summaries, columns=CV_SUMMARY_COLUMNS)


def _select_strategies(summary: pd.DataFrame) -> dict[str, str]:
    selected: dict[str, str] = {}
    choices = {
        "Mileage": ("exact_branch_peer_median", "mileage_hierarchy"),
        "Fuel Economy": ("exact_branch_peer_median", "economy_adjusted_peer_median"),
    }
    for variable, methods in choices.items():
        available = summary[summary["Variable"].eq(variable)].set_index("Method")
        ranked = [method for method in methods if method in available.index]
        if not ranked:
            raise ValueError(f"Cross-validation produced no eligible strategy for {variable}.")
        selected[variable] = min(
            ranked,
            key=lambda method: (
                float(available.loc[method, "Median APE"]),
                float(available.loc[method, "P90 APE"]),
                methods.index(method),
            ),
        )
    return selected


def estimate_missing_values(
    rows: pd.DataFrame | Iterable[Mapping[str, Any]],
    *,
    base_year: int,
    min_peer_economies: int = DEFAULT_MIN_PEER_ECONOMIES,
    min_adjustment_rows: int = DEFAULT_MIN_ADJUSTMENT_ROWS,
) -> EstimationResult:
    """Cross-validate methods and propose values for every non-positive row."""
    if min_peer_economies < 2:
        raise ValueError("min_peer_economies must be at least 2.")
    if min_adjustment_rows < 1:
        raise ValueError("min_adjustment_rows must be at least 1.")
    pool = normalise_estimation_pool(rows, base_year=base_year)
    estimator = _Estimator(pool, min_peer_economies, min_adjustment_rows)
    cv_rows: list[dict[str, Any]] = []
    for row in estimator.known.to_dict("records"):
        actual = float(row["Value"])
        peer, _ = estimator.estimate_peer(row)
        estimates: list[tuple[str, float | None]] = [("exact_branch_peer_median", peer)]
        if row["Variable"] == "Mileage":
            hierarchy, _, _, _ = estimator.estimate_mileage_hierarchy(row)
            estimates.append(("mileage_hierarchy", hierarchy))
        else:
            adjusted, _, _, _, _ = estimator.estimate_adjusted_fuel_economy(row)
            estimates.append(("economy_adjusted_peer_median", adjusted))
        for method, estimate in estimates:
            if estimate is None or estimate <= 0:
                continue
            cv_rows.append({
                "Economy": row["Economy"],
                "Branch Path": row["Branch Path"],
                "Variable": row["Variable"],
                "Actual Value": actual,
                "Method": method,
                "Estimated Value": estimate,
                "Absolute Percentage Error": abs(estimate - actual) / actual,
            })
    cross_validation = pd.DataFrame(cv_rows, columns=CV_COLUMNS)
    summary = _summarise_cross_validation(cross_validation)
    selected = _select_strategies(summary)

    summary_lookup = {
        (row["Variable"], row["Method"]): row
        for row in summary.to_dict("records")
    }
    proposals: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    invalid = pool[pool["Value"].le(0)].sort_values(KEY_COLUMNS, kind="stable")
    for row in invalid.to_dict("records"):
        proposal_id = _proposal_id(row)
        strategy = selected[row["Variable"]]
        peer_value, peer_records = estimator.estimate_peer(row)
        adjustment = 1.0
        adjustment_records: list[dict[str, Any]] = []
        if strategy == "mileage_hierarchy":
            value, method, method_records, method_peer = estimator.estimate_mileage_hierarchy(row)
            peer_value = method_peer if method_peer is not None else peer_value
        elif strategy == "economy_adjusted_peer_median":
            value, method_records, adjustment_records, adjustment, peer_value = (
                estimator.estimate_adjusted_fuel_economy(row)
            )
            method = (
                "economy_adjusted_exact_branch_peer_median"
                if adjustment != 1.0 else "exact_branch_peer_median"
            )
        else:
            value, method_records = peer_value, peer_records
            method = "exact_branch_peer_median"
        if value is None or not math.isfinite(value) or value <= 0:
            raise ValueError(f"No positive estimate is available for canonical key {tuple(row[c] for c in KEY_COLUMNS)!r}.")
        cv = summary_lookup[(row["Variable"], strategy)]
        peer_economies = len({record["Economy"] for record in peer_records})
        comment = (
            f"Estimated {base_year} {row['Variable']} using {method.replace('_', ' ')}. "
            f"Estimate inputs: {len(method_records)} value(s). "
            f"Exact-branch comparison: {peer_economies} peer economies. "
            f"Cross-validation median absolute percentage error for the selected strategy: "
            f"{float(cv['Median APE']):.1%}. Replace when better economy-specific evidence becomes available."
        )
        proposals.append({
            **{column: row[column] for column in KEY_COLUMNS},
            "Existing Value": float(row["Value"]),
            "Proposed Value": float(value),
            "Scale": row["Scale"],
            "Units": row["Units"],
            "Source": "Cross-validated Module 1 missing-value estimate",
            "Strategy": strategy,
            "Estimation Method": method,
            "Evidence Count": len(method_records),
            "Peer Economy Count": peer_economies,
            "Peer Median": peer_value,
            "Economy Adjustment Factor": adjustment,
            "Cross Validation Median APE": float(cv["Median APE"]),
            "Cross Validation P90 APE": float(cv["P90 APE"]),
            "Source Data Year": base_year,
            "Source Classification": "model_assumption",
            "Base Year Treatment": "transformed",
            "Derivation Method": method,
            "Review Status": "proposed_model_derived_proxy",
            "Comment": comment,
            "Proposal ID": proposal_id,
        })
        for record in method_records:
            evidence_rows.append({
                "Proposal ID": proposal_id,
                "Role": "estimate_input",
                "Evidence Economy": record["Economy"],
                "Evidence Branch Path": record["Branch Path"],
                "Evidence Value": record["Value"],
                "Evidence Ratio": "",
            })
        method_evidence_keys = {
            (record["Economy"], record["Branch Path"], record["Value"])
            for record in method_records
        }
        for record in peer_records:
            evidence_key = (record["Economy"], record["Branch Path"], record["Value"])
            if evidence_key in method_evidence_keys:
                continue
            evidence_rows.append({
                "Proposal ID": proposal_id,
                "Role": "exact_branch_peer_context",
                "Evidence Economy": record["Economy"],
                "Evidence Branch Path": record["Branch Path"],
                "Evidence Value": record["Value"],
                "Evidence Ratio": "",
            })
        for record in adjustment_records:
            evidence_rows.append({
                "Proposal ID": proposal_id,
                "Role": "economy_adjustment_ratio",
                "Evidence Economy": record["Economy"],
                "Evidence Branch Path": record["Branch Path"],
                "Evidence Value": record["Value"],
                "Evidence Ratio": record["Ratio"],
            })

    proposal_frame = pd.DataFrame(proposals, columns=PROPOSAL_COLUMNS)
    evidence_frame = pd.DataFrame(evidence_rows, columns=EVIDENCE_COLUMNS)
    if proposal_frame.empty:
        raise ValueError("Estimation pool contains no non-positive Mileage or Fuel Economy values to estimate.")
    if proposal_frame.duplicated(KEY_COLUMNS).any():
        raise AssertionError("Generated proposals contain duplicate canonical keys.")
    return EstimationResult(proposal_frame, evidence_frame, cross_validation, summary, selected)


def apply_estimation_proposals(
    canonical_rows: pd.DataFrame,
    proposals: pd.DataFrame,
) -> pd.DataFrame:
    """Return a staged copy with exact invalid keys replaced; never mutate inputs."""
    missing = [column for column in [*KEY_COLUMNS, "Proposed Value"] if column not in proposals.columns]
    if missing:
        raise ValueError(f"Proposal rows are missing required columns: {missing}.")
    validated_proposals = proposals.copy(deep=True)
    validated_proposals["Year"] = validated_proposals["Year"].map(
        lambda value: _integer_year(value, "Proposal Year")
    )
    if validated_proposals.duplicated(KEY_COLUMNS).any():
        raise ValueError("Proposal rows contain duplicate canonical keys.")
    result = canonical_rows.copy(deep=True)
    result["Year"] = result["Year"].map(_integer_year)
    proposal_map = {
        tuple(row[column] for column in KEY_COLUMNS): row
        for row in validated_proposals.to_dict("records")
    }
    applied: set[tuple[Any, ...]] = set()
    for index, row in result.iterrows():
        key = tuple(row[column] for column in KEY_COLUMNS)
        proposal = proposal_map.get(key)
        if proposal is None:
            continue
        existing = float(row["Value"])
        proposed = float(proposal["Proposed Value"])
        if existing > 0 or not math.isfinite(proposed) or proposed <= 0:
            raise ValueError(f"Proposal may replace only a non-positive value with a positive finite value: {key!r}.")
        result.at[index, "Value"] = proposed
        for column in [
            "Source", "Source Data Year", "Source Classification",
            "Base Year Treatment", "Derivation Method", "Comment",
        ]:
            if column in result.columns and column in proposal:
                result.at[index, column] = proposal[column]
        applied.add(key)
    missing_keys = set(proposal_map) - applied
    if missing_keys:
        raise ValueError(f"Proposal keys are absent from the canonical package. Sample: {sorted(missing_keys)[:5]}")
    return result
