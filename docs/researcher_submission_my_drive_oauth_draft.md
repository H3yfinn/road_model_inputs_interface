# Draft: My Drive OAuth Archive Setup

> Status: design/runbook only. The current production archive uses a service
> account and does **not** implement this OAuth route yet. Keep the existing
> Shared Drive documentation unchanged until this route has been implemented and
> tested successfully.

This alternative lets the Road Model archive researcher submissions into a
folder in **Finn's My Drive**. Archive files are owned by the signed-in Google
account and consume that account's storage quota.

## Intended security boundary

The implementation must use only this Google Drive OAuth scope:

```text
https://www.googleapis.com/auth/drive.file
```

Do **not** request broad `https://www.googleapis.com/auth/drive` access.
`drive.file` allows the app to create its own archive files and work with files
or folders explicitly selected for the app. It is a narrow per-file permission,
not a hard folder-only security primitive.

The app must also enforce its own folder allow-list:

- the researcher/admin selects one archive folder using Google Picker;
- the backend stores that approved folder ID;
- the backend may create economy subfolders and CSV/metadata files only below
  that folder;
- it must reject any other parent-folder ID supplied by a request.

## Google Cloud setup (do this before implementation)

1. Use the existing Google Cloud project `clean-athlete-351101`.
2. Leave **Google Drive API** enabled.
3. Go to **APIs & Services → OAuth consent screen**.
4. Choose the appropriate audience:
   - `External` for a personal Gmail account or early testing;
   - `Internal` only if every researcher uses the same Google Workspace.
5. Fill in the app name, support email, and developer contact email.
6. Add your Google account as a **Test user** while the app is in Testing.
7. Add only the `drive.file` scope above.
8. Go to **Credentials → Create credentials → OAuth client ID → Web application**.
9. Name it `Road model researcher archive (HF)`.
10. Add this authorised redirect URI (the route will be implemented before use):

```text
https://finbarmaunsell-leap-road-model.hf.space/api/v1/road-module1/google-oauth/callback
```

11. Download/copy the OAuth client ID and client secret. Do not commit them.

Google may show an “unverified app” warning during Testing. Only the configured
test users should use that temporary flow. Do not publish the consent screen
until the workflow has been tested and the required verification status is
understood.

## Hugging Face Secrets to add after implementation

Add these as **Secrets**, not Variables:

| Name | Value |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth web-client ID from Google Cloud |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth web-client secret |
| `GOOGLE_OAUTH_REDIRECT_URI` | The exact callback URL above |
| `GOOGLE_DRIVE_ARCHIVE_REFRESH_TOKEN` | Generated once by the authorised archive-account flow |
| `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID` | Folder selected by Google Picker during setup |

The refresh token is as sensitive as a long-lived password for the granted
scope. Never paste it into Git, browser JavaScript, chat, or a public HF
Variable.

## Implementation requirements (do not skip)

1. Add `/google-oauth/start` and `/google-oauth/callback` backend routes using
   authorization-code flow with PKCE and a state value validated server-side.
2. Add an admin-only first-run page/action that opens Google Picker and selects
   the single archive folder. Do not accept arbitrary folder IDs from ordinary
   model-run requests.
3. Exchange the authorization code server-side and store only the resulting
   refresh token in HF Secrets.
4. Use `drive.file` for all Drive API calls.
5. Verify the selected folder is accessible, then write only into that folder's
   economy subfolders.
6. Keep the archive failure non-blocking: a Drive error must still allow the
   model run to start.
7. Keep existing metadata fields, including baseline version and checksum.

## First real test

1. Select a new empty My Drive test folder through the implemented admin flow.
2. Make one small, valid Module 1 edit.
3. Run the model.
4. Confirm exactly two new files appear beneath `<archive folder>/20_USA/`:
   - complete submitted canonical-long CSV;
   - matching metadata JSON.
5. Confirm the metadata contains the run ID, timezone-aware timestamp, baseline
   version, and baseline checksum.
6. Confirm the model completed even if Drive was deliberately made unavailable.
7. Revoke the OAuth grant or remove the refresh-token Secret, retry, and verify
   that the run reports the archive failure without blocking.

## After successful test

Replace the service-account/Shared Drive production runbook with the tested
OAuth method, update `UPDATE_METHOD.md`, and remove unused service-account
configuration from the deployed environment and code.

## References

- [Google Drive API OAuth scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Google OAuth authorization](https://developers.google.com/identity/protocols/oauth2)
- [Hugging Face Space Secrets](https://huggingface.co/docs/hub/main/spaces-overview)
