#%%
"""Build static Road Module 1 defaults from fixed input files only.

This script is intended for client-side-only deployments (no backend runtime).
It reads source files from back-end/data/road_model, generates per-economy
Road Module 1 workbooks/CSVs, and writes front-end static JSON bundles.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.road_module1_defaults import (
    DEFAULT_SCENARIOS,
    DEFAULT_VERSION,
    DEFAULT_YEARS,
    ROAD_MODEL_DATA_DIR,
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
    "road_module1_default_vehicle_types.csv",
    "road_module1_default_drive_shares.csv",
    "road_module1_valid_drives_by_vehicle_type.csv",
    "road_module1_default_mileage_km_per_year.csv",
    "road_module1_default_efficiency_mj_per_km.csv",
    "road_module1_default_assumptions.csv",
    "vehicle_survival_modified_00_APEC.xlsx",
    "vintage_modelled_from_survival_00_APEC.xlsx",
]

REQUIRED_CSV_COLUMNS = {
    "apec_phev_utilisation_rates.csv": [
        "project_code",
        "economy",
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
        "reconciliation_bound_lower",
        "reconciliation_bound_upper",
        "reconciliation_weight",
        "data_year",
    ],
    "apec_vehicle_equivalent_weights.csv": [
        "vehicle_type",
        "vehicle_equivalent_weight",
        "lower_bound",
        "upper_bound",
        "data_year",
    ],
    "road_module1_default_vehicle_types.csv": [
        "transport_type",
        "vehicle_type",
        "vehicle_equivalent_weight",
        "stock_share",
    ],
    "road_module1_default_drive_shares.csv": [
        "vehicle_type",
        "drive",
        "share",
    ],
    "road_module1_valid_drives_by_vehicle_type.csv": [
        "vehicle_type",
        "drive",
    ],
    "road_module1_default_mileage_km_per_year.csv": [
        "vehicle_type",
        "mileage_km_per_year",
    ],
    "road_module1_default_efficiency_mj_per_km.csv": [
        "drive",
        "efficiency_mj_per_km",
    ],
    "road_module1_default_assumptions.csv": [
        "key",
        "value",
    ],
}


def _validate_required_inputs(data_dir: Path) -> list[Path]:
    missing: list[Path] = []
    for filename in REQUIRED_ROAD_MODEL_INPUTS:
        path = data_dir / filename
        if not path.exists():
            missing.append(path)

    leap_import_dir = data_dir / "leap_import_workbooks"
    has_leap_workbook = leap_import_dir.exists() and any(leap_import_dir.glob("*.xlsx"))
    if not has_leap_workbook:
        missing.append(leap_import_dir / "<at least one transport_leap_export_combined_*.xlsx>")

    return missing


def _validate_input_schemas(data_dir: Path) -> list[str]:
    issues: list[str] = []

    for filename, required_columns in REQUIRED_CSV_COLUMNS.items():
        path = data_dir / filename
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
        require_default_input_workbook=True,
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
