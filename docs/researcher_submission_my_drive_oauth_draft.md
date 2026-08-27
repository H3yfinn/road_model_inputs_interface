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
3. In the left navigation, use **Google Auth Platform**. The current console
   separates the OAuth setup into **Branding**, **Audience**, **Data Access**,
   and **Clients** (rather than the older single “OAuth consent screen” page).
4. In **Branding**, enter:
   - App name: `APERC Road Model Archive`;
   - User support email: `finn.maunsell@gmail.com`;
   - Developer contact email: `finn.maunsell@gmail.com`.

   A logo, homepage, privacy-policy URL, terms-of-service URL, and authorised
   domains are not needed for the initial Testing setup. Save the page. The
   developer-contact field is separate from the support email and is required
   even when both addresses are the same.
5. In **Audience**, choose the appropriate audience:
   - `External` for a personal Gmail account or early testing;
   - `Internal` only if every researcher uses the same Google Workspace.

   Keep the app in **Testing** until the implementation is ready. Add
   `finn.maunsell@gmail.com` as a **Test user**: this is required for the
   initial authorisation of the archive-owning My Drive account. It does not
   mean every later road-model user needs a Google or Cloud account.
6. In **Data Access**, choose **Add or remove scopes** and add only the
   `drive.file` scope above. The scope is required whether the app is in
   Testing or Production.
7. In **Clients**, choose **Create client**, select **Web application**, and
   name it `Road model researcher archive (HF)`. The legacy route is
   **APIs & Services → Credentials**.
8. You may create the client now, but do not add a redirect URI until the
   callback route has been implemented and its host has been confirmed. The
   intended callback is:

```text
https://finbarmaunsell-leap-road-model.hf.space/api/v1/road-module1/google-oauth/callback
```

   Google may require the callback’s domain to be pre-registered under
   **Branding → Authorised domains**, and may require proof that the project
   owns that domain. If it will not accept the Hugging Face Space domain, use a
   project-controlled custom domain for the callback instead; do not work
   around this with a broader Drive permission.
9. After the client is created, copy the OAuth client ID and client secret.
   Do not commit them.

Google may show an “unverified app” warning during Testing. Only the configured
test user should use that temporary flow. Testing refresh tokens expire after
seven days for Drive access, so do not leave the production archive in Testing.
After the workflow is tested, move it to Production and re-authorise the
archive account. The narrow `drive.file` scope is non-sensitive, but production
requirements should be checked in the console at that time.

### Long-term access and colleagues

The deployed backend will use one authorised archive-owner account to write
all submissions. Researchers and former colleagues do not need the archive
owner’s Google account, a Google Cloud account, or access to the OAuth client
or Hugging Face Secrets to run the road model.

To download archives, share the archive folder with each colleague’s own Google
account as a Viewer. They need their own Google account only for that private
folder access. An “Anyone with the link” folder is possible but is not suitable
for researcher submissions. The archive owner account must remain active and
retain Drive storage; a team-owned account or Shared Drive is the more durable
long-term option.

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
