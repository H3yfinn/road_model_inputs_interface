#%%
"""Build static Road Module 1 defaults from fixed input files only.

This script is intended for client-side-only deployments (no backend runtime).
It reads processed sources and supplemental source files from
back-end/data/road_model, generates per-economy Road Module 1 workbooks/CSVs,
and writes front-end static JSON bundles.

FRONTEND_MEASURES is the authoritative contract for what rows appear in the
frontend output.  Every entry specifies:
  - variable:     the canonical Variable name
  - source:       where values come from
  - branch_level: what kind of branch the row lives at (documentation only;
                  the actual branch logic is in the overlay functions)

The contract drives two things:
  1. Filtering: rows whose Variable is not in FRONTEND_ALLOWED_VARIABLES are
     dropped from every economy CSV before it is written to the static bundle.
  2. Validation: after generation, any required variable that is entirely
     absent from an economy's output triggers a warning.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Required rows manifest
# ---------------------------------------------------------------------------
# road_module1_required_rows.csv defines every (Branch Path, Variable) pair
# that must appear in every economy's frontend output CSV.
#
# It covers the fixed structure: transport, vehicle-type, age, and drive levels.
# It deliberately excludes Mileage and Fuel Economy because those appear at the
# fuel level and vary by economy (different fuel mixes in the LEAP export).
# Those are validated separately by _validate_fuel_level_completeness().
#
# To update the spec: edit road_module1_required_rows.csv directly.
# branch_level is a comment column only; validation uses Branch Path + Variable.

REQUIRED_ROWS_MANIFEST_PATH = Path(__file__).resolve().parent / "data" / "road_model" / "road_module1_required_rows.csv"

# Variables where completeness is checked row-by-row against the manifest.
FIXED_REQUIRED_VARS = frozenset({
    "Sales Share", "Stock Share",
    "PHEV Electric Driving Share",
    "Passenger Vehicle Saturation", "Passenger Saturation Reached",
    "Reconciliation Weight Stock", "Reconciliation Weight Mileage", "Reconciliation Weight Efficiency",
    "Reconciliation Bound Lower Mileage", "Reconciliation Bound Upper Mileage",
    "Reconciliation Bound Lower Efficiency", "Reconciliation Bound Upper Efficiency",
    "Vehicle Equivalent Weight", "Vehicle Equivalent Weight Lower Bound", "Vehicle Equivalent Weight Upper Bound",
    "Survival Rate", "Vintage Profile Share",
})

# Variables where completeness is checked by rule (every fuel-level branch must
# have both), because fuel mix differs across economies.
FUEL_LEVEL_VARS = frozenset({"Mileage", "Fuel Economy"})

from core.road_module1_defaults import (
    DEFAULT_SCENARIOS,
    DEFAULT_VERSION,
    DEFAULT_YEARS,
    FINAL_VALUE_OVERRIDE_COLUMNS,
    FINAL_VALUE_OVERRIDE_DIR,
    PROCESSED_SOURCE_COLUMNS,
    PROCESSED_SOURCE_DIR,
    ROAD_MODEL_DATA_DIR,
    ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH,
    SUPPLEMENTAL_SOURCE_DIR,
    write_all_economy_packages,
)
from road_module1_defaults_workflow import (
    FRONTEND_STATIC_BUNDLE_ROOT,
    OUTPUT_ROOT,
    write_frontend_static_bundle,
)


# ---------------------------------------------------------------------------
# Frontend output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FrontendMeasureSpec:
    variable: str
    source: str        # which supplemental/LEAP source provides values
    branch_level: str  # descriptive: "transport", "vehicle_type", "phev_parent",
                       #              "drive_or_deeper", "age", "any"
    required: bool = True


# Each entry is one measure that MUST (required=True) or MAY (required=False)
# appear in the frontend output CSV.  Add/remove rows here to change what users
# see in the interface.
FRONTEND_MEASURES: list[FrontendMeasureSpec] = [
    # --- From the LEAP export processed source ---
    FrontendMeasureSpec("Stock",             "leap_export",                "vehicle_type",    required=False),
    FrontendMeasureSpec("Mileage",           "leap_export",                "drive_or_deeper", required=True),
    FrontendMeasureSpec("Fuel Economy",      "leap_export",                "drive_or_deeper", required=True),
    FrontendMeasureSpec("Sales Share",       "leap_export",                "vehicle_type",    required=True),
    FrontendMeasureSpec("Stock Share",       "leap_export",                "vehicle_type",    required=True),

    # --- From supplemental source files (must be created if absent in LEAP export) ---
    FrontendMeasureSpec("PHEV Electric Driving Share",         "phev_utilisation",         "phev_parent",   required=True),
    FrontendMeasureSpec("Passenger Vehicle Saturation",        "passenger_saturation",     "transport",     required=True),
    FrontendMeasureSpec("Passenger Saturation Reached",        "passenger_saturation",     "transport",     required=True),
    FrontendMeasureSpec("Reconciliation Weight Stock",         "reconciliation_factors",   "transport",     required=True),
    FrontendMeasureSpec("Reconciliation Weight Mileage",       "reconciliation_factors",   "transport",     required=True),
    FrontendMeasureSpec("Reconciliation Weight Efficiency",    "reconciliation_factors",   "transport",     required=True),
    FrontendMeasureSpec("Reconciliation Bound Lower Mileage",  "reconciliation_factors",   "transport",     required=True),
    FrontendMeasureSpec("Reconciliation Bound Upper Mileage",  "reconciliation_factors",   "transport",     required=True),
    FrontendMeasureSpec("Reconciliation Bound Lower Efficiency","reconciliation_factors",  "transport",     required=True),
    FrontendMeasureSpec("Reconciliation Bound Upper Efficiency","reconciliation_factors",  "transport",     required=True),
    FrontendMeasureSpec("Vehicle Equivalent Weight",           "vehicle_equivalent_weights","vehicle_type", required=True),
    FrontendMeasureSpec("Vehicle Equivalent Weight Lower Bound","vehicle_equivalent_weights","vehicle_type",required=True),
    FrontendMeasureSpec("Vehicle Equivalent Weight Upper Bound","vehicle_equivalent_weights","vehicle_type",required=True),
    FrontendMeasureSpec("Survival Rate",                       "survival_profile",         "age",           required=True),
    FrontendMeasureSpec("Vintage Profile Share",               "vintage_profile",          "age",           required=True),
]

# Derived set: the only Variable values allowed in a frontend output CSV.
FRONTEND_ALLOWED_VARIABLES: frozenset[str] = frozenset(m.variable for m in FRONTEND_MEASURES)

# Required subset: variables that must be present for every economy output.
FRONTEND_REQUIRED_VARIABLES: frozenset[str] = frozenset(
    m.variable for m in FRONTEND_MEASURES if m.required
)


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


def _load_required_rows_manifest() -> pd.DataFrame:
    """Load the required rows manifest CSV.  Raises clearly if the file is missing."""
    if not REQUIRED_ROWS_MANIFEST_PATH.exists():
        raise SystemExit(
            f"\nERROR — required rows manifest not found:\n  {REQUIRED_ROWS_MANIFEST_PATH}\n\n"
            "This file defines what (Branch Path, Variable) pairs must appear in every "
            "economy's frontend output CSV.  It should be committed to the repository.\n"
            "To regenerate it from a correct output, run the regeneration helper in "
            "build_road_model_static_defaults.py."
        )
    return pd.read_csv(REQUIRED_ROWS_MANIFEST_PATH)


def _validate_output_completeness(economy_row_pairs: dict[str, set[tuple[str, str]]]) -> None:
    """Raise if any required (Branch Path, Variable) pair is missing from any economy's output.

    Two separate checks are run:
    1. Fixed structure (manifest): every (Branch Path, Variable) in
       road_module1_required_rows.csv must be present.
    2. Fuel level (rule): every fuel-level branch present in the output must
       have both Mileage and Fuel Economy — because fuel mix is economy-specific.
    """
    if not economy_row_pairs:
        return

    manifest = _load_required_rows_manifest()
    required_pairs = frozenset(zip(manifest["Branch Path"], manifest["Variable"]))

    failures: list[str] = []

    for economy_code, pairs_present in sorted(economy_row_pairs.items()):
        # --- Check 1: fixed manifest ---
        missing_fixed = required_pairs - pairs_present
        if missing_fixed:
            for bp, var in sorted(missing_fixed):
                failures.append(f"  {economy_code}: missing ({bp!r}, {var!r})")

        # --- Check 2: fuel-level rule ---
        # Find every fuel-level branch (depth 5) that has at least one fuel-level variable.
        fuel_branches = {
            bp for bp, var in pairs_present
            if len(bp.split("\\")) == 5 and var in FUEL_LEVEL_VARS
        }
        for bp in sorted(fuel_branches):
            for var in FUEL_LEVEL_VARS:
                if (bp, var) not in pairs_present:
                    failures.append(f"  {economy_code}: fuel branch missing {var!r}: {bp!r}")

    if failures:
        block = "\n".join(failures)
        raise SystemExit(
            f"\nERROR — required rows missing from output CSV(s):\n{block}\n\n"
            "Fixed-structure rows must match road_module1_required_rows.csv.\n"
            "Fuel-level branches must each have both Mileage and Fuel Economy.\n"
            "Check supplemental source files and overlay functions in road_module1_defaults.py."
        )

    print("Completeness check passed: all required rows present in every economy output.")


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
        scenarios=list(DEFAULT_SCENARIOS),
        allowed_variables=FRONTEND_ALLOWED_VARIABLES,
    )

    print(f"Generated defaults for {len(generated)} economies.")
    print(f"Output root: {OUTPUT_ROOT}")
    print(f"Static bundle root: {FRONTEND_STATIC_BUNDLE_ROOT}")
    print(f"Defaults JSON files written: {static_summary.get('defaults_files_written', 0)}")

    _validate_output_completeness(static_summary.get("economy_row_pairs", {}))


if __name__ == "__main__":
    main()
#%%
