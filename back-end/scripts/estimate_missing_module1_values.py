"""Generate a cross-validated, review-only missing-value proposal package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from tempfile import mkdtemp


BACK_END = Path(__file__).resolve().parents[1]
if str(BACK_END) not in sys.path:
    sys.path.insert(0, str(BACK_END))

from core.missing_value_estimation import (
    DEFAULT_MIN_ADJUSTMENT_ROWS,
    DEFAULT_MIN_PEER_ECONOMIES,
    REVIEW_COLUMNS,
    STRICTLY_POSITIVE_VARIABLES,
    estimate_missing_values,
    load_static_estimation_pool,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_review_package(
    *,
    static_dir: str | Path,
    base_year: int,
    output_dir: str | Path,
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise ValueError(f"Output directory must not already exist: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        pool, source_paths = load_static_estimation_pool(static_dir, base_year=base_year)
        result = estimate_missing_values(pool, base_year=base_year)
        artifacts = {
            "proposals": staging / "proposed_missing_values.csv",
            "proposal_audit": staging / "proposal_audit.csv",
            "evidence": staging / "proposal_evidence.csv",
            "cross_validation": staging / "cross_validation_predictions.csv",
            "cross_validation_summary": staging / "cross_validation_summary.csv",
        }
        result.proposals.reindex(columns=REVIEW_COLUMNS).to_csv(
            artifacts["proposals"], index=False, lineterminator="\n", float_format="%.15g"
        )
        result.proposals.to_csv(
            artifacts["proposal_audit"], index=False, lineterminator="\n", float_format="%.15g"
        )
        result.evidence.to_csv(artifacts["evidence"], index=False, lineterminator="\n", float_format="%.15g")
        result.cross_validation.to_csv(
            artifacts["cross_validation"], index=False, lineterminator="\n", float_format="%.15g"
        )
        result.cross_validation_summary.to_csv(
            artifacts["cross_validation_summary"], index=False, lineterminator="\n", float_format="%.15g"
        )
        manifest = {
            "schema_version": 1,
            "mode": "review_only_no_promotion",
            "estimator": "masked_known_value_cross_validation",
            "base_year": int(base_year),
            "strictly_positive_variables": sorted(STRICTLY_POSITIVE_VARIABLES),
            "minimum_peer_economies": DEFAULT_MIN_PEER_ECONOMIES,
            "minimum_adjustment_rows": DEFAULT_MIN_ADJUSTMENT_ROWS,
            "source_static_directory": str(Path(static_dir).resolve()),
            "source_csv_count": len(source_paths),
            "source_csv_sha256": {path.name: _sha256(path) for path in source_paths},
            "selected_strategies": dict(result.selected_strategies),
            "proposal_row_count": len(result.proposals),
            "evidence_row_count": len(result.evidence),
            "cross_validation_prediction_count": len(result.cross_validation),
            "artifacts": {
                name: {"filename": path.name, "sha256": _sha256(path)}
                for name, path in artifacts.items()
            },
        }
        manifest_path = staging / "estimation_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging.replace(destination)
        return {**manifest, "output_dir": str(destination), "manifest": str(destination / manifest_path.name)}
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-dir", required=True, help="Explicit static package version directory.")
    parser.add_argument("--base-year", required=True, type=int, help="Current Accounts base year to estimate.")
    parser.add_argument("--output-dir", required=True, help="New staging-only output directory.")
    args = parser.parse_args()
    try:
        summary = generate_review_package(
            static_dir=args.static_dir,
            base_year=args.base_year,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"Missing-value estimation failed safely: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
