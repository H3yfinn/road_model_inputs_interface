#%%
"""
One-button Road Module 1 data refresh workflow.

Use this from Jupyter/VS Code interactive after changing source data under
back-end/data/road_model/. For routine edits in manually_filled_rows/,
supplemental_source_files/, final_value_overrides/, or config/, leave
RUN_PREPARE_SOURCE_FROM_LEAP_EXPORT = False and run the file.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


# --- Stable paths ---
BACKEND_DIR = Path(__file__).resolve().parent
REPO_DIR = BACKEND_DIR.parent
ROAD_MODEL_DATA_DIR = BACKEND_DIR / "data" / "road_model"
LEAP_EXPORT_WORKBOOK_DIR = ROAD_MODEL_DATA_DIR / "leap_import_workbooks"
PROCESSED_SOURCE_DIR = ROAD_MODEL_DATA_DIR / "processed_source"
OUTPUT_ROOT = BACKEND_DIR / "outputs" / "road_module1_defaults"
STATIC_BUNDLE_ROOT = REPO_DIR / "front-end" / "road-module1-static"


if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import build_road_model_static_defaults as static_builder


def load_prepare_road_source_module():
    """Load scripts/prepare_road_source.py without requiring package imports."""
    script_path = BACKEND_DIR / "scripts" / "prepare_road_source.py"
    spec = importlib.util.spec_from_file_location("prepare_road_source_script", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load source-prep script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_latest_leap_export_workbook(workbook_dir: Path = LEAP_EXPORT_WORKBOOK_DIR) -> Path:
    """Return the newest LEAP export workbook by modified time."""
    workbooks = sorted(
        workbook_dir.glob("*.xlsx"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not workbooks:
        raise FileNotFoundError(f"No .xlsx files found in {workbook_dir}")
    return workbooks[0]


def print_path(label: str, path: Path) -> None:
    """Print a stable Windows path for operator review."""
    print(f"{label}: {path.resolve()}")


def run_source_prep_from_leap_export(export_path: Path | list[Path] | None = None) -> list[Path]:
    """Regenerate processed_source/ from an upstream LEAP export workbook."""
    prepare_module = load_prepare_road_source_module()
    selected_export_path = export_path
    if selected_export_path is None and hasattr(prepare_module, "find_latest_all_economies_exports"):
        selected_export_path = prepare_module.find_latest_all_economies_exports()
    if selected_export_path is None:
        selected_export_path = get_latest_leap_export_workbook()
    print("\n--- Source prep ---")
    if isinstance(selected_export_path, list):
        for path in selected_export_path:
            print_path("LEAP export workbook", path)
    else:
        print_path("LEAP export workbook", selected_export_path)
    written_files = prepare_module.prepare_road_source(
        export_path=selected_export_path,
        output_dir=PROCESSED_SOURCE_DIR,
    )
    print(f"Wrote {len(written_files)} processed source CSV files.")
    for path in written_files[:10]:
        print(f"  - {path}")
    if len(written_files) > 10:
        print(f"  ... {len(written_files) - 10} more")
    return written_files


def run_static_build() -> None:
    """Generate backend defaults and frontend static CSV bundle."""
    print("\n--- Static build ---")
    static_builder.main()


def get_static_index_summary() -> None:
    """Print the current frontend static bundle index summary."""
    index_path = STATIC_BUNDLE_ROOT / "index.json"
    print("\n--- Static bundle summary ---")
    if not index_path.exists():
        print_path("Missing index.json", index_path)
        return

    import json

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    default_version = payload.get("default_version")
    versions = payload.get("versions", [])
    default_entry = next(
        (item for item in versions if item.get("version") == default_version),
        {},
    )
    economies = default_entry.get("economies", [])
    print(f"Default version: {default_version}")
    print(f"Economies in default version: {len(economies)}")
    print_path("Static index", index_path)
    if default_version:
        print_path("Static version folder", STATIC_BUNDLE_ROOT / str(default_version))


def print_git_status() -> None:
    """Print changed files so the HF Space upload/commit scope is visible."""
    print("\n--- Git status ---")
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        print(f"Could not run git status: {exc}")
        return
    status_text = result.stdout.strip()
    if status_text:
        print(status_text)
    else:
        print("No local changes detected.")


def run_data_refresh_workflow(
    *,
    run_prepare_source_from_leap_export: bool,
    leap_export_workbook_path: Path | None,
    run_build: bool,
    show_static_summary: bool,
    show_git_status: bool,
) -> None:
    """Run the selected Road Module 1 refresh steps in the correct order."""
    os.chdir(REPO_DIR)
    print_path("Repository", REPO_DIR)
    print_path("Road model data", ROAD_MODEL_DATA_DIR)

    if run_prepare_source_from_leap_export:
        run_source_prep_from_leap_export(export_path=leap_export_workbook_path)
    else:
        print("\n--- Source prep ---")
        print("Skipped. This is correct for routine manually_filled_rows/ edits.")

    if run_build:
        run_static_build()
    else:
        print("\n--- Static build ---")
        print("Skipped by RUN_BUILD = False.")

    if show_static_summary:
        get_static_index_summary()

    if show_git_status:
        print_git_status()


# --- Frequently changed toggles ---
# Set this True only when leap_import_workbooks/ has been replaced or updated.
RUN_PREPARE_SOURCE_FROM_LEAP_EXPORT = False

# Leave as None to use the newest .xlsx in leap_import_workbooks/.
LEAP_EXPORT_WORKBOOK_PATH = None

# Keep True for nearly every data update. This generates:
# - back-end/outputs/road_module1_defaults/
# - front-end/road-module1-static/
RUN_BUILD = True

SHOW_STATIC_SUMMARY = True
SHOW_GIT_STATUS = True


# --- Run block ---
if __name__ == "__main__":
    try:
        run_data_refresh_workflow(
            run_prepare_source_from_leap_export=RUN_PREPARE_SOURCE_FROM_LEAP_EXPORT,
            leap_export_workbook_path=LEAP_EXPORT_WORKBOOK_PATH,
            run_build=RUN_BUILD,
            show_static_summary=SHOW_STATIC_SUMMARY,
            show_git_status=SHOW_GIT_STATUS,
        )
    except Exception as exc:
        print("\nWorkflow failed.")
        print(f"{type(exc).__name__}: {exc}")
        raise

#%%
