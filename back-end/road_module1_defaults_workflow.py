#%%
"""
Generate Road model transport provided-values packages.

This workflow writes versioned, per-economy CSV files for the road input data and
provided-values layer. The generated values are placeholders for researcher review.
"""

import json
import os
import re
import shutil
from pathlib import Path

import pandas as pd

from core.road_module1_defaults import (
    DEFAULT_SCENARIOS,
    DEFAULT_VERSION,
    DEFAULT_YEARS,
    MODULE1_LONG_COLUMNS,
    MODULE1_LONG_KEY_COLUMNS,
    MODULE1_KEY_COLUMNS,
    _wide_defaults_to_long,
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
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip())



def write_frontend_static_bundle(
    output_root: Path,
    static_root: Path,
    version: str,
    scenarios: list[str],
) -> dict[str, int]:
    """Write frontend static CSV defaults + index.json for client-side Road Module 1.

    Each economy is written as a long-format CSV with columns:
      Economy, Scenario, Branch Path, Variable, Year, Value, Units, Source, Comment

    This is the same format used for 'download filled CSV' and 'upload filled CSV',
    so the static bundle, the download, and the upload all share one schema.
    """
    static_root.mkdir(parents=True, exist_ok=True)

    version_root = static_root / _sanitize_static_segment(version)
    shutil.rmtree(version_root, ignore_errors=True)
    version_root.mkdir(parents=True, exist_ok=True)

    economies = list_default_economies(version=version, output_root=output_root)
    defaults_files_written = 0

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
    (static_root / "index.json").write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "economies_written": len(economies),
        "defaults_files_written": defaults_files_written,
    }


# --- Functions ---
def generate_module1_default_packages(
    output_root: Path,
    scenarios: list[str],
    years: list[int],
) -> dict:
    """Create the provided-values package for every APEC economy."""
    os.chdir(NOTEBOOK_DIR)
    return write_all_economy_packages(
        output_root=output_root,
        scenarios=scenarios,
        years=years,
    )


def print_generation_summary(generated_paths: dict) -> None:
    """Print a concise summary for notebook runs."""
    economy_count = len(generated_paths)
    first_economy = next(iter(generated_paths))
    first_paths = generated_paths[first_economy]

    print(f"Generated Road model provided-values version: {DEFAULT_VERSION}")
    print(f"Economies written: {economy_count}")
    print(f"Output root: {OUTPUT_ROOT}")
    print("Example files:")
    for file_type, path in first_paths.items():
        print(f"  - {file_type}: {path}")


def print_static_bundle_summary(summary: dict[str, int]) -> None:
    print("Frontend static bundle updated:")
    print(f"  - static root: {FRONTEND_STATIC_BUNDLE_ROOT}")
    print(f"  - economies written: {summary.get('economies_written', 0)}")
    print(f"  - defaults JSON files written: {summary.get('defaults_files_written', 0)}")


# --- Frequently changed toggles ---
GENERATE_ALL_ECONOMY_DEFAULTS = True
SCENARIOS_TO_WRITE = list(DEFAULT_SCENARIOS)
YEARS_TO_WRITE = list(DEFAULT_YEARS)
WRITE_FRONTEND_STATIC_BUNDLE = True


# --- Run blocks ---
if __name__ == "__main__":
    if GENERATE_ALL_ECONOMY_DEFAULTS:
        GENERATED_PATHS = generate_module1_default_packages(
            output_root=OUTPUT_ROOT,
            scenarios=SCENARIOS_TO_WRITE,
            years=YEARS_TO_WRITE,
        )
        print_generation_summary(GENERATED_PATHS)

        if WRITE_FRONTEND_STATIC_BUNDLE:
            STATIC_BUNDLE_SUMMARY = write_frontend_static_bundle(
                output_root=OUTPUT_ROOT,
                static_root=FRONTEND_STATIC_BUNDLE_ROOT,
                version=DEFAULT_VERSION,
                scenarios=SCENARIOS_TO_WRITE,
            )
            print_static_bundle_summary(STATIC_BUNDLE_SUMMARY)

#%%
