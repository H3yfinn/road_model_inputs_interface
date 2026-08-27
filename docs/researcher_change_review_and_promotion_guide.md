# Researcher Change Review and Default-Promotion Guide

## Intention

Use this guide when a researcher changes a Road Module 1 value in the website
and the team wants to consider making that change a future website default. It
keeps three things separate:

1. **Researcher submission** — an immutable record of what was run.
2. **Reviewer decision** — a human decision about whether the change is sound.
3. **New defaults version** — a newly built package that becomes the website
   default only after approval and deployment.

An archived submission never updates source inputs or website defaults by
itself.

## Default cadence: batch promotion at the end of an iteration

Treat the archive as a collection point during modelling, then review and
promote changes as a **large batch at the end of a modelling iteration**. Do
not normally rebuild and deploy defaults economy by economy as submissions
arrive.

The recommended sequence is:

1. Researchers submit and test changes for all relevant economies during the
   iteration.
2. Reviewers collect the archive records, group comparable changes, and resolve
   cross-economy consistency issues together.
3. Source owners apply the approved set of changes together.
4. Build, validate, commit, and deploy one new dated defaults version for that
   reviewed batch.

This produces one clear version boundary and avoids a website default changing
mid-iteration because one economy happened to be reviewed first. An individual
economy promotion is appropriate only for an urgent, documented correction that
cannot wait for the normal batch.

## Plain-English flow

```text
researcher changes a website value
  -> runs the model
  -> complete submission CSV + metadata JSON go to Google Drive
  -> reviewer downloads the CSV and compares it with its recorded baseline
  -> reviewer approves, rejects, or requests changes
  -> approved change is put in the correct source owner
  -> build a new dated immutable version
  -> deploy that version
  -> researchers see the approved value as the new website default
```

The previous source files and previous generated version are retained. Do not
overwrite a previous version to promote a change.

## Roles and access

| Role | What they do | What they must not do |
|---|---|---|
| Researcher | Edits existing values/comments, runs the model, checks results | Adds new row keys or edits source/default files directly |
| Reviewer | Compares the archive to the named baseline and decides whether it is suitable | Treats an archive as automatically approved |
| Source owner | Updates the appropriate documented source/override and rebuilds a new version | Rebuilds an existing version in place |
| Deployment owner | Commits and deploys the reviewed version | Exposes OAuth or Drive secrets |

## 1. Researcher submission and archive

When a researcher changes any existing Module 1 input — for example `Stock`,
`Mileage`, `Fuel Economy`, a sales share, or a reconciliation weight — and
clicks **Run Road Model**:

- the website submits the complete canonical-long Module 1 CSV, not only the
  changed rows;
- the model run starts from that submitted package; and
- the Drive archive creates two immutable files in
  `Road model researcher submissions/<economy>/`:
  - `..._module1_<version>.csv`, the complete submission;
  - `..._metadata.json`, including timestamp, run ID, baseline version and
    baseline checksum.

The archive is a review record. It is not a live database and it is not a
source of truth for future defaults.

Researchers should put a clear explanation in the changed row's comment. They
must not include personal, confidential, or sensitive information: the archive
folder is intentionally shared as **Anyone with the link → Viewer**.

## 2. Obtain the submission and correct baseline

1. In Google Drive, open `Road model researcher submissions/<economy>/`.
2. Download the submission CSV and matching metadata JSON to a local review
   folder. Do not edit the downloaded submission CSV.
3. Open the metadata JSON and record:
   - `module1_defaults_version`;
   - `baseline_filename` and `baseline_sha256`;
   - `submission_id` and `model_run_id`.
4. Find the matching website baseline in this repository:

```text
front-end/road-module1-static/<module1_defaults_version>/<compact-economy>.csv
```

For example, for `20_USA` and version
`v2026_06_05_road_module1_sources`, use:

```text
front-end/road-module1-static/v2026_06_05_road_module1_sources/20USA.csv
```

Use the version named in the metadata, not whatever happens to be the current
website default. This is what makes the review reproducible.

## 3. Generate the review artefacts

Use the notebook-friendly functions in
`back-end/scripts/review_researcher_submission.py`. The review step writes
files only to its selected review-output folder; it does not modify sources,
defaults, or the website bundle.

In a Jupyter notebook or VS Code interactive Python cell, use a dated local
review folder and set the paths explicitly. Because the repository folder is
named `back-end` (with a hyphen), use this import setup instead of importing
`back-end` as a Python package:

```python
#%%
from pathlib import Path
import sys

REPO_DIR = Path(r"C:\Users\Work\github\road_model_inputs_interface")
BACKEND_DIR = REPO_DIR / "back-end"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from review_researcher_submission import review_submission

SUBMISSION_PATH = Path(r"C:\review\20USA\submission_module1.csv")
BASELINE_VERSION = "v2026_06_05_road_module1_sources"
BASELINE_PATH = REPO_DIR / "front-end" / "road-module1-static" / BASELINE_VERSION / "20USA.csv"
OUTPUT_DIR = Path(r"C:\review\20USA\2026_08_27_submission_review")
SUBMISSION_ID = "2026-08-27_researcher_submission"

artefacts = review_submission(
    submission_path=SUBMISSION_PATH,
    baseline_path=BASELINE_PATH,
    output_dir=OUTPUT_DIR,
    baseline_version=BASELINE_VERSION,
    submission_id=SUBMISSION_ID,
)
artefacts
#%%
```

The output folder contains:

| File | Meaning |
|---|---|
| `*_review.csv` | Every changed, added, or removed row relative to the baseline |
| `*_final_value_overrides_candidate.csv` | Candidate values in the model's internal units, ready for reviewer approval |
| `*_source_promotion_plan.csv` | A checklist showing that a reviewer must choose the correct source owner |

## 4. Review and decide

Open `*_review.csv` and check, row by row:

- the economy, scenario, branch path, variable, and year are expected;
- the baseline and submitted values are plausible;
- the value uses the correct scale and units;
- the comment gives adequate evidence; and
- the change does not unintentionally remove or add a row key.

Choose one of these outcomes:

| Decision | Next action |
|---|---|
| Reject | Keep the archive for the audit trail. Do not promote it. |
| Ask for clarification | Send the review result back to the researcher; they submit a new run later. |
| Approve as a targeted override | Use the final-value override candidate as described below. |
| Approve as a source-data correction | Update the owning source file/method and `UPDATE_METHOD.md`, then rebuild. |

The correct source owner depends on provenance. A one-off reviewed policy or
model judgement may belong in `final_value_overrides`; a corrected upstream
dataset value should be fixed in its actual processed/manual/supplemental
source instead.

## 5. Promote an approved change without losing history

### A. Targeted final-value override

Use this for a small approved exception that should intentionally take priority
over source-merged values.

1. Review the candidate CSV; do not promote a test file or an unreviewed file.
2. Copy the approved rows into the economy's documented final-override source
   location under:

```text
back-end/data/road_model/final_value_overrides/
```

3. Use the expected filename pattern:

```text
module1_final_value_overrides_20USA.csv
```

4. Preserve the candidate's raw/internal `Value` values. Do not manually turn
   `Millions` or `Thousands` back into website display values.
5. Add an approval note, source/evidence reference, reviewer, and date in the
   `note` field and `UPDATE_METHOD.md`.

### B. Correct the underlying source

Use this when the source data itself was wrong or superseded.

1. Locate the source owner from the reviewed row's provenance and the source
   merge method.
2. Update that source file or its documented generation method.
3. Update `back-end/data/road_model/UPDATE_METHOD.md` with the reason, source,
   reviewer, and affected outputs.
4. Do not also add a final override unless the source method cannot express the
   approved exception.

## 6. Build a new immutable defaults version

After source owners have made the **approved batch** of changes, create one new
dated version instead of rebuilding the previous version. From a
notebook/interactive cell:

```python
#%%
from review_researcher_submission import build_approved_source_version

NEW_VERSION = "v2026_08_27_approved_researcher_changes"
build_approved_source_version(NEW_VERSION)
#%%
```

The build:

1. generates each economy's Module 1 package;
2. runs the static-contract/completeness checks;
3. writes a new static website bundle under
   `front-end/road-module1-static/<NEW_VERSION>/`; and
4. updates `front-end/road-module1-static/index.json` so this new version is
   the website default.

Never use the previous version name. The function rejects a rebuild of the
configured default version for this reason.

## 7. Verify before deployment

At minimum:

1. Confirm the approved row exists in the new static CSV with the intended
   website/display value.
2. Confirm its `Input Status`, comment, source, units, and scale are sensible.
3. Run the reviewer diff again against the new version: the approved change
   should no longer appear as a difference.
4. Run the affected economy through the road workflow.
5. Confirm the website loads the new version and displays the approved value as
   the default.

For a stock change, also check stock shares and downstream module outputs; a
stock value can affect derived stock shares, turnover, and energy results.

## 8. Commit and deploy

Commit only the approved source change, the generated new static/default
version, and its documentation. Keep archived submissions and local review
outputs out of Git unless there is an explicit reason to retain a small review
artefact in the repository.

Push the commit to `main`. The existing deployment workflow updates the Hugging
Face Space. After deployment, reload the website and confirm the new version is
shown in its data/version information.

## What is deliberately not automatic

- An archive does not change defaults.
- The review script does not copy a candidate into source data.
- The build does not replace an older version.
- The website does not become a source-data editor.

Those controls are intentional: they keep a researcher experiment, a reviewed
assumption, and a published default distinguishable years later.

## Related documents

- [My Drive OAuth Archive Setup](researcher_submission_my_drive_oauth_draft.md)
- [Google Drive archive overview](researcher_submission_drive_archive.md)
- `back-end/data/road_model/UPDATE_METHOD.md`
- `back-end/scripts/review_researcher_submission.py`
