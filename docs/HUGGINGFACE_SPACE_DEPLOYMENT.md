# Hugging Face Space deployment

This repository can be run locally with `python back-end/run.py` and deployed
to a Hugging Face Space. The normal GitHub history and the Hugging Face Space
history do not have to be the same.

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

Repeat the clean-snapshot method after committing changes to the local
repository. The Space will rebuild after the push. Check the Space page and
its build logs if the old version remains visible for a few minutes.

For a Space whose `main` branch is a normal descendant of the local branch and
whose Git history contains no rejected large blobs, a regular push is enough:

```powershell
git remote set-url hf https://huggingface.co/spaces/<OWNER>/<SPACE>
git push hf main
```

## Deployment checklist

- `hf auth login` completed with a Write token.
- The `hf` remote URL contains no token.
- Local `git status` is clean and the intended changes are committed.
- Current files do not exceed Hugging Face's 10 MiB ordinary-Git limit.
- Documentation-only binary assets are omitted or stored using the Hugging Face
  binary-storage mechanism.
- The Space page has rebuilt successfully after the push.
