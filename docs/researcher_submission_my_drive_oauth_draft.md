# My Drive OAuth Archive Setup

> Status: deployed and successfully tested against Finn's My Drive on
> 2026-08-27.

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

The app also enforces its own folder allow-list:

- the one-time OAuth setup creates the archive root folder;
- the backend stores that created folder ID as a Hugging Face Secret;
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

   For the initial Testing setup, a logo, homepage, privacy-policy URL,
   terms-of-service URL, and authorised domains are not needed. Save the page.
   The developer-contact field is separate from the support email and is
   required even when both addresses are the same.
5. In **Audience**, choose the appropriate audience:
   - `External` for a personal Gmail account or early testing;
   - `Internal` only if every researcher uses the same Google Workspace.

   For the initial connection, keep the app in **Testing** and add
   `finn.maunsell@gmail.com` as a **Test user**: this is required for the
   initial authorisation of the archive-owning My Drive account. It does not
   mean every later road-model user needs a Google or Cloud account.
6. In **Data Access**, choose **Add or remove scopes** and add only the
   `drive.file` scope above. The scope is required whether the app is in
   Testing or Production.
7. In **Clients**, choose **Create client**, select **Web application**, and
   name it `Road model researcher archive (HF)`. The legacy route is
   **APIs & Services → Credentials**.
8. Add this authorised redirect URI to the OAuth web client:

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

### Move to Production after the first successful test

Testing refresh tokens expire after seven days. To keep the archive running
long-term, return to **Branding** and enter these exact values before clicking
**Audience → Publish app**:

| Branding field | Value |
|---|---|
| Application home page | `https://finbarmaunsell-leap-road-model.hf.space/` |
| Application privacy policy link | `https://finbarmaunsell-leap-road-model.hf.space/privacy.html` |
| Authorised domains | `finbarmaunsell-leap-road-model.hf.space` |
| Developer contact information | `finn.maunsell@gmail.com` |

Leave the logo and Terms of Service link blank. A logo is not needed for this
small internal-use archive and can trigger additional verification requirements.
The privacy notice explains the model archive, its narrow Drive permission, and
the link-sharing policy. Save Branding, publish the app from Audience, then
reconnect the archive account using the one-time setup flow to replace the
Testing refresh token.

Google may show an “unverified app” warning during Testing. Only the configured
test user should use that temporary flow. Testing refresh tokens expire after
seven days for Drive access. After the initial test, move the app to Production
and reconnect the archive account to obtain a long-lived refresh token. The
narrow `drive.file` scope is non-sensitive.

### Long-term access and colleagues

The deployed backend will use one authorised archive-owner account to write
all submissions. Researchers and former colleagues do not need the archive
owner’s Google account, a Google Cloud account, or access to the OAuth client
or Hugging Face Secrets to run the road model.

For simple long-term access, set the archive folder to **Anyone with the link →
Viewer**. Former colleagues can then download files without your Google account,
a Google Cloud account, or even their own Google account. This is intentionally
not private: anyone who obtains the link can theoretically download the
researcher submissions. That is acceptable here because the submissions are not
treated as sensitive or especially useful outside the model workflow; do not use
this setting if that changes.

The archive owner account must remain active. Its My Drive storage is the
intended archive location and has ample capacity, so storage quota is not a
reason to move this workflow to a Shared Drive.

## Hugging Face Secrets

Add these as **Secrets**, not Variables:

| Name | Value |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth web-client ID from Google Cloud |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth web-client secret |
| `GOOGLE_OAUTH_REDIRECT_URI` | The exact callback URL above |
| `GOOGLE_OAUTH_SETUP_TOKEN` | A newly generated, long random admin-only setup password |
| `GOOGLE_DRIVE_ARCHIVE_REFRESH_TOKEN` | Generated once by the authorised archive-account flow |
| `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID` | App-created My Drive archive folder ID returned by setup |

The setup token and refresh token are as sensitive as passwords. Never paste
either into Git, browser JavaScript, chat, or a public HF Variable.

## One-time deployment setup

1. Add the three client settings and a new random `GOOGLE_OAUTH_SETUP_TOKEN`
   as Hugging Face **Secrets**. Do not add a refresh token or folder ID yet.
2. Set `GOOGLE_OAUTH_REDIRECT_URI` to the exact callback configured on the
   OAuth client. Deploy the app.
3. Open this one-time admin page in the deployed Space:

```text
https://finbarmaunsell-leap-road-model.hf.space/api/v1/road-module1/google-oauth/setup
```

   Enter the setup token. The page redirects to Google; approve the
   `drive.file` consent using the My Drive account that should own archives.
4. On the first connection, the callback creates an app-owned `Road model
   researcher submissions` folder in that account’s My Drive. On a deliberate
   reconnection, it verifies and keeps using the existing configured folder.
   It stages the refresh token and folder ID in server memory for 15 minutes
   only.
5. On the callback page, click **Reveal one-time secrets**. It shows the two
   values once in the same browser session, then removes them from server
   memory.
6. Immediately replace `GOOGLE_DRIVE_ARCHIVE_REFRESH_TOKEN` with the shown
   value. Keep `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID` unchanged unless this
   is the first connection. Restart/redeploy the Space. Remove
   `GOOGLE_OAUTH_SETUP_TOKEN` afterwards; it is only needed for first-time
   setup or a deliberate reconnection.

## Verified deployment test

On 2026-08-27, the live Hugging Face Space archived a controlled `20_USA`
submission with one changed reconciliation-weight value. The archive created
both the complete canonical-long CSV and its metadata JSON, and the model run
completed. The test submission is clearly labelled `REAL OAUTH ARCHIVE TEST —
revert/not for source promotion.`

## References

- [Google Drive API OAuth scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Google OAuth authorization](https://developers.google.com/identity/protocols/oauth2)
- [Hugging Face Space Secrets](https://huggingface.co/docs/hub/main/spaces-overview)
