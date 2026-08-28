"""Generate one staged Module 1 review package without promoting it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.base_year_candidate_extraction import generate_checked_in_source_review_package
from core.road_module1_provenance import CURRENT_SOURCE_PACKAGE_VERSION
from core.supplemental_provenance_inventory import build_supplemental_provenance_inventory


def _unused_output_dir(output_dir: str | Path) -> Path:
    destination = Path(output_dir).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(
            f"Review output directory must be new or empty so existing artifacts are not overwritten: {destination}"
        )
    return destination


def generate_staged_review(
    *,
    economy: str,
    base_year: int,
    output_dir: str | Path,
    package_version: str,
    source_package_version: str = CURRENT_SOURCE_PACKAGE_VERSION,
    fallback_csv: str | Path | None = None,
) -> dict[str, object]:
    """Generate review artifacts and return a compact operator summary."""
    destination = _unused_output_dir(output_dir)
    package_paths = generate_checked_in_source_review_package(
        economy=economy,
        requested_base_year=base_year,
        source_package_version=source_package_version,
        package_version=package_version,
        output_dir=destination,
        fallback_csv=fallback_csv,
    )
    supplemental_path = destination / "supplemental_provenance_inventory.csv"
    supplemental = build_supplemental_provenance_inventory(output_path=supplemental_path)
    manifest = json.loads(package_paths["manifest_json"].read_text(encoding="utf-8"))
    resolution = manifest["resolution"]
    return {
        "mode": "staging_only_no_promotion",
        "economy": economy,
        "base_year": base_year,
        "output_dir": str(destination),
        "package_version": package_version,
        "source_package_version": source_package_version,
        "resolution_summary": resolution["summary_counts"],
        "candidate_extraction_summary": resolution["candidate_extraction"],
        "supplemental_summary": supplemental.summary,
        "artifacts": {
            **{name: str(path) for name, path in package_paths.items()},
            "supplemental_inventory_csv": str(supplemental_path),
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a staged Module 1 base-year review package and supplemental provenance audit. "
            "This command never promotes outputs or updates the static package index."
        )
    )
    parser.add_argument("--economy", required=True, help="Compact economy code, for example 20USA.")
    parser.add_argument("--base-year", required=True, type=int, help="Requested model base year.")
    parser.add_argument("--output-dir", required=True, help="New or empty caller-owned staging directory.")
    parser.add_argument("--package-version", required=True, help="Review-only package identity.")
    parser.add_argument(
        "--source-package-version",
        default=CURRENT_SOURCE_PACKAGE_VERSION,
        help=f"Checked-in source/static package version (default: {CURRENT_SOURCE_PACKAGE_VERSION}).",
    )
    parser.add_argument(
        "--fallback-csv",
        default=None,
        help="Optional explicit canonical fallback CSV; defaults to the checked-in static economy CSV.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = generate_staged_review(
            economy=args.economy,
            base_year=args.base_year,
            output_dir=args.output_dir,
            package_version=args.package_version,
            source_package_version=args.source_package_version,
            fallback_csv=args.fallback_csv,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Review package generation failed: {exc}", file=sys.stderr)
        return 2
    print("Staged Module 1 review package generated; no promotion or index update was performed.")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
