# Hugging Face Space deployment

This repository can be run locally with `python back-end/run.py` and deployed
to a Hugging Face Space. The normal GitHub history and the Hugging Face Space
history do not have to be the same.

## What is actually deployed

The Hugging Face Space is the `road_model_inputs_interface` repository. The
`leap_road_model` repository is **not** a Git submodule and is not copied into
the Space repository. Instead, the Space's Docker build clones it from GitHub:

```text
Hugging Face Space repository
  = road_model_inputs_interface (frontend + backend + Module 1 static data)
                         |
                         | Dockerfile: git clone during image build
                         v
                    /app/leap_road_model
                         |
                         | backend writes Module 1 CSV and launches
                         | codebase/road_workflow.py
                         v
                    model outputs / LEAP workbook
```

The mechanism is defined in `Dockerfile`:

- `LEAP_ROAD_MODEL_REPO` defaults to
  `https://github.com/asia-pacific-energy-research-centre/leap_road_model`.
- `LEAP_ROAD_MODEL_REF` defaults to `main`; it can be set to a commit SHA for
  a reproducible deployment.
- The clone is placed at `/app/leap_road_model`.
- `LEAP_ROAD_MODEL_DIR` tells the interface backend where that clone lives.
- The backend writes researcher-exported Module 1 values to
  `/app/leap_road_model/input_data/module1_defaults` and starts
  `/app/leap_road_model/codebase/road_workflow.py` when the user presses **Run
  Road Model**.
- Results are written under `/app/leap_road_model/results` and served back by
  the interface.

This differs from local development, where the backend expects the two sibling
repositories:

```text
github/
  road_model_inputs_interface/
  leap_road_model/
```

The local backend falls back to the sibling `leap_road_model` directory when
`LEAP_ROAD_MODEL_DIR` is not set.

`leap_road_model_sha.txt` is a Docker cache-busting input. It does not contain
the model repository. The GitHub deployment workflow writes the current
`leap_road_model` commit SHA into that file before pushing the Space snapshot,
so the Docker build fetches a fresh model clone instead of reusing a stale
Docker layer.

There are therefore two independent codebases in one running container. A
change to the interface normally requires a new interface deployment. A
change to model Modules 2-7 must first be pushed to the public
`leap_road_model` GitHub repository; the next Space build then clones that
updated model. The SHA file triggers Docker to rebuild the clone layer, but
with `LEAP_ROAD_MODEL_REF=main` it is a cache marker rather than a version pin.

## Authentication

Authenticate once on the deployment machine with a Hugging Face user token
that has `Write` permission:

```powershell
hf auth login
```

Do not put the token in a Git remote URL or commit it to the repository. A
Space/deployment token shown in the Hugging Face web settings is not
automatically available to local Git. If its full value was not saved when it
was created, create a separate local-upload token.

## Why a normal push may fail

This Space has previously been initialized from a standalone Hugging Face
deployment snapshot. It therefore may have no common ancestor with the local
`main` branch. A normal push can fail with `fetch first`, even when the local
commits are the intended deployment.

Hugging Face also rejects ordinary Git pushes containing files larger than
10 MiB and may reject binary assets such as documentation PNGs unless they are
stored through its Xet/LFS storage. The repository's current files are below
the size limit, but old large blobs can remain in local Git history. Splitting
the current CSV does not remove those historical blobs.

## Deploy the current repository without LFS

Use this clean-snapshot method when the Space has unrelated history or the
normal push is rejected for historical large files. It creates a temporary,
single-commit copy from the current `HEAD`; it does not rewrite the normal
repository or GitHub history.

First confirm the intended local changes are committed:

```powershell
cd C:\Users\Work\github\road_model_inputs_interface
git status
git log -1 --oneline
```

Then replace the owner and Space name in the commands below:

```powershell
$snapshot = Join-Path $env:TEMP ('hf_upload_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $snapshot | Out-Null
$prefix = $snapshot + '\\'
git checkout-index --all --prefix="$prefix"

git init -b main $snapshot
git -C $snapshot config user.name 'HF deployment snapshot'
git -C $snapshot config user.email 'hf-deployment@local'
git -C $snapshot add -A

# Optional: omit documentation-only binary assets that the Space does not need.
if (Test-Path (Join-Path $snapshot 'docs\new model\End-to-end road model workflow 8062026.png')) {
    git -C $snapshot rm --cached -- 'docs/new model/End-to-end road model workflow 8062026.png'
}

git -C $snapshot commit -m 'deploy current road model interface'
git -C $snapshot remote add hf https://huggingface.co/spaces/<OWNER>/<SPACE>
git -C $snapshot push hf main:main --force
```

The force push is intentionally scoped to the temporary snapshot's `hf`
remote. Never use it against `origin` or the normal GitHub repository unless
rewriting that repository's history is explicitly intended.

## Updating the existing Space later

The preferred update path is:

1. Commit interface changes in `road_model_inputs_interface`.
2. Push `main` to the GitHub repository.
3. Let `.github/workflows/sync_to_hf.yml` fetch the current public
   `leap_road_model` commit SHA, write `leap_road_model_sha.txt`, create an
   orphan deployment commit, remove documentation-only files that Hugging Face
   rejects, and force-push the snapshot to the Space.
4. The Space rebuilds its Docker image. During that build, Docker clones the
   `leap_road_model` GitHub repository at `main`.

The workflow needs a GitHub repository secret named `HF_TOKEN` with Write
permission for the Space. The token belongs in GitHub Actions Secrets, never
in a committed file or a permanent local remote URL. The workflow may use the
secret in its ephemeral CI remote URL while the job runs. If the model code must be pinned, change
the Docker build reference strategy and ensure the cache-busting SHA is kept
in sync.

Repeat the clean-snapshot method below only when manually deploying from a
local machine or when repairing an existing Space whose history is unrelated.
The Space will rebuild after the push. Check the Space page and its build logs
if the old version remains visible for a few minutes.

For a Space whose `main` branch is a normal descendant of the local branch and
whose Git history contains no rejected large blobs, a regular push is enough:

```powershell
git remote set-url hf https://huggingface.co/spaces/<OWNER>/<SPACE>
git push hf main
```

## First-time handoff to a new owner or Space

Use this checklist when the project is transferred to another person, HF
account, or Space name.

### 1. Confirm the two GitHub repositories

The new maintainer needs access to:

- the interface repository, which becomes the HF Space contents; and
- the public `leap_road_model` repository, which the Docker build clones.

If the model repository is forked or moved, update
`LEAP_ROAD_MODEL_REPO` in `Dockerfile`. The current Dockerfile assumes that the
model repository is public; a private model repository would require a
different authenticated clone design.

### 2. Create the new Hugging Face Space

In Hugging Face:

1. Create a new Space under the new account or organization.
2. Choose **Docker** as the SDK.
3. Use the target Space name in the deployment configuration below.
4. The Space can start empty or contain an automatically created deployment
   commit; the orphan-snapshot workflow can replace that history.

### 3. Configure the GitHub Actions secret

Create a Hugging Face user token with Write permission for the new Space, then
add it to the **interface GitHub repository** as:

```text
Settings → Secrets and variables → Actions → New repository secret
Name: HF_TOKEN
Value: <the token value>
```

Never commit the token or put it in a permanent remote URL. The token is used
only by the GitHub Actions deployment job.

### 4. Change the deployment target

Edit `.github/workflows/sync_to_hf.yml` and change this line to the new HF
owner and Space:

```text
git remote add hf https://<OWNER>:$HF_TOKEN@huggingface.co/spaces/<OWNER>/<SPACE>
```

The workflow currently also assumes the deployment branch is `main` and uses
an orphan commit. Keep the orphan push unless the new Space is deliberately
managed with a shared Git history.

The `Dockerfile` normally does not need the HF owner/name changed. It only
needs updating if the `leap_road_model` GitHub repository or branch changes.

### 5. Deploy and verify

Push the configured workflow and interface changes to the interface GitHub
repository's `main` branch. The workflow will:

1. fetch the current `leap_road_model` HEAD SHA;
2. write it to `leap_road_model_sha.txt`;
3. create a clean orphan deployment commit;
4. remove documentation-only files that HF rejects as binary assets; and
5. force-push the snapshot to the new Space.

Then open the Space's **Logs** tab and confirm that Docker:

- clones `leap_road_model` successfully;
- installs both `requirements.txt` files;
- starts `back-end/run.py`; and
- reports a healthy `/health` endpoint.

Finally test one economy in the browser, download its Module 1 CSV, and run a
small model case before treating the new Space as operational.

### Configuration summary

| Item | Where to change it | Purpose |
|---|---|---|
| HF destination | `.github/workflows/sync_to_hf.yml` | Account, organization, and Space receiving deployment snapshots |
| HF write credential | GitHub Actions secret `HF_TOKEN` | Allows the workflow to push to the Space |
| Model repository | `Dockerfile` → `LEAP_ROAD_MODEL_REPO` | GitHub source cloned into the container |
| Model branch/ref | `Dockerfile` → `LEAP_ROAD_MODEL_REF` | Model version used by the Docker build |
| Docker port | `Dockerfile` → `PORT` | Must remain compatible with HF Spaces, normally `7860` |
| Runtime model path | `Dockerfile` → `LEAP_ROAD_MODEL_DIR` | Location used by the interface backend inside the container |

## Deployment checklist

- `hf auth login` completed with a Write token.
- The `hf` remote URL contains no token.
- Local `git status` is clean and the intended changes are committed.
- Current files do not exceed Hugging Face's 10 MiB ordinary-Git limit.
- Documentation-only binary assets are omitted or stored using the Hugging Face
  binary-storage mechanism.
- The Space page has rebuilt successfully after the push.
