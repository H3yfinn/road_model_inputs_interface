# Researcher Submission Google Drive Archive

This runbook configures the optional immutable archive used when a researcher
changes Module 1 inputs and clicks **Run Road Model**. The archive is a review
record, not a source of truth: submissions are never automatically merged into
future defaults.

## Recommended deployment: Hugging Face + Shared Drive

Use a folder inside a Google **Shared drive**. A service account has no storage
quota, so a Shared drive is more reliable than a folder in an individual's My
Drive. The backend creates an economy subfolder, then writes one complete
canonical-long CSV and one metadata JSON file per changed submission. Existing
files are never overwritten.

1. Create a folder in a Shared drive, for example `Road model researcher submissions`.
2. Copy its folder ID from `https://drive.google.com/drive/folders/<FOLDER_ID>`.
3. In a dedicated Google Cloud project, enable the Google Drive API.
4. Create a service account named `road-model-archive`.
5. Create a JSON key for that account and keep it private. Do not add it to Git.
6. Add the service-account email as a Shared drive member with permission to
   create files and folders (normally **Content manager**).
7. In the Hugging Face Space's **Settings → Variables and secrets**, add:

   | Type | Name | Value |
   |---|---|---|
   | Secret | `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON` | Complete contents of the service-account JSON key |
   | Variable or Secret | `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID` | The Shared Drive folder ID from step 2 |

8. Deploy the interface. The Docker build installs the Google Drive client from
   `requirements.txt`; Hugging Face exposes Space Secrets as environment variables.

For a local backend, `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` can instead point to
the local JSON key file. Hugging Face should use
`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`, not a local file path.

## Service account fields

Suggested name: `road-model-archive`

Suggested description:

> Writes immutable Road Module 1 researcher-submission CSV and metadata records to the APERC Shared Drive archive. This account may create economy subfolders and files in that archive only; it must not modify source defaults, generated input versions, or LEAP model outputs.

Do not grant broad project IAM roles for this task. Folder/Shared Drive membership
is the required access boundary.

## Expected result and troubleshooting

After a researcher changes a value and starts a run, the log reports archive
success or failure before the model starts. An archive failure must not block the
model run. Each metadata record includes economy, timezone-aware timestamp,
Module 1 defaults version, session identity where available, model run ID,
submission identifier, and the exact baseline CSV checksum.

Common errors:

- `Drive archive is not configured`: add both settings above and restart/redeploy.
- `403` or permission failure: add the service-account email to the Shared drive
  or archive folder with file/folder creation permission.
- `404` folder not found: check the folder ID, not the whole Drive URL.
- `storage quota` error: use a Shared drive rather than My Drive.

## Security and lifecycle

- Never paste the JSON key into chat, browser code, Git, or a public Space Variable.
- Use an HF **Secret**, not a Variable, for the JSON key.
- Rotate the service-account key periodically and immediately revoke it if it is
  exposed or the archive integration is retired.
- A service-account key is not recoverable after initial download; create a new
  one if it is lost.
