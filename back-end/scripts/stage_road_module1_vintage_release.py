#%%
"""Build every registered ESTO-vintage package in caller-owned staging roots.

This command is deliberately separate from the normal static-default builder.
It never writes repository defaults or frontend static files, never accesses
Drive, and has no deployment or promotion operation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Sequence

import pandas as pd


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
MODEL_REPO_ROOT = Path(
    os.getenv("LEAP_ROAD_MODEL_DIR") or str(REPO_ROOT.parent / "leap_road_model")
).resolve()
PROTECTED_ROOTS = (
    REPO_ROOT / "back-end" / "data",
    REPO_ROOT / "back-end" / "outputs",
    REPO_ROOT / "front-end" / "road-module1-static",
    MODEL_REPO_ROOT / "input_data" / "module1_defaults",
    MODEL_REPO_ROOT / "results",
)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import build_road_model_static_defaults as static_builder
from core.base_year_candidate_extraction import generate_checked_in_source_review_package
from core.base_year_package_generation import CANONICAL_LONG_COLUMNS
from core.esto_vintage_registry import build_available_vintage_index, load_esto_vintage_registry
from core.road_module1_defaults import (
    DEFAULT_SCENARIOS,
    DEFAULT_YEARS,
    get_economy_info,
    validate_module1_value_for_variable,
)
from core.road_module1_provenance import CURRENT_SOURCE_PACKAGE_VERSION


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_destinations(output_root: str | Path, static_root: str | Path) -> tuple[Path, Path]:
    output = Path(output_root).resolve()
    static = Path(static_root).resolve()
    if output == static or _is_within(output, static) or _is_within(static, output):
        raise ValueError("Backend and static staging roots must be separate, non-nested directories.")
    for destination in (output, static):
        for protected in PROTECTED_ROOTS:
            if _is_within(destination, protected.resolve()):
                raise ValueError(f"Staged releases cannot be written under protected path {protected}.")
        if destination.exists():
            raise ValueError(f"Staging destination must not already exist: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
    return output, static


def _temporary_sibling(destination: Path, label: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f".{destination.name}.{label}.", dir=destination.parent)).resolve()


def _build_source_fallback_bundle(work_root: Path) -> Path:
    missing = static_builder._validate_required_inputs(static_builder.ROAD_MODEL_DATA_DIR)
    if missing:
        raise ValueError("Missing required Road Module 1 inputs: " + ", ".join(str(path) for path in missing))
    schema_issues = static_builder._validate_input_schemas(static_builder.ROAD_MODEL_DATA_DIR)
    if schema_issues:
        raise ValueError("Road Module 1 input schema validation failed: " + "; ".join(schema_issues))

    backend_root = work_root / "source_backend"
    static_root = work_root / "source_static"
    static_builder.write_all_economy_packages(
        output_root=backend_root,
        version=CURRENT_SOURCE_PACKAGE_VERSION,
        scenarios=list(DEFAULT_SCENARIOS),
        years=list(DEFAULT_YEARS),
        require_default_input_workbook=False,
        enforce_source_backed_values=True,
    )
    summary = static_builder.write_frontend_static_bundle(
        output_root=backend_root,
        static_root=static_root,
        version=CURRENT_SOURCE_PACKAGE_VERSION,
    )
    static_builder._validate_static_contract_output(summary.get("economy_row_keys", {}))
    return static_root / CURRENT_SOURCE_PACKAGE_VERSION


def _validate_complete_package(path: Path, economy: str, base_year: int) -> tuple[int, int]:
    rows = pd.read_csv(path)
    if list(rows.columns) != CANONICAL_LONG_COLUMNS:
        raise ValueError(f"Complete package columns are not canonical for {economy}.")
    if sorted(rows["Economy"].astype(str).unique()) != [economy]:
        raise ValueError(f"Complete package contains the wrong economy for {economy}.")
    keys = ["Economy", "Scenario", "Branch Path", "Variable", "Year"]
    if rows.duplicated(keys).any():
        raise ValueError(f"Complete package contains duplicate canonical keys for {economy}.")
    years = pd.to_numeric(rows["Year"], errors="coerce")
    if years.isna().any() or (~years.map(lambda value: float(value).is_integer())).any():
        raise ValueError(f"Complete package contains a missing or fractional year for {economy}.")
    current_accounts = rows[rows["Scenario"].eq("Current Accounts")]
    if current_accounts.empty or set(years.loc[current_accounts.index].astype(int)) != {base_year}:
        raise ValueError(f"Current Accounts rows do not match base year {base_year} for {economy}.")
    projections = rows[rows["Scenario"].isin(["Reference", "Target"])]
    if not projections.empty and (years.loc[projections.index] <= base_year).any():
        raise ValueError(f"Projection rows overlap base year {base_year} for {economy}.")
    invalid = []
    for row_number, row in rows.iterrows():
        message = validate_module1_value_for_variable(row["Variable"], row["Value"])
        if message:
            invalid.append(f"row {row_number + 2}: {message}")
            if len(invalid) == 5:
                break
    if invalid:
        raise ValueError(f"Complete package contains invalid values for {economy}: {'; '.join(invalid)}")
    return len(rows), len(current_accounts)


def _write_static_index(static_root: Path, records: list[Any], economies: list[str]) -> Path:
    versions = []
    for record in records:
        versions.append({
            "version": record.package_version,
            "esto_vintage": record.esto_vintage,
            "base_year": record.base_year,
            "is_preliminary": record.is_preliminary,
            "economies": [
                {
                    "economy": economy,
                    "economy_name": get_economy_info(economy).name,
                    "base_year": record.base_year,
                }
                for economy in economies
            ],
        })
    available_versions = {record.package_version for record in records}
    available_vintages, default_vintage = build_available_vintage_index(records, available_versions)
    default_version = next(record.package_version for record in records if record.is_default)
    payload = {
        "default_version": default_version,
        "configured_scenarios": static_builder._load_configured_scenario_labels(),
        "default_esto_vintage": default_vintage,
        "esto_vintages": available_vintages,
        "versions": versions,
    }
    path = static_root / "index.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def stage_vintage_release(*, output_root: str | Path, static_root: str | Path) -> dict[str, Any]:
    """Build and atomically expose a complete local staging release."""
    output, static = _validate_destinations(output_root, static_root)
    output_work = _temporary_sibling(output, "building")
    static_work = _temporary_sibling(static, "building")
    output_published = False
    try:
        records = load_esto_vintage_registry()
        with tempfile.TemporaryDirectory(prefix="road_module1_source_fallback_") as source_temp:
            source_dir = _build_source_fallback_bundle(Path(source_temp))
            economies = sorted(path.stem for path in source_dir.glob("*.csv"))
            if not economies:
                raise ValueError("Generated source fallback bundle contains no economy CSVs.")

            version_summaries = []
            for record in records:
                economy_summaries = []
                for economy in economies:
                    economy_output = output_work / record.package_version / economy
                    review_output = economy_output / "resolution_review"
                    paths = generate_checked_in_source_review_package(
                        economy=economy,
                        requested_base_year=record.base_year,
                        source_package_version=CURRENT_SOURCE_PACKAGE_VERSION,
                        package_version=record.package_version,
                        output_dir=review_output,
                        fallback_csv=source_dir / f"{economy}.csv",
                    )
                    complete_path = paths["complete_package_csv"]
                    row_count, current_accounts_row_count = _validate_complete_package(
                        complete_path, economy, record.base_year
                    )
                    backend_csv = economy_output / f"road_module1_values_{economy}.csv"
                    backend_csv.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(complete_path, backend_csv)
                    static_csv = static_work / record.package_version / f"{economy}.csv"
                    static_csv.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(complete_path, static_csv)
                    checksum = _sha256(complete_path)
                    if _sha256(backend_csv) != checksum or _sha256(static_csv) != checksum:
                        raise RuntimeError(f"Staged copies do not match the resolved package for {economy}.")
                    economy_summaries.append({
                        "economy": economy,
                        "row_count": row_count,
                        "current_accounts_row_count": current_accounts_row_count,
                        "package_sha256": checksum,
                        "resolution_manifest": str(
                            Path(record.package_version) / economy / "resolution_review" / paths["manifest_json"].name
                        ),
                        "resolution_manifest_sha256": _sha256(paths["manifest_json"]),
                    })
                version_manifest = {
                    "package_version": record.package_version,
                    "esto_vintage": record.esto_vintage,
                    "base_year": record.base_year,
                    "is_preliminary": record.is_preliminary,
                    "is_default": record.is_default,
                    "source_package_version": CURRENT_SOURCE_PACKAGE_VERSION,
                    "economy_count": len(economy_summaries),
                    "economies": economy_summaries,
                }
                version_manifest_path = output_work / record.package_version / "road_module1_manifest.json"
                version_manifest_path.write_text(
                    json.dumps(version_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                version_summaries.append({
                    **{key: version_manifest[key] for key in (
                        "package_version", "esto_vintage", "base_year", "is_preliminary",
                        "is_default", "economy_count",
                    )},
                    "manifest_sha256": _sha256(version_manifest_path),
                })

        index_path = _write_static_index(static_work, records, economies)
        release_manifest = {
            "mode": "local_staging_only_no_deployment",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_package_version": CURRENT_SOURCE_PACKAGE_VERSION,
            "output_root": str(output),
            "static_root": str(static),
            "index_sha256": _sha256(index_path),
            "version_count": len(version_summaries),
            "economy_count_per_version": len(economies),
            "versions": version_summaries,
        }
        (output_work / "staging_release_manifest.json").write_text(
            json.dumps(release_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        os.replace(output_work, output)
        output_published = True
        try:
            os.replace(static_work, static)
        except Exception:
            os.replace(output, output_work)
            output_published = False
            raise
        return release_manifest
    finally:
        if not output_published and output_work.exists():
            shutil.rmtree(output_work)
        if static_work.exists():
            shutil.rmtree(static_work)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, help="New backend-package staging directory.")
    parser.add_argument("--static-root", required=True, help="New frontend-static staging directory.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = stage_vintage_release(output_root=args.output_root, static_root=args.static_root)
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Staged vintage release failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("All registered vintages were staged locally; nothing was deployed or promoted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
