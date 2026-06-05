"""
Audit guard for Road Module 1 data sourcing policy.

Policy:
- Runtime code must not hard-code road input datasets.
- Operational data must come from back-end/data/road_model CSV/XLSX sources.

Exit code:
- 0: pass
- 1: fail (violations found)
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "back-end" / "data" / "road_model"
SUPPLEMENTAL_SOURCE_DIR = DATA_DIR / "supplemental_source_files"
FRONTEND_APP = REPO_ROOT / "front-end" / "app.js"

REQUIRED_DATA_FILES = [
    "apec_reconciliation_factors.csv",
    "apec_phev_utilisation_rates.csv",
    "apec_vehicle_equivalent_weights.csv",
    "apec_passenger_vehicle_saturation.csv",
    "apec_lifecycle_profile_factors.csv",
    "vehicle_survival_modified_00_APEC.xlsx",
    "vintage_modelled_from_survival_00_APEC.xlsx",
]

# Keep this list intentionally narrow and high-signal.
# These markers indicate model-data literals that should not be reintroduced.
FORBIDDEN_APP_TOKENS = [
    "const module6DefaultByRole",
    "ROAD_MODULE1_FALLBACK_ECONOMIES",
    "ROAD_MODULE1_FALLBACK_VERSION",
]


def main() -> int:
    violations: list[str] = []

    if not DATA_DIR.exists():
        violations.append(f"Missing data directory: {DATA_DIR}")
    else:
        if not SUPPLEMENTAL_SOURCE_DIR.exists():
            violations.append(f"Missing supplemental source directory: {SUPPLEMENTAL_SOURCE_DIR}")
        for filename in REQUIRED_DATA_FILES:
            path = SUPPLEMENTAL_SOURCE_DIR / filename
            if not path.exists():
                violations.append(f"Missing required data source file: {path}")

        processed_source_dir = DATA_DIR / "processed_source"
        has_processed_source = processed_source_dir.exists() and any(
            processed_source_dir.glob("road_module1_source_*.csv")
        )
        default_workbook = DATA_DIR / "road_model_default_input_workbook.xlsx"
        if not has_processed_source and not default_workbook.exists():
            violations.append(
                "Missing Road Module 1 primary source: expected processed_source/"
                "road_module1_source_*.csv or road_model_default_input_workbook.xlsx"
            )

        source_files = []
        if SUPPLEMENTAL_SOURCE_DIR.exists():
            source_files = [
                p for p in SUPPLEMENTAL_SOURCE_DIR.iterdir()
                if p.is_file() and p.suffix.lower() in {".csv", ".xlsx", ".xls"}
            ]
        if not source_files:
            violations.append(
                "No CSV/XLSX/XLS source files found in "
                "back-end/data/road_model/supplemental_source_files."
            )

    if not FRONTEND_APP.exists():
        violations.append(f"Missing front-end app file: {FRONTEND_APP}")
    else:
        app_text = FRONTEND_APP.read_text(encoding="utf-8")
        for token in FORBIDDEN_APP_TOKENS:
            if token in app_text:
                violations.append(
                    f"Forbidden hard-coded runtime data marker found in front-end/app.js: {token}"
                )

    if violations:
        print("Road model data sourcing audit FAILED:\n")
        for issue in violations:
            print(f"- {issue}")
        return 1

    print("Road model data sourcing audit PASSED.")
    print(f"- Data directory: {DATA_DIR}")
    print(f"- Supplemental source directory: {SUPPLEMENTAL_SOURCE_DIR}")
    print(f"- Checked required source files: {len(REQUIRED_DATA_FILES)}")
    print("- Checked Module 1 processed-source/default-workbook availability")
    print("- No forbidden hard-coded runtime data markers found in front-end/app.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
