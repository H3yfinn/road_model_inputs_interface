#%%
"""Build static Road Module 1 defaults from fixed input files only.

This script is intended for client-side-only deployments (no backend runtime).
It reads processed sources and supplemental source files from
back-end/data/road_model, generates per-economy Road Module 1 workbooks/CSVs,
and writes front-end static JSON bundles.

road_module1_static_contract.csv is the row contract for the static dataset.
It defines every (Branch Path, Variable) pair that may appear in the output,
whether each row is in the Current Accounts scenario, and what units the user
should provide. Edit that CSV to add/remove rows or update units.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pandas as pd

from core.road_module1_defaults import (
    BASE_YEAR,
    DEFAULT_SCENARIOS,
    DEFAULT_VERSION,
    DEFAULT_YEARS,
    FINAL_VALUE_OVERRIDE_COLUMNS,
    FINAL_VALUE_OVERRIDE_DIR,
    MODULE1_LONG_COLUMNS,
    PROJECTED_SALES_SHARE_YEARS,
    PROCESSED_SOURCE_COLUMNS,
    PROCESSED_SOURCE_DIR,
    ROAD_MODEL_DATA_DIR,
    ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH,
    SUPPLEMENTAL_SOURCE_DIR,
    TRANSPORT_LEAP_EXPORT_HEADER_ROW,
    TRANSPORT_LEAP_EXPORT_SHEET,
    _wide_defaults_to_long,
    find_transport_leap_export_path,
    list_default_economies,
    list_default_versions,
    load_default_filled_inputs,
    write_all_economy_packages,
)


# --- Stable paths ---
NOTEBOOK_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = NOTEBOOK_DIR / "outputs" / "road_module1_defaults"
FRONTEND_STATIC_BUNDLE_ROOT = NOTEBOOK_DIR.parent / "front-end" / "road-module1-static"


def _sanitize_static_segment(value: str) -> str:
    """Return a filesystem-safe static bundle path segment."""
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip())


def _coerce_bool_text(value: bool) -> str:
    return "True" if bool(value) else "False"


def _load_projected_sales_share_from_processed_source(economy_code: str) -> pd.DataFrame:
    """Read future Sales Share rows from the processed source CSV."""
    src_path = PROCESSED_SOURCE_DIR / f"road_module1_source_{economy_code}.csv"
    if not src_path.exists():
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)

    df = pd.read_csv(src_path)
    future = df[
        df["Variable"].fillna("").astype(str).str.strip().eq("Sales Share")
        & pd.to_numeric(df["Year"], errors="coerce").isin(PROJECTED_SALES_SHARE_YEARS)
    ].copy()
    if future.empty:
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)

    rows = []
    for _, row in future.iterrows():
        rows.append({
            "Economy": economy_code,
            "Scenario": row.get("Scenario", "Target") or "Target",
            "Branch Path": row.get("Branch Path", ""),
            "Variable": "Sales Share",
            "Year": int(row["Year"]),
            "Value": float(pd.to_numeric(row["Value"], errors="coerce")),
            "Scale": "%",
            "Units": row.get("Units", "Share") or "Share",
            "Source": src_path.name,
            "Comment": "Projected Sales Share from processed source CSV.",
            "Input Status": "default",
            "Shown In Interface": "True",
        })
    if not rows:
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)
    return pd.DataFrame(rows, columns=MODULE1_LONG_COLUMNS)


def _load_projected_sales_share_long_rows(economy_code: str) -> pd.DataFrame:
    """Load 2023-2060 Sales Share rows from the matched transport LEAP workbook.

    Falls back to the processed source CSV when no workbook is available.
    """
    workbook_path = find_transport_leap_export_path(economy=economy_code)
    if workbook_path is None:
        return _load_projected_sales_share_from_processed_source(economy_code)

    raw_df = pd.read_excel(
        workbook_path,
        sheet_name=TRANSPORT_LEAP_EXPORT_SHEET,
        header=TRANSPORT_LEAP_EXPORT_HEADER_ROW,
    )
    required_columns = ["Branch Path", "Variable", "Scenario", "Region", "Scale", "Units"]
    if any(column not in raw_df.columns for column in required_columns):
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)

    sales_df = raw_df[
        raw_df["Variable"].fillna("").astype(str).str.strip().eq("Sales Share")
    ].copy()
    if sales_df.empty:
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)

    # FOR_VIEWING workbooks put 2022-2060 values in unnamed columns immediately
    # after Method. They are not labelled as years in the header row.
    value_columns = [
        column
        for column in sales_df.columns
        if str(column).startswith("Unnamed:")
        and pd.to_numeric(sales_df[column], errors="coerce").notna().any()
    ]
    value_columns = value_columns[: len([BASE_YEAR, *PROJECTED_SALES_SHARE_YEARS])]
    year_by_column = {
        column: year
        for column, year in zip(value_columns, [BASE_YEAR, *PROJECTED_SALES_SHARE_YEARS])
        if year in PROJECTED_SALES_SHARE_YEARS
    }
    if not year_by_column:
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)

    rows: list[dict[str, object]] = []
    source_name = workbook_path.name
    for _, source_row in sales_df.iterrows():
        for value_column, year in year_by_column.items():
            value = pd.to_numeric(source_row.get(value_column), errors="coerce")
            if pd.isna(value):
                continue
            rows.append(
                {
                    "Economy": economy_code,
                    "Scenario": source_row.get("Scenario", "Target") or "Target",
                    "Branch Path": source_row.get("Branch Path", ""),
                    "Variable": "Sales Share",
                    "Year": int(year),
                    "Value": float(value),
                    "Scale": source_row.get("Scale", "%") or "%",
                    "Units": source_row.get("Units", "Share") or "Share",
                    "Source": source_name,
                    "Comment": "Projected Sales Share from matched transport LEAP export workbook.",
                    "Input Status": "default",
                    "Shown In Interface": "True",
                }
            )

    if not rows:
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)
    return pd.DataFrame(rows, columns=MODULE1_LONG_COLUMNS)


def _build_projected_correction_factor_rows(long_defaults_df: pd.DataFrame, economy_code: str) -> pd.DataFrame:
    """Build default 1.0 projected correction-factor rows from fuel-level Module 1 rows."""
    source_rows = long_defaults_df[
        long_defaults_df["Variable"].isin(["Mileage", "Fuel Economy"])
        & long_defaults_df["Branch Path"].astype(str).str.startswith("Demand\\")
    ].copy()
    if source_rows.empty:
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)

    factor_variable_by_source = {
        "Mileage": "Mileage Correction Factor",
        "Fuel Economy": "Fuel Economy Correction Factor",
    }
    rows: list[dict[str, object]] = []
    for _, source_row in source_rows[["Branch Path", "Variable"]].drop_duplicates().iterrows():
        factor_variable = factor_variable_by_source.get(source_row["Variable"])
        if not factor_variable:
            continue
        for year in range(BASE_YEAR + 1, 2061):
            rows.append({
                "Economy": economy_code,
                "Scenario": "Target",
                "Branch Path": source_row["Branch Path"],
                "Variable": factor_variable,
                "Year": int(year),
                "Value": 1.0,
                "Scale": "",
                "Units": "Multiplier",
                "Source": "generated_default_correction_factor",
                "Comment": "Default LEAP correction factor. Set to 1.0 unless a scenario adjustment is needed.",
                "Input Status": "default",
                "Shown In Interface": "True",
            })
    if not rows:
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)
    return pd.DataFrame(rows, columns=MODULE1_LONG_COLUMNS)


ROAD_MODEL_CONFIG_DIR = Path(__file__).resolve().parent / "data" / "road_model" / "config"
STATIC_CONTRACT_CSV_PATH = ROAD_MODEL_CONFIG_DIR / "road_module1_static_contract.csv"
STATIC_CONTRACT_KEY_COLUMNS = ["Branch Path", "Variable"]
STATIC_CONTRACT_REQUIRED_COLUMNS = [*STATIC_CONTRACT_KEY_COLUMNS, "Current Accounts", "Projected Scenario", "Shown In Interface", "Shown In Interface Projected", "Units"]
STATIC_FUEL_BRANCH_EXCLUSIONS_PATH = ROAD_MODEL_CONFIG_DIR / "road_module1_static_fuel_branch_exclusions.csv"
STATIC_FUEL_BRANCH_EXCLUSION_REASON = "0 data for fuel in esto dataset"
STATIC_FUEL_BRANCH_EXCLUSION_COLUMNS = ["Economy", "Branch Path", "Fuel", "Reason"]
STATIC_NO_DISPLAY_ROUND_VARIABLES = {"Survival Rate", "Vintage Profile Share"}


def _contract_bool(value: object, default: bool = True) -> bool:
    if pd.isna(value):
        return default
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return default


def _load_static_contract() -> pd.DataFrame:
    """Load road_module1_static_contract.csv. Returns one row per (Branch Path, Variable)."""
    if not STATIC_CONTRACT_CSV_PATH.exists():
        raise SystemExit(
            f"\nERROR - static row contract not found:\n  {STATIC_CONTRACT_CSV_PATH}"
        )
    contract = pd.read_csv(STATIC_CONTRACT_CSV_PATH)
    missing = [column for column in STATIC_CONTRACT_REQUIRED_COLUMNS if column not in contract.columns]
    if missing:
        raise SystemExit(
            f"\nERROR - {STATIC_CONTRACT_CSV_PATH.name} is missing required columns: "
            f"{', '.join(missing)}"
        )
    contract = contract.copy()
    for column in ["Branch Path", "Variable"]:
        contract[column] = contract[column].fillna("").astype(str).str.strip()
    contract["Current Accounts"] = contract["Current Accounts"].map(
        lambda value: _contract_bool(value, default=True)
    )
    contract["Projected Scenario"] = contract["Projected Scenario"].map(
        lambda value: _contract_bool(value, default=False)
    )
    contract["Shown In Interface"] = contract["Shown In Interface"].map(
        lambda value: _contract_bool(value, default=True)
    )
    contract["Shown In Interface Projected"] = contract["Shown In Interface Projected"].map(
        lambda value: _contract_bool(value, default=True)
    )
    duplicate_mask = contract.duplicated(subset=STATIC_CONTRACT_KEY_COLUMNS, keep=False)
    if duplicate_mask.any():
        duplicates = contract.loc[duplicate_mask, STATIC_CONTRACT_KEY_COLUMNS].head(20)
        raise SystemExit(
            "\nERROR - duplicate row keys in static contract CSV:\n"
            + duplicates.to_string(index=False)
        )
    factor_contract_rows = []
    for source_variable, factor_variable in {
        "Mileage": "Mileage Correction Factor",
        "Fuel Economy": "Fuel Economy Correction Factor",
    }.items():
        for _, row in contract[contract["Variable"].eq(source_variable)].iterrows():
            factor_row = row.copy()
            factor_row["Variable"] = factor_variable
            factor_row["Current Accounts"] = False
            factor_row["Projected Scenario"] = True
            factor_row["Shown In Interface"] = False
            factor_row["Shown In Interface Projected"] = True
            factor_row["Units"] = "Multiplier"
            if "Notes" in factor_row.index:
                factor_row["Notes"] = "Generated default LEAP correction-factor row."
            factor_contract_rows.append(factor_row)
    if factor_contract_rows:
        contract = pd.concat([contract, pd.DataFrame(factor_contract_rows)], ignore_index=True)
        contract = contract.drop_duplicates(subset=STATIC_CONTRACT_KEY_COLUMNS, keep="first")
    return contract


def _load_static_fuel_branch_exclusions() -> pd.DataFrame:
    """Load economy-specific fuel branch exclusions from the static config folder."""
    if not STATIC_FUEL_BRANCH_EXCLUSIONS_PATH.exists():
        return pd.DataFrame(columns=STATIC_FUEL_BRANCH_EXCLUSION_COLUMNS)

    exclusions = pd.read_csv(STATIC_FUEL_BRANCH_EXCLUSIONS_PATH)
    missing = [
        column for column in STATIC_FUEL_BRANCH_EXCLUSION_COLUMNS
        if column not in exclusions.columns
    ]
    if missing:
        raise SystemExit(
            f"\nERROR - {STATIC_FUEL_BRANCH_EXCLUSIONS_PATH.name} is missing required columns: "
            f"{', '.join(missing)}"
        )

    exclusions = exclusions[STATIC_FUEL_BRANCH_EXCLUSION_COLUMNS].copy()
    for column in STATIC_FUEL_BRANCH_EXCLUSION_COLUMNS:
        exclusions[column] = exclusions[column].fillna("").astype(str).str.strip()

    bad_reason = exclusions["Reason"].ne(STATIC_FUEL_BRANCH_EXCLUSION_REASON)
    if bad_reason.any():
        sample = exclusions.loc[bad_reason, STATIC_FUEL_BRANCH_EXCLUSION_COLUMNS].head(20)
        raise SystemExit(
            f"\nERROR - fuel branch exclusions must use reason "
            f"{STATIC_FUEL_BRANCH_EXCLUSION_REASON!r}:\n"
            + sample.to_string(index=False)
        )

    duplicate_mask = exclusions.duplicated(subset=["Economy", "Branch Path"], keep=False)
    if duplicate_mask.any():
        duplicates = exclusions.loc[duplicate_mask, ["Economy", "Branch Path"]].head(20)
        raise SystemExit(
            "\nERROR - duplicate static fuel branch exclusions:\n"
            + duplicates.to_string(index=False)
        )

    return exclusions


def _apply_static_contract(long_df: pd.DataFrame, contract: pd.DataFrame, economy_code: str) -> pd.DataFrame:
    """Apply row visibility from the static contract and fail on uncontracted rows.

    Merges on (Branch Path, Variable) only — Scenario and Year are not part of the
    contract key. CA rows use 'Shown In Interface'; projected rows use
    'Shown In Interface Projected'.
    """
    if long_df.empty:
        return long_df
    df = long_df.copy()
    merged = df.merge(
        contract[["Branch Path", "Variable", "Shown In Interface", "Shown In Interface Projected"]],
        on=["Branch Path", "Variable"],
        how="left",
        indicator=True,
        suffixes=("", "_contract"),
    )
    missing_contract = merged["_merge"].eq("left_only")
    if missing_contract.any():
        sample = merged.loc[missing_contract, ["Branch Path", "Variable"]].drop_duplicates().head(20)
        raise SystemExit(
            f"\nERROR - {economy_code} generated rows that are not in "
            f"{STATIC_CONTRACT_CSV_PATH.name}:\n"
            + sample.to_string(index=False)
        )
    is_ca = merged["Scenario"].eq("Current Accounts")
    ca_visibility = merged["Shown In Interface_contract"]
    projected_visibility = merged["Shown In Interface Projected"]
    merged["Shown In Interface"] = ca_visibility.where(is_ca, projected_visibility).map(_coerce_bool_text)
    merged = merged.drop(columns=["Shown In Interface_contract", "Shown In Interface Projected", "_merge"], errors="ignore")
    return merged[MODULE1_LONG_COLUMNS].copy()


def _filter_to_static_contract(long_df: pd.DataFrame, contract: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows whose (Branch Path, Variable) pair is in the static contract."""
    if long_df.empty:
        return long_df
    contract_keys = contract[STATIC_CONTRACT_KEY_COLUMNS].drop_duplicates()
    filtered = long_df.merge(
        contract_keys,
        on=STATIC_CONTRACT_KEY_COLUMNS,
        how="inner",
    )
    return filtered[MODULE1_LONG_COLUMNS].copy()


def _is_drive_level_sales_share_row(df: pd.DataFrame) -> pd.Series:
    """Rows edited as Ultra-mode sales-share series."""
    branch_depth = df["Branch Path"].fillna("").astype(str).str.count(r"\\")
    return df["Variable"].eq("Sales Share") & branch_depth.ge(3)


def _round_static_display_values(long_df: pd.DataFrame) -> pd.DataFrame:
    """Round values for the frontend static CSV display contract.

    Ultra sales-share rows are rounded to whole percentages. Survival and
    vintage profile rows keep their source precision because coarse rounding
    makes those curves look jagged. Other numeric values are rounded to 2
    decimals so single-value editors stay readable.
    """
    if long_df.empty or "Value" not in long_df.columns:
        return long_df

    rounded = long_df.copy()
    numeric_values = pd.to_numeric(rounded["Value"], errors="coerce")
    no_round_mask = rounded["Variable"].isin(STATIC_NO_DISPLAY_ROUND_VARIABLES)
    list_mask = _is_drive_level_sales_share_row(rounded)
    rounded.loc[numeric_values.notna() & list_mask, "Value"] = numeric_values[list_mask].round(0)
    rounded.loc[numeric_values.notna() & ~list_mask & ~no_round_mask, "Value"] = numeric_values[~list_mask & ~no_round_mask].round(2)
    return rounded[MODULE1_LONG_COLUMNS].copy()


def write_frontend_static_bundle(
    output_root: Path,
    static_root: Path,
    version: str,
) -> dict[str, int | dict]:
    """Write frontend static CSV defaults and index.json."""
    static_root.mkdir(parents=True, exist_ok=True)
    static_contract = _load_static_contract()

    version_root = static_root / _sanitize_static_segment(version)
    shutil.rmtree(version_root, ignore_errors=True)
    version_root.mkdir(parents=True, exist_ok=True)

    economies = list_default_economies(version=version, output_root=output_root)
    defaults_files_written = 0
    economy_row_keys: dict[str, set[tuple[str, str, str]]] = {}

    for economy_item in economies:
        economy_code = economy_item["economy"]
        economy_safe = _sanitize_static_segment(economy_code)
        defaults_df = load_default_filled_inputs(
            economy=economy_code,
            version=version,
            output_root=output_root,
        )
        if "Scenario" in defaults_df.columns:
            defaults_df = defaults_df.copy()
            defaults_df["Scenario"] = "Current Accounts"

        long_defaults_df = _wide_defaults_to_long(defaults_df, economy=economy_code)

        projected_sales_df = _load_projected_sales_share_long_rows(economy_code)
        if not projected_sales_df.empty:
            long_defaults_df = pd.concat([long_defaults_df, projected_sales_df], ignore_index=True)
        correction_factor_df = _build_projected_correction_factor_rows(long_defaults_df, economy_code)
        if not correction_factor_df.empty:
            long_defaults_df = pd.concat([long_defaults_df, correction_factor_df], ignore_index=True)

        long_defaults_df = _filter_to_static_contract(
            long_df=long_defaults_df,
            contract=static_contract,
        )
        long_defaults_df = _apply_static_contract(
            long_df=long_defaults_df,
            contract=static_contract,
            economy_code=economy_code,
        )
        long_defaults_df = _round_static_display_values(long_defaults_df)

        economy_row_keys[economy_code] = set(
            zip(
                long_defaults_df["Scenario"],
                long_defaults_df["Branch Path"],
                long_defaults_df["Variable"],
            )
        )

        csv_path = version_root / f"{economy_safe}.csv"
        long_defaults_df[MODULE1_LONG_COLUMNS].to_csv(csv_path, index=False)
        defaults_files_written += 1

    versions_index = []
    available_versions = [
        v for v in list_default_versions(output_root=output_root)
        if not str(v).startswith("_tmp")
    ]
    for available_version in available_versions:
        versions_index.append(
            {
                "version": available_version,
                "economies": list_default_economies(version=available_version, output_root=output_root),
            }
        )

    index_payload = {
        "default_version": version,
        "versions": versions_index,
    }
    (static_root / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "economies_written": len(economies),
        "defaults_files_written": defaults_files_written,
        "economy_row_keys": economy_row_keys,
    }


REQUIRED_ROAD_MODEL_INPUTS = [
    "apec_phev_utilisation_rates.csv",
    "apec_passenger_vehicle_saturation.csv",
    "apec_reconciliation_factors.csv",
    "apec_vehicle_equivalent_weights.csv",
    "apec_lifecycle_profile_factors.csv",
    "vehicle_survival_modified_00_APEC.xlsx",
    "vintage_modelled_from_survival_00_APEC.xlsx",
]

REQUIRED_CSV_COLUMNS = {
    "apec_phev_utilisation_rates.csv": [
        "project_code",
        "economy",
        "vehicle_type",
        "data_year",
        "phev_utilisation_rate",
        "lower_rate",
        "upper_rate",
        "evidence_grade",
        "estimation_status",
    ],
    "apec_passenger_vehicle_saturation.csv": [
        "project_code",
        "economy",
        "data_year",
        "saturation_vehicles_per_1000",
        "lower_bound",
        "upper_bound",
        "evidence_grade",
        "estimation_status",
        "reached_saturation_lenient",
    ],
    "apec_reconciliation_factors.csv": [
        "transport_type",
        "weight_stock",
        "weight_mileage",
        "weight_efficiency",
        "bound_lower_mileage",
        "bound_upper_mileage",
        "bound_lower_efficiency",
        "bound_upper_efficiency",
        "data_year",
    ],
    "apec_vehicle_equivalent_weights.csv": [
        "vehicle_type",
        "vehicle_equivalent_weight",
        "lower_bound",
        "upper_bound",
        "data_year",
    ],
    "apec_lifecycle_profile_factors.csv": [
        "project_code",
        "economy",
        "transport_type",
        "data_year",
        "turnover_rate_lower",
        "turnover_rate_upper",
        "fit_mode",
        "scale_age_band_age_min",
        "scale_age_band_age_max",
        "smoothing_window",
        "evidence_grade",
        "estimation_status",
    ],
}


def _validate_required_inputs(data_dir: Path) -> list[Path]:
    missing: list[Path] = []
    for filename in REQUIRED_ROAD_MODEL_INPUTS:
        path = SUPPLEMENTAL_SOURCE_DIR / filename
        if not path.exists():
            missing.append(path)

    leap_import_dir = data_dir / "leap_import_workbooks"
    has_leap_workbook = leap_import_dir.exists() and any(leap_import_dir.glob("*.xlsx"))
    if not has_leap_workbook:
        missing.append(leap_import_dir / "<at least one transport_leap_export_combined_*.xlsx>")

    has_processed_source = PROCESSED_SOURCE_DIR.exists() and any(
        PROCESSED_SOURCE_DIR.glob("road_module1_source_*.csv")
    )
    has_default_workbook = ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH.exists()
    if not has_processed_source and not has_default_workbook:
        missing.append(PROCESSED_SOURCE_DIR / "road_module1_source_<ECONOMY>.csv")
        missing.append(ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH)

    return missing


def _validate_input_schemas(data_dir: Path) -> list[str]:
    issues: list[str] = []

    for filename, required_columns in REQUIRED_CSV_COLUMNS.items():
        path = SUPPLEMENTAL_SOURCE_DIR / filename
        if not path.exists():
            continue
        try:
            columns = pd.read_csv(path, nrows=0).columns.tolist()
        except Exception as exc:  # pragma: no cover - defensive guard for malformed files
            issues.append(f"{filename}: could not read CSV header ({exc})")
            continue

        missing_columns = [column for column in required_columns if column not in columns]
        if missing_columns:
            issues.append(
                f"{filename}: missing required columns: {', '.join(missing_columns)}"
            )

    if PROCESSED_SOURCE_DIR.exists():
        for path in PROCESSED_SOURCE_DIR.glob("road_module1_source_*.csv"):
            try:
                columns = pd.read_csv(path, nrows=0).columns.tolist()
            except Exception as exc:  # pragma: no cover - defensive guard for malformed files
                issues.append(f"{path.name}: could not read CSV header ({exc})")
                continue
            missing_columns = [column for column in PROCESSED_SOURCE_COLUMNS if column not in columns]
            if missing_columns:
                issues.append(
                    f"{path.name}: missing required columns: {', '.join(missing_columns)}"
                )

    if FINAL_VALUE_OVERRIDE_DIR.exists():
        override_paths = [
            *FINAL_VALUE_OVERRIDE_DIR.glob("module1_final_value_override*.csv"),
            *FINAL_VALUE_OVERRIDE_DIR.glob("module1_final_value_override*.xlsx"),
            *FINAL_VALUE_OVERRIDE_DIR.glob("module1_final_value_override*.xls"),
        ]
        for path in sorted(set(override_paths)):
            try:
                if path.suffix.lower() == ".csv":
                    columns = pd.read_csv(path, nrows=0).columns.tolist()
                else:
                    columns = pd.read_excel(path, nrows=0).columns.tolist()
            except Exception as exc:  # pragma: no cover - defensive guard for malformed files
                issues.append(f"{path.name}: could not read override header ({exc})")
                continue
            missing_columns = [column for column in FINAL_VALUE_OVERRIDE_COLUMNS if column not in columns]
            if missing_columns:
                issues.append(
                    f"{path.name}: missing required columns: {', '.join(missing_columns)}"
                )

    return issues




def _validate_static_contract_output(
    economy_row_keys: dict[str, set[tuple[str, str, str]]],
) -> None:
    """Validate generated static rows against road_module1_static_contract.csv.

    Three checks per economy:
    1. No (Branch Path, Variable) in the output that isn't in the contract.
    2. Every contract row with Current Accounts=True must appear in the CA scenario output.
    3. Every contract row with Projected Scenario=True must appear in every non-CA scenario output.

    All contract rows are required unconditionally. Previously, fuel-level branches with zero ESTO
    data were exempted via road_module1_static_fuel_branch_exclusions.csv. That file is now retired:
    all such branches must be populated (e.g. via manually_filled_rows) before the build passes.
    """
    if not economy_row_keys:
        return

    contract = _load_static_contract()

    # All valid (Branch Path, Variable) pairs in the contract
    contract_bp_var: frozenset[tuple[str, str]] = frozenset(
        zip(contract["Branch Path"], contract["Variable"])
    )
    # Pairs required in the Current Accounts scenario
    ca_required: frozenset[tuple[str, str]] = frozenset(
        zip(
            contract.loc[contract["Current Accounts"], "Branch Path"],
            contract.loc[contract["Current Accounts"], "Variable"],
        )
    )
    # Pairs required in non-CA (Target and other projected) scenarios
    target_required: frozenset[tuple[str, str]] = frozenset(
        zip(
            contract.loc[contract["Projected Scenario"], "Branch Path"],
            contract.loc[contract["Projected Scenario"], "Variable"],
        )
    )

    failures: list[str] = []

    for economy_code, generated_keys in sorted(economy_row_keys.items()):
        ca_generated = {(bp, var) for scen, bp, var in generated_keys if scen == "Current Accounts"}
        target_generated = {(bp, var) for scen, bp, var in generated_keys if scen != "Current Accounts"}
        all_generated = {(bp, var) for _, bp, var in generated_keys}

        # Check 1: no uncontracted (Branch Path, Variable) pairs
        uncontracted = all_generated - contract_bp_var
        if uncontracted:
            sample = sorted(uncontracted)[:20]
            failures.append(
                f"  {economy_code}: generated rows absent from {STATIC_CONTRACT_CSV_PATH.name}:\n"
                + "\n".join(f"    {key!r}" for key in sample)
            )

        # Check 2: required CA rows present (no exclusion exemptions)
        missing_ca = ca_required - ca_generated
        if missing_ca:
            sample = sorted(missing_ca)[:20]
            failures.append(
                f"  {economy_code}: missing required Current Accounts rows:\n"
                + "\n".join(f"    {key!r}" for key in sample)
                + "\n    (Add missing Mileage/Fuel Economy rows to manually_filled_rows/ to fix.)"
            )

        # Check 3: required Target rows present (no exclusion exemptions)
        missing_target = target_required - target_generated
        if missing_target:
            sample = sorted(missing_target)[:20]
            failures.append(
                f"  {economy_code}: missing required projected scenario rows:\n"
                + "\n".join(f"    {key!r}" for key in sample)
                + "\n    (Add missing rows to manually_filled_rows/ to fix.)"
            )

    if failures:
        raise SystemExit(
            f"\nERROR - static bundle rows do not match {STATIC_CONTRACT_CSV_PATH.name}:\n"
            + "\n".join(failures)
            + f"\n\nUpdate {STATIC_CONTRACT_CSV_PATH.name} if the generated static dataset changed intentionally."
        )

    print(f"Static contract check passed: generated rows match {STATIC_CONTRACT_CSV_PATH.name}.")


def main() -> None:
    data_dir = ROAD_MODEL_DATA_DIR
    missing = _validate_required_inputs(data_dir)
    if missing:
        print("Missing required Road Module 1 input files:")
        for path in missing:
            print(f"  - {path}")
        raise SystemExit(1)

    schema_issues = _validate_input_schemas(data_dir)
    if schema_issues:
        print("Road Module 1 input schema validation failed:")
        for issue in schema_issues:
            print(f"  - {issue}")
        raise SystemExit(1)

    generated = write_all_economy_packages(
        output_root=OUTPUT_ROOT,
        scenarios=list(DEFAULT_SCENARIOS),
        years=list(DEFAULT_YEARS),
        require_default_input_workbook=False,
        enforce_source_backed_values=True,
    )

    static_summary = write_frontend_static_bundle(
        output_root=OUTPUT_ROOT,
        static_root=FRONTEND_STATIC_BUNDLE_ROOT,
        version=DEFAULT_VERSION,
    )

    print(f"Generated defaults for {len(generated)} economies.")
    print(f"Output root: {OUTPUT_ROOT}")
    print(f"Static bundle root: {FRONTEND_STATIC_BUNDLE_ROOT}")
    print(f"Defaults JSON files written: {static_summary.get('defaults_files_written', 0)}")

    _validate_static_contract_output(
        static_summary.get("economy_row_keys", {}),
    )


if __name__ == "__main__":
    main()
#%%
