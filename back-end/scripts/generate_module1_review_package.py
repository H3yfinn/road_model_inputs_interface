"""Generate staged Module 1 review packages without promoting them."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
STATIC_BUNDLE_ROOT = REPO_ROOT / "front-end" / "road-module1-static"
REVIEW_FAILURES = (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError)
PROTECTED_OUTPUT_ROOTS = (
    REPO_ROOT / "back-end" / "data",
    REPO_ROOT / "back-end" / "outputs" / "road_module1_defaults",
    STATIC_BUNDLE_ROOT,
)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.base_year_candidate_extraction import (
    build_static_package_conflict_report,
    generate_checked_in_source_review_package,
    summarise_static_package_conflicts,
)
from core.researcher_submission_review import write_reviewer_csv
from core.road_module1_provenance import CURRENT_SOURCE_PACKAGE_VERSION
from core.supplemental_provenance_inventory import build_supplemental_provenance_inventory


def _unused_output_dir(output_dir: str | Path) -> Path:
    destination = Path(output_dir).resolve()
    for root in PROTECTED_OUTPUT_ROOTS:
        try:
            destination.relative_to(root.resolve())
        except ValueError:
            continue
        raise ValueError(f"Review artifacts cannot be written under protected path {root}.")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(
            f"Review output directory must be new or empty so existing artifacts are not overwritten: {destination}"
        )
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _write_summary(destination: Path, summary: dict[str, object]) -> Path:
    path = destination / "review_run_summary.json"
    summary.setdefault("artifacts", {})["run_summary_json"] = str(path)
    path.write_text(json.dumps(_json_ready(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _review_researcher_submissions(
    *,
    destination: Path,
    include_researcher_submissions: bool,
    researcher_submissions_folder_id: str | None,
) -> dict[str, object]:
    if not include_researcher_submissions:
        return {"included": False, "message": "Researcher-submission review was not requested."}
    from scripts.review_researcher_submission_batch import review_new_archived_submissions

    review = review_new_archived_submissions(
        output_dir=destination / "researcher_submission_review",
        static_bundle_dir=STATIC_BUNDLE_ROOT,
        drive_folder_id=researcher_submissions_folder_id,
    )
    return {
        "included": True,
        "message": review["message"],
        "reviewed_submission_count": review["reviewed_submission_count"],
        "quarantined_submission_count": review["quarantined_submission_count"],
        "artifacts": _json_ready({
            key: value for key, value in review.items()
            if key not in {"message", "reviewed_submission_count", "quarantined_submission_count"}
        }),
    }


def _generate_economy_package(
    *,
    economy: str,
    base_year: int,
    output_dir: Path,
    package_version: str,
    source_package_version: str,
    fallback_csv: str | Path | None = None,
) -> dict[str, object]:
    package_paths = generate_checked_in_source_review_package(
        economy=economy,
        requested_base_year=base_year,
        source_package_version=source_package_version,
        package_version=package_version,
        output_dir=output_dir,
        fallback_csv=fallback_csv,
    )
    manifest = json.loads(package_paths["manifest_json"].read_text(encoding="utf-8"))
    resolution = manifest["resolution"]
    return {
        "economy": economy,
        "base_year": base_year,
        "resolution_summary": resolution["summary_counts"],
        "candidate_extraction_summary": resolution["candidate_extraction"],
        "artifacts": {name: str(path) for name, path in package_paths.items()},
    }


def _supplemental_inventory(destination: Path) -> tuple[dict[str, Any], Path]:
    supplemental_path = destination / "supplemental_provenance_inventory.csv"
    supplemental = build_supplemental_provenance_inventory(output_path=supplemental_path)
    return supplemental.summary, supplemental_path


def _checked_in_economies(source_package_version: str) -> list[str]:
    source_dir = STATIC_BUNDLE_ROOT / source_package_version
    if not source_dir.is_dir():
        raise ValueError(f"Checked-in static source package does not exist: {source_dir}")
    economies = sorted(path.stem for path in source_dir.glob("*.csv") if path.is_file())
    if not economies:
        raise ValueError(f"Checked-in static source package has no economy CSVs: {source_dir}")
    return economies


def _write_economy_conflict_report(
    *,
    destination: Path,
    economy: str,
    base_year: int,
    source_package_version: str,
) -> dict[str, object] | None:
    source_csv = STATIC_BUNDLE_ROOT / source_package_version / f"{economy}.csv"
    report = build_static_package_conflict_report(
        fallback_csv=source_csv,
        economy=economy,
        requested_base_year=base_year,
        source_package_version=source_package_version,
    )
    if report.empty:
        return None
    review = summarise_static_package_conflicts(report)
    quarantine_dir = destination / "quarantine" / economy
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    review_path = quarantine_dir / f"{economy}_{base_year}_source_conflict_review.csv"
    evidence_path = quarantine_dir / f"{economy}_{base_year}_source_conflict_evidence.csv"
    write_reviewer_csv(review, review_path)
    write_reviewer_csv(report, evidence_path)
    return {
        "conflict_review_csv": str(review_path),
        "conflict_review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "conflict_evidence_csv": str(evidence_path),
        "conflict_evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "conflict_group_count": int(report["Conflict Group"].nunique()),
        "conflict_row_count": len(report),
    }


def generate_staged_review(
    *,
    economy: str,
    base_year: int,
    output_dir: str | Path,
    package_version: str,
    source_package_version: str = CURRENT_SOURCE_PACKAGE_VERSION,
    fallback_csv: str | Path | None = None,
    include_researcher_submissions: bool = False,
    researcher_submissions_folder_id: str | None = None,
) -> dict[str, object]:
    """Generate one economy review plus optional researcher-submission review."""
    destination = _unused_output_dir(output_dir)
    submission_summary = _review_researcher_submissions(
        destination=destination,
        include_researcher_submissions=include_researcher_submissions,
        researcher_submissions_folder_id=researcher_submissions_folder_id,
    )
    economy_summary = _generate_economy_package(
        economy=economy,
        base_year=base_year,
        output_dir=destination,
        package_version=package_version,
        source_package_version=source_package_version,
        fallback_csv=fallback_csv,
    )
    supplemental_summary, supplemental_path = _supplemental_inventory(destination)
    summary: dict[str, object] = {
        "mode": "staging_only_no_promotion",
        "economy": economy,
        "base_year": base_year,
        "output_dir": str(destination),
        "package_version": package_version,
        "source_package_version": source_package_version,
        "resolution_summary": economy_summary["resolution_summary"],
        "candidate_extraction_summary": economy_summary["candidate_extraction_summary"],
        "supplemental_summary": supplemental_summary,
        "researcher_submission_review": submission_summary,
        "artifacts": {
            **economy_summary["artifacts"],
            "supplemental_inventory_csv": str(supplemental_path),
        },
    }
    _write_summary(destination, summary)
    return summary


def generate_all_economies_staged_review(
    *,
    base_year: int,
    output_dir: str | Path,
    package_version: str,
    source_package_version: str = CURRENT_SOURCE_PACKAGE_VERSION,
    include_researcher_submissions: bool = False,
    researcher_submissions_folder_id: str | None = None,
) -> dict[str, object]:
    """Generate every checked-in economy plus optional researcher-submission review."""
    destination = _unused_output_dir(output_dir)
    submission_summary = _review_researcher_submissions(
        destination=destination,
        include_researcher_submissions=include_researcher_submissions,
        researcher_submissions_folder_id=researcher_submissions_folder_id,
    )
    economy_summaries: list[dict[str, object]] = []
    economy_failures: list[dict[str, object]] = []
    resolution_totals: Counter[str] = Counter()
    extraction_totals: Counter[str] = Counter()
    economies = _checked_in_economies(source_package_version)
    for economy in economies:
        try:
            economy_summary = _generate_economy_package(
                economy=economy,
                base_year=base_year,
                output_dir=destination / "packages" / economy,
                package_version=package_version,
                source_package_version=source_package_version,
            )
        except REVIEW_FAILURES as exc:
            failure: dict[str, object] = {"economy": economy, "error": str(exc)}
            try:
                quarantine = _write_economy_conflict_report(
                    destination=destination,
                    economy=economy,
                    base_year=base_year,
                    source_package_version=source_package_version,
                )
            except REVIEW_FAILURES as report_exc:
                failure["conflict_report_error"] = str(report_exc)
            else:
                if quarantine is not None:
                    failure["quarantine_artifacts"] = quarantine
            economy_failures.append(failure)
            continue
        resolution_totals.update(economy_summary["resolution_summary"])
        extraction = economy_summary["candidate_extraction_summary"]
        for key in ("source_rows_total", "matched_rows", "candidate_count"):
            extraction_totals[key] += int(extraction[key])
        economy_summaries.append(economy_summary)
    supplemental_summary, supplemental_path = _supplemental_inventory(destination)
    summary: dict[str, object] = {
        "mode": "all_economies_staging_only_no_promotion",
        "base_year": base_year,
        "economy_count": len(economies),
        "generated_economy_count": len(economy_summaries),
        "failed_economy_count": len(economy_failures),
        "output_dir": str(destination),
        "package_version": package_version,
        "source_package_version": source_package_version,
        "resolution_summary": dict(sorted(resolution_totals.items())),
        "candidate_extraction_summary": dict(sorted(extraction_totals.items())),
        "supplemental_summary": supplemental_summary,
        "researcher_submission_review": submission_summary,
        "economies": economy_summaries,
        "economy_failures": economy_failures,
        "artifacts": {"supplemental_inventory_csv": str(supplemental_path)},
    }
    _write_summary(destination, summary)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate staged Module 1 review packages, a supplemental provenance audit, and optionally "
            "download/validate archived researcher submissions. Nothing is promoted or applied automatically."
        )
    )
    economy_group = parser.add_mutually_exclusive_group(required=True)
    economy_group.add_argument("--economy", help="Compact economy code, for example 20USA.")
    economy_group.add_argument(
        "--all-economies", action="store_true", help="Generate every economy in the checked-in source package."
    )
    parser.add_argument("--base-year", required=True, type=int, help="Requested model/output year.")
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
        help="Optional single-economy fallback CSV; not valid with --all-economies.",
    )
    parser.add_argument(
        "--include-researcher-submissions",
        action="store_true",
        help=(
            "Deliberately download and validate the configured researcher-submission archive, producing review-only "
            "decisions and override candidates. No submission is applied automatically."
        ),
    )
    parser.add_argument(
        "--researcher-submissions-folder-id",
        default=None,
        help=(
            "Optional researcher-submission archive folder ID; otherwise "
            "ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID is used."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.researcher_submissions_folder_id and not args.include_researcher_submissions:
            raise ValueError(
                "--researcher-submissions-folder-id requires --include-researcher-submissions."
            )
        if args.all_economies:
            if args.fallback_csv:
                raise ValueError("--fallback-csv is available only with --economy, not --all-economies.")
            summary = generate_all_economies_staged_review(
                base_year=args.base_year,
                output_dir=args.output_dir,
                package_version=args.package_version,
                source_package_version=args.source_package_version,
                include_researcher_submissions=args.include_researcher_submissions,
                researcher_submissions_folder_id=args.researcher_submissions_folder_id,
            )
        else:
            summary = generate_staged_review(
                economy=args.economy,
                base_year=args.base_year,
                output_dir=args.output_dir,
                package_version=args.package_version,
                source_package_version=args.source_package_version,
                fallback_csv=args.fallback_csv,
                include_researcher_submissions=args.include_researcher_submissions,
                researcher_submissions_folder_id=args.researcher_submissions_folder_id,
            )
    except REVIEW_FAILURES as exc:
        print(f"Review package generation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_json_ready(summary), indent=2, sort_keys=True))
    failed_economy_count = int(summary.get("failed_economy_count", 0))
    if failed_economy_count:
        print(
            f"Staged review attempted every economy but {failed_economy_count} failed strict validation; "
            "see review_run_summary.json. No submission was applied and no promotion/index update occurred.",
            file=sys.stderr,
        )
        return 2
    print("Staged Module 1 review completed; no submission was applied and no promotion/index update occurred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
