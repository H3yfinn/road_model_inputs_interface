# Researcher Submission My Drive Archive

This runbook configures the optional immutable archive used when a researcher
changes Module 1 inputs and clicks **Run Road Model**. The archive is a review
record, not a source of truth: submissions are never automatically merged into
future defaults.

For normal end-of-iteration work, use the checkpointed batch-review tool in
the promotion guide. It collects and records only submissions not already
processed by that review batch, avoiding repeated manual inspection of the
whole archive.

## Deliberate all-in-one local review

An operator can stage all checked-in Module 1 economy packages, the separate
supplemental provenance inventory and a read-only review of every currently
visible archived submission in one command from the repository root:

```powershell
python back-end/scripts/generate_module1_review_package.py `
  --all-economies `
  --base-year 2022 `
  --package-version review_only_all_2022 `
  --output-dir C:\path\to\new_or_empty_staging_directory `
  --include-drive-submissions
```

The Drive download is performed only when `--include-drive-submissions` is
present. It uses `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID` by default, or an
explicit `--drive-folder-id`, together with the existing archive credentials.
The output directory is a new review batch, so all archive pairs are considered;
the lower-level checkpointed batch tool remains preferable when continuing an
established review directory.

This is still review-only. Downloads, quarantine reports, review decisions and
candidate overrides are written below `drive_submission_review/`, but nothing
is uploaded, deleted, applied or promoted. The generated economy packages do
not incorporate those submissions. `--base-year 2022` selects the requested
model/output year for the checked-in packages; it does not mean that all Drive
submissions or source evidence are dated 2022.

If one economy fails strict package validation, the command continues trying
the remaining economies, records the failure in `review_run_summary.json`, and
returns a nonzero exit code. Reviewers must therefore treat the run as partial
until every listed economy succeeds.

## Active deployment: Hugging Face + Finn's My Drive

The deployed archive uses OAuth with the narrow `drive.file` permission. It
creates an app-owned `Road model researcher submissions` folder in Finn's My
Drive, then creates economy subfolders and writes one complete canonical-long
CSV plus one metadata JSON file for each changed submission. Existing files are
never overwritten. Economy/version inputs are validated before any filesystem
or Drive path is constructed. Archive files are uploaded under non-reviewable
staging names, completed with their mutual Drive file IDs and checksums, and
only then published under the documented pair filenames. Failed publication
attempts make a best-effort cleanup of only the files created by that attempt.

The configuration and one-time connection procedure are the canonical runbook:
[`researcher_submission_my_drive_oauth_draft.md`](researcher_submission_my_drive_oauth_draft.md).
For reviewing and promoting a submission into a future default, use
[`researcher_change_review_and_promotion_guide.md`](researcher_change_review_and_promotion_guide.md).

## Expected result and troubleshooting

After a researcher changes a value and starts a run, the log reports archive
success or failure before the model starts. An archive failure must not block the
model run. Each metadata record includes economy, timezone-aware timestamp,
Module 1 defaults version, session identity where available, model run ID,
submission identifier, and the exact baseline CSV checksum.

When the browser opens, it performs a read-only check of the configured archive
folder. If the folder or Drive connection is unavailable, an amber warning next
to **Tour** tells researchers to use **Download Filled CSV** before running if
they need their changed inputs retained for later review. The model can still be
run for exploratory work, but an unarchived run cannot be batch-reviewed or
promoted unless it is rerun after the archive becomes available.

A changed submission is archived only when the exact version/economy baseline
CSV is locally available. Batch review verifies its recorded checksum against
that immutable static version before comparing values. A missing or changed
baseline quarantines the submission; it is never silently compared with the
current website default.

Common errors:

- `Drive archive is not configured`: add both settings above and restart/redeploy.
- `OAuth Drive archive credentials are incomplete`: check all five OAuth
  archive Secrets are present with their exact names.
- `invalid_grant` or token failure: reconnect the My Drive archive using the
  one-time setup page and replace the refresh-token Secret.
- `404` folder not found: check the folder ID, not the whole Drive URL.
- `storage quota` error: confirm the archive-owning My Drive account is active.

## Security and lifecycle

- Never paste OAuth client secrets, setup tokens, or refresh tokens into chat,
  browser code, Git, or a public Space Variable.
- Use HF **Secrets**, not Variables, for all OAuth values.
- Both OAuth and legacy service-account connections use the narrow
  `drive.file` scope; broad whole-Drive scope is not requested.
- One-time setup creates or verifies **Anyone with the link → Viewer** access.
  It refuses a folder with public/link writer access instead of silently
  accepting broader ordinary-user permissions.
- The archive folder is intentionally **Anyone with the link → Viewer**.
  Anyone who obtains that link can theoretically download submissions; this is
  accepted because these submissions are not treated as sensitive or especially
  useful outside the model workflow.
