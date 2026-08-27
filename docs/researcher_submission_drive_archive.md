# Researcher Submission My Drive Archive

This runbook configures the optional immutable archive used when a researcher
changes Module 1 inputs and clicks **Run Road Model**. The archive is a review
record, not a source of truth: submissions are never automatically merged into
future defaults.

For normal end-of-iteration work, use the checkpointed batch-review tool in
the promotion guide. It collects and records only submissions not already
processed by that review batch, avoiding repeated manual inspection of the
whole archive.

## Active deployment: Hugging Face + Finn's My Drive

The deployed archive uses OAuth with the narrow `drive.file` permission. It
creates an app-owned `Road model researcher submissions` folder in Finn's My
Drive, then creates economy subfolders and writes one complete canonical-long
CSV plus one metadata JSON file for each changed submission. Existing files are
never overwritten.

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
- The archive folder is intentionally **Anyone with the link → Viewer**.
  Anyone who obtains that link can theoretically download submissions; this is
  accepted because these submissions are not treated as sensitive or especially
  useful outside the model workflow.
