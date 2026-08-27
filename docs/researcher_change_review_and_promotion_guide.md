# Researcher Change Review and Default-Promotion Guide

## Intention

Use this guide when a researcher changes a Road Module 1 value in the website
and the team wants to consider making that change a future website default. It
keeps three things separate:

1. **Researcher submission** — an immutable record of what was run.
2. **Model-manager decision** — a human decision about whether the change is sound.
3. **New defaults version** — a newly built package that becomes the website
   default only after approval and deployment.

An archived submission never updates source inputs or website defaults by
itself.

## Default cadence: batch promotion at the end of an iteration

Treat the archive as a collection point during modelling, then review and
promote changes as a **large batch at the end of a modelling iteration**. Do
not normally rebuild and deploy defaults economy by economy as submissions
arrive.

Use `review_researcher_submission_batch.py` as the **default review entry
point**. Its checkpoint means the model manager/developer sees only submissions
that have arrived since the last recorded batch, rather than repeatedly sifting
through every CSV and metadata file in Drive. Use the one-submission tool only
to investigate an urgent or unusual individual submission.

The recommended sequence is:

1. Researchers submit and test changes for all relevant economies during the
   iteration.
2. The model manager/developer runs the batch-review tool, then groups the new
   records and resolves cross-economy consistency issues together.
3. The model manager/developer applies the approved set of changes together in
   the correct source location.
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
  -> model manager/developer downloads the CSV and compares it with its recorded baseline
  -> model manager/developer approves, rejects, or requests changes
  -> approved change is put in the correct source location
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
| Model manager/developer | Reviews submissions, chooses the correct source location, applies approved changes, builds a new version, and deploys it | Treats an archive as automatically approved, rebuilds an existing version in place, or exposes OAuth/Drive secrets |

## 1. Researcher submission and archive

When a researcher changes any existing Module 1 input — for example `Stock`,
`Mileage`, `Fuel Economy`, a sales share, or a reconciliation weight — and
clicks **Run Road Model**:

- once per browser session, the website explains that changed inputs and
  comments will be saved to the shared archive, repeats what a useful source /
  reason note contains, and asks the researcher to acknowledge this before the
  run continues;
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

Every comment input is labelled **Source / reason for change**. For each changed
value, researchers should record the dataset or document, source year, link or
reference, and why the value changed. The same guidance is shown beside the run
action and in the run acknowledgement. If a changed value has no note, the
interface warns how many notes are missing but does not block the model run.
Researchers must not include personal, confidential, or sensitive information:
the archive folder is intentionally shared as **Anyone with the link → Viewer**.

## 2. Obtain the submission and correct baseline

1. Open the shared [Road model researcher submissions archive](https://drive.google.com/drive/folders/1Dwl1PMh3WMR3CjLtbGVLC4HmxFPO--RX),
   then open the required `<economy>/` folder.
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

## 3. Default: batch-download and review new archive submissions

For the normal end-of-iteration review, use
`back-end/scripts/review_researcher_submission_batch.py`. It uses the
configured Drive archive connection to download only submission CSV + metadata
pairs that are not already recorded in its local checkpoint. Archive pairs are
untrusted input: before review, the tool validates metadata, pair filenames and
IDs, canonical CSV columns, economy/version, row count, CSV checksum, baseline
filename, and baseline checksum. It creates a **review dataset and candidate
override files**; it never alters Drive, source files, generated defaults,
active overrides, or the website.

Run it only on the model manager/developer's secure local machine, where the
existing Drive OAuth credentials are available as environment variables. Do not
put those credentials in a notebook, a CSV, or Git. In a Jupyter notebook or
VS Code interactive cell, the normal review is one call. It reads the archive
folder ID from `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID`, uses the repository's
static bundles, and keeps its checkpoint in the stable default output folder:

```python
#%%
import sys
from pathlib import Path

REPO_DIR = Path(r"C:\Users\Work\github\road_model_inputs_interface")
BACKEND_DIR = REPO_DIR / "back-end"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from review_researcher_submission_batch import review_new_archived_submissions

artefacts = review_new_archived_submissions()
artefacts
#%%
```

Pass `output_dir=Path(...)` only when a different secure local review folder is
needed. Keep using the same output folder during an iteration so the locked
checkpoint prevents repeat work.

The output folder contains:

| File | Meaning |
|---|---|
| `batch_review_decisions.csv` | **Open this first.** One row per model key and only 14 plainly named columns: a blank `Chosen Value`, baseline, newest proposal and time, all distinct proposals newest-first, latest source/reason note, proposal count, and direct review guidance |
| `batch_review_rows.csv` | Supporting audit detail, one row per proposal, including submission identity, explicit recency rank, `Batch Status`, cumulative `Review Reasons`, and `Safe Replacement` |
| `batch_review_manifest.csv` | Submission-level audit: timestamp/run/researcher-or-session identity, archive file IDs/checksums, baseline identity, row counts, outcome, and failure reason |
| `batch_review_quarantine.csv` | Invalid, incomplete, or baseline-unverifiable submissions, with file IDs, reason, and quarantine fingerprint |
| `module1_final_value_overrides_<economy>_candidate.csv` | A candidate replacement dataset for that economy, in raw/internal units. It is not live and must still be approved. |
| `batch_review_checkpoint.json` | The atomically replaced, file-locked record of successful submission IDs plus quarantined file fingerprints |

`Batch Status` makes the decision visible before anything is promoted:

| Status | Meaning and action |
|---|---|
| `replacement_candidate` | One existing baseline row has a proposed replacement. Check it, then decide whether to promote it. |
| `same_replacement_proposed_multiple_times` | More than one submission proposes the same replacement. It is included once in the candidate file, but still needs a human decision. |
| `conflicting_replacement_values` | Submissions against one baseline version propose different values for the same row. No candidate override is made; decide manually. |
| `new_or_removed_row_requires_source_review` | A row key was added or removed. Do not use a final override; review the source/contract change. |
| `baseline_version_mismatch_requires_review` | The same row was submitted against different defaults versions. Resolve the baseline difference first. |
| `multiple_review_reasons` | Multiple blocking conditions apply. Read every semicolon-separated `Review Reasons` value. |

`Review Reasons` can include `added_key_requires_source_review`,
`removed_key_requires_source_review`, `baseline_version_mismatch`,
`conflicting_proposed_values`, and `identical_duplicate_proposal`. Only existing
key replacements with no blocking reason are marked `Safe Replacement=True`
and included in a candidate. Identical duplicates remain visible in review rows
but are deduplicated in the candidate.

The decision sheet intentionally shows the newest proposal first and records
its timestamp, but does **not** imply that newest means correct. Enter a value in
`Chosen Value` only after checking the source/reason. For conflicts, baseline
mismatches, additions, or removals, follow `Review Guidance` and open
`batch_review_rows.csv` only for the extra evidence needed. This keeps the
ordinary selection task small without discarding the full audit trail.

A malformed pair does not abort later valid submissions. It is written to the
quarantine report and recorded by Drive/file fingerprint, not in
`processed_submission_ids`. An unchanged bad object is skipped later; changed
file identity/metadata makes it eligible for validation again. If nothing new
is found, the result says so explicitly and all output CSVs contain headers.

All reviewer CSV writers neutralise formula-like text beginning with `=`, `+`,
`-`, or `@` (including after leading whitespace) by prefixing an apostrophe.
Numeric negative values remain numeric.

Keep the checkpoint with the batch review record. To deliberately review every
archived submission again, create a new empty review-output folder; do not
delete a checkpoint by accident. Candidate CSVs are only a convenient starting
point for the approval workflow below, not an automatic integration.

## 3A. Exception: inspect one specific submission

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
| `*_final_value_overrides_candidate.csv` | Candidate values in the model's internal units, ready for model-manager approval |
| `*_source_promotion_plan.csv` | A checklist showing the source location the model manager/developer must choose |

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

The correct source location depends on provenance. A one-off reviewed policy or
model judgement may belong in `final_value_overrides`; a corrected upstream
dataset value should be fixed in its actual processed/manual/supplemental
source instead.

## 5. Promote an approved change without losing history

### A. Targeted final-value override

Use this for a small approved exception that should intentionally take priority
over source-merged values.

#### Duplicate and priority rule — do not rely on file order

Final-value overrides are the last layer after the normal source merge, so an
override takes priority over a source-provided value. However, there is **no
“last file wins” or alphabetical file-priority rule** between two final-value
override rows.

Each override key must be unique across every matching override file for the
economy. The key is:

```text
Branch Path + Variable + Scenario + Year
```

If the same key appears twice — whether in one CSV or in two files in
`final_value_overrides/` — the build fails with a duplicate-row-key error. It
does not choose one value silently.

Before adding a new override, search the existing economy override files for
the same key. If an approved value supersedes an existing override, update that
existing row and its note, or mark the old row `DO_NOT_USE`; do not add a second
row and expect an implicit priority order. If different values genuinely need
to coexist, they must have different scenarios, years, variables, or branch
paths.

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
5. Add an approval note, source/evidence reference, model manager/developer,
   and date in the
   `note` field and `UPDATE_METHOD.md`.

### B. Correct the underlying source

Use this when the source data itself was wrong or superseded.

1. Locate the correct source location from the reviewed row's provenance and the source
   merge method.
2. Update that source file or its documented generation method.
3. Update `back-end/data/road_model/UPDATE_METHOD.md` with the reason, source,
   model manager/developer, and affected outputs.
4. Do not also add a final override unless the source method cannot express the
   approved exception.

## 6. Build a new immutable defaults version

After the model manager/developer has made the **approved batch** of changes, create one new
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
3. Run the review diff again against the new version: the approved change
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

## 9. Archive retention and safe cleanup

The Drive archive is not wiped automatically. It is an audit trail for what a
researcher ran, so cleanup should normally happen as a deliberate batch task at
the end of an iteration or edition—not immediately after each economy run.

### Normal workflow: leave the archive intact

Most users have **Anyone with the link → Viewer** access. They can open and
download files, but cannot move, delete, upload, or change sharing permissions.
That is intentional: the archive is owned by the Drive account that created it.

Researchers and colleagues should therefore not try to clean up the archive.
They should use the batch-review tool in section 3A. It reads only submissions
not already recorded in that batch folder's `batch_review_checkpoint.json`,
then records every downloaded submission in `batch_review_manifest.csv`. This
lets later batches find the new submissions without needing to delete older
audit records.

If someone believes test files or old submissions should be removed, they
should contact the Drive owner/model manager/developer with the economy,
submission ID, and reason. Only that owner (or a person explicitly given Editor
access) can perform cleanup.

### Owner-only cleanup procedure

1. Decide the retention boundary first, for example “remove test submissions
   from this iteration after the approved defaults version has been deployed.”
2. Confirm that every submission being removed has either been rejected,
   incorporated into a reviewed version, or retained elsewhere for a specific
   audit reason.
3. Open the shared [Road model researcher submissions archive](https://drive.google.com/drive/folders/1Dwl1PMh3WMR3CjLtbGVLC4HmxFPO--RX)
   and work economy by economy.
4. Delete a submission's CSV and matching metadata JSON **together**. Match
   them using their common timestamp/submission-ID prefix.
5. Move files to Google Drive Trash first. Do not permanently empty Trash until
   the model manager/developer has checked the selected submissions.
6. Record the cleanup date, selected economy/submission IDs, reason, and person
   who performed it in the iteration notes or `UPDATE_METHOD.md`.

### Metadata and records for a long-lived archive

Every submission is deliberately stored as a paired CSV and metadata JSON. The
metadata records a unique `submission_id`, economy, timestamp, defaults version,
model-run ID, original submission identifier, row count, CSV checksum, and the
baseline filename and checksum. Archive format 2 also records both Drive file
IDs, the canonical columns, and `pair_state=complete`. The shared ID is the
authoritative way to match the pair. Drive listings use 1,000-item pages and
follow pagination tokens so thousands of archived submissions remain usable.

For each review batch, retain these locally with the iteration records:

- `batch_review_manifest.csv` — the inventory of newly processed submissions;
- `batch_review_decisions.csv` — the compact, one-row-per-key decision sheet;
- `batch_review_rows.csv` — the proposal-level audit detail;
- `batch_review_quarantine.csv` — invalid pair/baseline evidence and reasons;
- `batch_review_checkpoint.json` — successful IDs and quarantined fingerprints;
- the commit/version that eventually incorporated any approved changes.

Never rename just one file in a CSV/metadata pair. If a file name must change,
rename both consistently and preserve the `submission_id` inside the metadata.

### Important boundaries

- Do not delete the `Road model researcher submissions` root folder. Its ID is
  saved in Hugging Face as `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID`; deleting
  it breaks future archiving.
- Deleting an economy subfolder is recoverable from Trash, and the application
  can create it again on a future submission, but it removes that economy's
  archive history. Prefer deleting selected submission pairs instead.
- Removing a file from Drive prevents future link-based downloads, but cannot
  retrieve copies that someone may already have downloaded.
- The shared-link setting is intentionally broad. If the archive ever begins to
  contain sensitive information, change its sharing policy before continuing to
  use it rather than relying on later cleanup.

## What is deliberately not automatic

- An archive does not change defaults.
- The review script does not copy a candidate into source data.
- The build does not replace an older version.
- The website does not become a source-data editor.
- Archive deletion is never triggered by a model run, review, build, or deploy.

Those controls are intentional: they keep a researcher experiment, a reviewed
assumption, and a published default distinguishable years later.

## Related documents

- [My Drive OAuth Archive Setup](researcher_submission_my_drive_oauth_draft.md)
- [Google Drive archive overview](researcher_submission_drive_archive.md)
- `back-end/data/road_model/UPDATE_METHOD.md`
- `back-end/scripts/review_researcher_submission.py`
