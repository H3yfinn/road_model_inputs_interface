#%%
"""Inspect one archived submission; use the batch-review entry point by default.

For normal end-of-iteration work, run review_researcher_submission_batch.py so
only submissions absent from the recorded checkpoint are collected. This file
is intentionally retained for an urgent or unusual individual investigation.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from core.researcher_submission_review import (
    build_final_value_overrides, build_source_promotion_plan, compare_submission_to_baseline,
    normalise_module1_csv, path_within, validate_identifier, validate_version,
    write_reviewer_csv,
)


def _load_static_builder():
    """Import the expensive static builder only when an approved rebuild is requested."""
    import build_road_model_static_defaults

    return build_road_model_static_defaults


def review_submission(submission_path: Path, baseline_path: Path, output_dir: Path, baseline_version: str, submission_id: str) -> dict[str, Path]:
    """Write review, final-override candidate, and source-promotion plan without mutating data."""
    submission_id = validate_identifier(submission_id, "submission ID")
    baseline_version = validate_version(baseline_version)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    submission = normalise_module1_csv(submission_path)
    baseline = normalise_module1_csv(baseline_path, legacy_values_are_internal=False)
    review = compare_submission_to_baseline(submission, baseline)
    review_path = path_within(output_dir, f"{submission_id}_review.csv")
    overrides_path = path_within(output_dir, f"{submission_id}_final_value_overrides_candidate.csv")
    promotion_path = path_within(output_dir, f"{submission_id}_source_promotion_plan.csv")
    write_reviewer_csv(review, review_path)
    write_reviewer_csv(build_final_value_overrides(review, note_prefix=f"Approved researcher submission {submission_id}"), overrides_path)
    write_reviewer_csv(build_source_promotion_plan(review, baseline_version, submission_id), promotion_path)
    return {"review": review_path, "override_candidate": overrides_path, "promotion_plan": promotion_path}


def build_approved_source_version(new_version: str) -> None:
    """Generate a new immutable defaults/static version after a reviewer updates a source owner.

    This intentionally has no source-editing arguments: review approval and the
    source-file change happen first, then this creates a fresh dated package.
    """
    new_version = validate_version(new_version)
    static_builder = _load_static_builder()
    if not new_version or new_version == static_builder.DEFAULT_VERSION:
        raise ValueError("Choose a new immutable dated version; never rebuild the existing default version in place.")
    static_builder.main(version=new_version)


# --- Edit these values in a Jupyter/VS Code interactive cell before running. ---
RUN_REVIEW = False
SUBMISSION_PATH = Path("")
BASELINE_PATH = Path("")
OUTPUT_DIR = Path("outputs/researcher_submission_reviews")
BASELINE_VERSION = ""
SUBMISSION_ID = ""
NEW_VERSION = ""
BUILD_APPROVED_SOURCE_VERSION = False

if __name__ == "__main__" and RUN_REVIEW:
    print(review_submission(SUBMISSION_PATH, BASELINE_PATH, OUTPUT_DIR, BASELINE_VERSION, SUBMISSION_ID))
if __name__ == "__main__" and BUILD_APPROVED_SOURCE_VERSION:
    build_approved_source_version(NEW_VERSION)
#%%
