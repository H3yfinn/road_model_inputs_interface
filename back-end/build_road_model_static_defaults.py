#%%
"""Build static Road Module 1 defaults from fixed input files only.

This script is intended for client-side-only deployments (no backend runtime).
It reads processed sources and supplemental source files from
back-end/data/road_model, generates per-economy Road Module 1 workbooks/CSVs,
and writes front-end static JSON bundles.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

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
    )

    print(f"Generated defaults for {len(generated)} economies.")
    print(f"Output root: {OUTPUT_ROOT}")
    print(f"Static bundle root: {FRONTEND_STATIC_BUNDLE_ROOT}")
    print(f"Defaults JSON files written: {static_summary.get('defaults_files_written', 0)}")


if __name__ == "__main__":
    main()
#%%
