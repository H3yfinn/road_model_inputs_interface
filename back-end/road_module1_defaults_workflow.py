#%%
"""
Generate Road model transport provided-values packages.

This workflow writes versioned, per-economy CSV files for the road input data and
provided-values layer. The generated values are placeholders for researcher review.
"""

import os
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from core.road_module1_defaults import (
    DEFAULT_SCENARIOS,
    DEFAULT_VERSION,
    DEFAULT_YEARS,
    MODULE1_KEY_COLUMNS,
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


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def write_frontend_static_bundle(
    output_root: Path,
    static_root: Path,
    version: str,
    scenarios: list[str],
) -> dict[str, int]:
    """Write frontend static JSON defaults + index.json for client-side Road Module 1."""
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
        if "Scenario" not in defaults_df.columns:
            continue

        available_scenarios = {
            str(s).strip()
            for s in defaults_df["Scenario"].dropna().astype(str).tolist()
            if str(s).strip()
        }

        requested_scenarios = [scenario for scenario in scenarios if scenario in available_scenarios]
        if not requested_scenarios:
            requested_scenarios = sorted(available_scenarios)

        fallback_payload = None

        for scenario in requested_scenarios:
            scenario_safe = _sanitize_static_segment(scenario)
            scenario_rows_df = defaults_df[defaults_df["Scenario"].astype(str).eq(scenario)].copy()
            if scenario_rows_df.empty:
                continue

            payload = {
                "key_columns": MODULE1_KEY_COLUMNS,
                "rows": [
                    {key: _json_safe_value(value) for key, value in record.items()}
                    for record in scenario_rows_df.to_dict(orient="records")
                ],
            }

            scenario_path = version_root / f"{economy_safe}_{scenario_safe}.json"
            scenario_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            defaults_files_written += 1

            if scenario == "Reference":
                fallback_payload = payload

        if fallback_payload is None and requested_scenarios:
            first_scenario = requested_scenarios[0]
            first_rows_df = defaults_df[defaults_df["Scenario"].astype(str).eq(first_scenario)].copy()
            if not first_rows_df.empty:
                fallback_payload = {
                    "key_columns": MODULE1_KEY_COLUMNS,
                    "rows": [
                        {key: _json_safe_value(value) for key, value in record.items()}
                        for record in first_rows_df.to_dict(orient="records")
                    ],
                }

        if fallback_payload is not None:
            fallback_path = version_root / f"{economy_safe}.json"
            fallback_path.write_text(json.dumps(fallback_payload, ensure_ascii=False), encoding="utf-8")
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
