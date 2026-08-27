"""
Optional local-only router for launching leap_road_model from the Road Module 1 interface.

Not part of the static/client-side-first researcher workflow. Only available when the
backend server is running locally and leap_road_model is cloned as a sibling directory.

Endpoints:
  POST /api/v1/road-module1/run-model         — write Module 1 CSV, start subprocess, return run_id
  GET  /api/v1/road-module1/run-model-stream  — SSE stream of log lines until the run finishes
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import secrets
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from core.logger import get_logger
from core.researcher_submission_review import (
    DRIVE_FILE_SCOPE,
    archive_submission_to_drive,
    canonical_economy_code,
    create_my_drive_archive_folder,
    path_within,
    validate_version,
)

logger = get_logger(__name__)

road_run_router = APIRouter(prefix="/api/v1/road-module1", tags=["Road model runner"])

# --------------------------------------------------------------------------- #
# Paths                                                                        #
# --------------------------------------------------------------------------- #

_INTERFACE_DIR = Path(__file__).resolve().parent.parent.parent  # road_model_inputs_interface/ or /app/

# LEAP_ROAD_MODEL_DIR env var is set in the Dockerfile for server deployments.
# Falls back to the sibling repo layout used in local development.
_ROAD_MODEL_REPO = Path(
    os.getenv("LEAP_ROAD_MODEL_DIR") or str(_INTERFACE_DIR.parent / "leap_road_model")
)
_ROAD_WORKFLOW = _ROAD_MODEL_REPO / "codebase" / "road_workflow.py"
_MODULE1_INPUT_DIR = _ROAD_MODEL_REPO / "input_data" / "module1_defaults"
_ROAD_SCENARIOS_CONFIG = _ROAD_MODEL_REPO / "codebase" / "config" / "scenarios.yaml"
_STATIC_BUNDLE_DIR = _INTERFACE_DIR / "front-end" / "road-module1-static"

# In-memory registry of active subprocess handles keyed by run_id.
_active_runs: dict[str, tuple[asyncio.subprocess.Process, str, bool]] = {}
_oauth_setup_sessions: dict[str, dict[str, Any]] = {}
_OAUTH_SETUP_SESSION_SECONDS = 15 * 60


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

_DASHBOARD_DIR_RE = re.compile(r"^dashboard_\d{8}_\d{6}$")


def _find_latest_dashboard_index(economy_canonical: str) -> tuple[Path | None, str | None]:
    """Return (filesystem path, URL path) for the most recent dashboard index.html."""
    diag_dir = _ROAD_MODEL_REPO / "results" / economy_canonical / "diagnostics"
    if not diag_dir.is_dir():
        return None, None
    candidates = sorted(
        (d for d in diag_dir.iterdir() if d.is_dir() and _DASHBOARD_DIR_RE.match(d.name)),
        key=lambda d: d.name,
        reverse=True,
    )
    for d in candidates:
        idx = d / "index.html"
        if idx.exists():
            url = f"/road-results/{economy_canonical}/diagnostics/{d.name}/index.html"
            return idx, url
    return None, None


def _to_canonical_economy(economy: str) -> str:
    """Convert no-underscore economy code to canonical form: '20USA' → '20_USA'."""
    return canonical_economy_code(economy)


def _baseline_static_csv_path(economy: str, version: str) -> Path:
    """Locate the immutable browser baseline used by this run, when available."""
    compact_economy = _to_canonical_economy(economy).replace("_", "")
    return path_within(_STATIC_BUNDLE_DIR, validate_version(version), f"{compact_economy}.csv")


def _configured_scenario_labels() -> set[str]:
    """Read configured scenario labels from leap_road_model's scenarios.yaml."""
    if not _ROAD_SCENARIOS_CONFIG.exists():
        return set()
    try:
        import yaml

        with _ROAD_SCENARIOS_CONFIG.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        scenarios = data.get("scenarios") if isinstance(data, dict) else {}
        if not isinstance(scenarios, dict):
            return set()
        return {str(label).strip() for label in scenarios if str(label).strip()}
    except Exception as exc:
        logger.warning(f"Failed to read scenario config {_ROAD_SCENARIOS_CONFIG}: {exc}")
        return set()


def _normalise_projection_scenarios(rows: list[dict[str, Any]], requested: list[str] | None) -> list[str]:
    """Return ordered non-Current Accounts scenario labels for a run."""
    labels: list[str] = []
    seen: set[str] = set()
    for value in requested or []:
        text = str(value or "").strip()
        if not text or text == "Current Accounts" or text in seen:
            continue
        labels.append(text)
        seen.add(text)
    if labels:
        return labels

    for row in rows:
        text = str(row.get("Scenario") or "").strip()
        if not text or text == "Current Accounts" or text in seen:
            continue
        labels.append(text)
        seen.add(text)
    return labels or ["Target"]


def _validate_projection_scenarios(scenarios: list[str]) -> None:
    configured = _configured_scenario_labels()
    if not configured:
        return
    unknown = [scenario for scenario in scenarios if scenario not in configured]
    if unknown:
        raise ValueError(
            "Projection scenario label(s) are not configured for LEAP import: "
            f"{', '.join(unknown)}. Add them to {_ROAD_SCENARIOS_CONFIG} first."
        )


def _write_lifecycle_factors_csv(turnover_config: dict[str, Any], dest_dir: Path) -> Path | None:
    """Write a lifecycle calibration factors CSV from frontend turnover_config.

    The frontend sends rates as percentages (e.g. 5 for 5 %/yr); this converts
    them to fractions (0.05) for the road model.
    """
    _TRANSPORT_DEFAULTS = {
        "passenger": {"lower": 0.05, "upper": 0.08},
        "freight":   {"lower": 0.06, "upper": 0.10},
    }
    rows = []
    for transport_type, cfg in turnover_config.items():
        d = _TRANSPORT_DEFAULTS.get(transport_type, {"lower": 0.05, "upper": 0.08})
        lower_pct = cfg.get("lower")
        upper_pct = cfg.get("upper")
        lower = float(lower_pct) / 100.0 if lower_pct is not None else d["lower"]
        upper = float(upper_pct) / 100.0 if upper_pct is not None else d["upper"]
        rows.append({
            "project_code": "",
            "economy": "",
            "transport_type": transport_type,
            "data_year": "",
            "turnover_rate_lower": lower,
            "turnover_rate_upper": upper,
            "fit_mode": cfg.get("fit_mode", "auto"),
            "scale_age_band_age_min": 4,
            "scale_age_band_age_max": 15,
            "scale_age_band_factor": 1.0,
            "smoothing_window": 1,
            "evidence_grade": "user",
            "estimation_status": "user-configured",
            "source_note": "Configured via road model interface",
        })
    if not rows:
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = dest_dir / "lifecycle_factors_override.csv"
    headers = list(rows[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Lifecycle factors CSV written: {csv_path}")
    return csv_path


def _write_module1_csv(rows: list[dict[str, Any]], economy: str, version: str) -> Path:
    """Write completed Module 1 rows as CSV into leap_road_model's input_data directory."""
    economy_canonical = _to_canonical_economy(economy)
    version = validate_version(version)
    dest_dir = path_within(_MODULE1_INPUT_DIR, version, economy_canonical)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / f"road_module1_values_{economy_canonical}.csv"

    if not rows:
        raise ValueError("No rows provided — cannot write empty Module 1 input file.")

    headers = list(rows[0].keys())
    with dest_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Module 1 CSV written: {dest_file} ({len(rows)} rows)")
    return dest_file


def _oauth_configuration() -> tuple[str, str, str]:
    """Return required OAuth settings without ever logging their values."""
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if not all([client_id, client_secret, redirect_uri]):
        raise HTTPException(
            status_code=503,
            detail=(
                "OAuth setup is not configured. Set GOOGLE_OAUTH_CLIENT_ID, "
                "GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REDIRECT_URI as Secrets."
            ),
        )
    return client_id, client_secret, redirect_uri


def _require_oauth_setup_token(provided_token: str | None) -> None:
    configured_token = os.getenv("GOOGLE_OAUTH_SETUP_TOKEN", "")
    if not configured_token:
        raise HTTPException(status_code=503, detail="OAuth setup is disabled (GOOGLE_OAUTH_SETUP_TOKEN is not configured).")
    if not provided_token or not secrets.compare_digest(provided_token, configured_token):
        raise HTTPException(status_code=403, detail="OAuth setup token is invalid.")


def _prune_oauth_setup_sessions() -> None:
    now = time.monotonic()
    for state, session in list(_oauth_setup_sessions.items()):
        if float(session["expires_at"]) < now:
            _oauth_setup_sessions.pop(state, None)


def _exchange_google_oauth_code(*, code: str, client_id: str, client_secret: str, redirect_uri: str) -> str:
    """Exchange a one-time authorization code without writing credentials to disk."""
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    response.raise_for_status()
    refresh_token = str(response.json().get("refresh_token") or "")
    if not refresh_token:
        raise ValueError("Google did not return a refresh token. Revoke the prior grant and retry with consent.")
    return refresh_token


def _google_oauth_redirect() -> RedirectResponse:
    """Create state, store it server-side, and redirect an authenticated admin to Google."""
    client_id, _, redirect_uri = _oauth_configuration()
    _prune_oauth_setup_sessions()
    state = secrets.token_urlsafe(32)
    _oauth_setup_sessions[state] = {"expires_at": time.monotonic() + _OAUTH_SETUP_SESSION_SECONDS}
    query = urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": DRIVE_FILE_SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
    })
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=302)
    response.set_cookie(
        "road_model_oauth_setup_state", state, max_age=_OAUTH_SETUP_SESSION_SECONDS,
        secure=True, httponly=True, samesite="lax",
    )
    return response


async def _sse_generator(run_id: str):
    """
    Async generator that yields SSE-formatted events from a running subprocess.

    Reads stdout line-by-line (structured JSON log lines from road_workflow),
    then captures any stderr, then emits a final 'done' event with the return
    code and dashboard path.
    """
    entry = _active_runs.get(run_id)
    if entry is None:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Run not found'})}\n\n"
        return

    process, economy_canonical, enable_vis = entry

    try:
        # Stream stdout line by line as the model runs
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                yield f"data: {json.dumps({'type': 'log', 'source': 'stdout', 'text': text})}\n\n"

        # Drain stderr after stdout closes
        stderr_bytes = await process.stderr.read()
        if stderr_bytes:
            for line in stderr_bytes.decode("utf-8", errors="replace").splitlines():
                if line.strip():
                    yield f"data: {json.dumps({'type': 'log', 'source': 'stderr', 'text': line})}\n\n"

    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    finally:
        return_code = await process.wait()
        _active_runs.pop(run_id, None)

        dashboard_url: str | None = None
        if return_code == 0 and enable_vis:
            _, dashboard_url = _find_latest_dashboard_index(economy_canonical)

        workbook_url: str | None = None
        if return_code == 0:
            wb_candidate = (
                _ROAD_MODEL_REPO / "results" / economy_canonical
                / "module6" / f"{economy_canonical}_leap_import.xlsx"
            )
            if wb_candidate.exists():
                workbook_url = (
                    f"/road-results/{economy_canonical}/module6/{economy_canonical}_leap_import.xlsx"
                )

        lifecycle_profiles_url: str | None = None
        if return_code == 0:
            lifecycle_candidate = (
                _ROAD_MODEL_REPO / "results" / economy_canonical
                / "lifecycle_profiles" / f"{economy_canonical}_lifecycle_profiles.xlsx"
            )
            if lifecycle_candidate.exists():
                lifecycle_profiles_url = (
                    f"/road-results/{economy_canonical}/lifecycle_profiles/{economy_canonical}_lifecycle_profiles.xlsx"
                )

        reimport_csv_url: str | None = None
        if return_code == 0:
            reimport_candidate = (
                _ROAD_MODEL_REPO / "results" / economy_canonical
                / "module6" / f"{economy_canonical}_module1_reimport_reconciled.csv"
            )
            if reimport_candidate.exists():
                reimport_csv_url = (
                    f"/road-results/{economy_canonical}/module6/{economy_canonical}_module1_reimport_reconciled.csv"
                )

        yield (
            f"data: {json.dumps({'type': 'done', 'return_code': return_code, 'dashboard_url': dashboard_url, 'workbook_url': workbook_url, 'lifecycle_profiles_url': lifecycle_profiles_url, 'reimport_csv_url': reimport_csv_url})}\n\n"
        )


# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #

class RunModelRequest(BaseModel):
    economy: str
    version: str
    rows: list[dict[str, Any]]
    scenarios: list[str] | None = None
    enable_visualisations: bool = True
    turnover_config: dict[str, Any] | None = None
    has_researcher_changes: bool = False
    researcher_identity: str = ""
    original_filename: str = ""


class RunModelResponse(BaseModel):
    run_id: str
    status: str
    economy_canonical: str
    module1_csv_path: str
    archive: dict[str, Any]


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #

@road_run_router.get("/google-oauth/start", include_in_schema=False)
async def start_google_oauth_setup(
    x_road_model_oauth_setup_token: str | None = Header(default=None),
):
    """Begin the one-time, admin-protected My Drive archive authorisation."""
    _require_oauth_setup_token(x_road_model_oauth_setup_token)
    return _google_oauth_redirect()


@road_run_router.get("/google-oauth/setup", include_in_schema=False)
async def google_oauth_setup_page():
    """Serve the small one-time admin page without exposing any credentials."""
    return HTMLResponse(
        "<h1>Connect Google Drive archive</h1>"
        "<p>Enter the temporary OAuth setup token. This page is only for the archive administrator.</p>"
        "<form method='post'><label>Setup token <input type='password' name='setup_token' required autofocus></label>"
        "<button type='submit'>Continue to Google</button></form>"
    )


@road_run_router.post("/google-oauth/setup", include_in_schema=False)
async def begin_google_oauth_setup_from_page(setup_token: str = Form(...)):
    """Validate the setup token submitted by the one-time admin page."""
    _require_oauth_setup_token(setup_token)
    return _google_oauth_redirect()


@road_run_router.get("/google-oauth/callback", include_in_schema=False)
async def complete_google_oauth_setup(request: Request, code: str = "", state: str = "", error: str = ""):
    """Receive Google's redirect and stage one-time credentials for an admin to save."""
    _prune_oauth_setup_sessions()
    session = _oauth_setup_sessions.get(state)
    if not session:
        raise HTTPException(status_code=400, detail="OAuth setup session is missing or has expired. Start again.")
    if not secrets.compare_digest(request.cookies.get("road_model_oauth_setup_state", ""), state):
        raise HTTPException(status_code=403, detail="OAuth setup browser session is missing. Start again.")
    if error:
        _oauth_setup_sessions.pop(state, None)
        raise HTTPException(status_code=400, detail=f"Google OAuth was not approved: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Google OAuth callback did not contain an authorization code.")

    client_id, client_secret, redirect_uri = _oauth_configuration()
    try:
        refresh_token = _exchange_google_oauth_code(
            code=code, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri,
        )
        folder_id = create_my_drive_archive_folder(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            existing_folder_id=os.getenv("ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID", "").strip(),
        )
    except Exception as exc:
        logger.warning(f"Google OAuth archive setup failed: {exc}")
        raise HTTPException(status_code=502, detail="Google OAuth setup failed. Check server logs without exposing credentials.") from exc

    session.update({"refresh_token": refresh_token, "folder_id": folder_id, "completed": True})
    return HTMLResponse(
        "<h1>Google Drive connected</h1>"
        "<p>The archive folder was created. Click once to reveal the two values that must be "
        "saved as Hugging Face Secrets.</p>"
        f"<form method='post' action='/api/v1/road-module1/google-oauth/pending-credentials'>"
        f"<input type='hidden' name='state' value='{state}'>"
        "<button type='submit'>Reveal one-time secrets</button></form>"
    )


@road_run_router.post("/google-oauth/pending-credentials", include_in_schema=False)
async def get_pending_google_oauth_credentials(
    request: Request,
    state: str = Form(...),
    x_road_model_oauth_setup_token: str | None = Header(default=None),
):
    """Return one-time credentials to the authorised admin, then discard them from memory."""
    _prune_oauth_setup_sessions()
    session = _oauth_setup_sessions.get(state)
    if not session or not session.get("completed"):
        raise HTTPException(status_code=404, detail="Completed OAuth setup credentials were not found.")
    cookie_state = request.cookies.get("road_model_oauth_setup_state", "")
    if not secrets.compare_digest(cookie_state, state):
        _require_oauth_setup_token(x_road_model_oauth_setup_token)
    _oauth_setup_sessions.pop(state, None)
    return HTMLResponse(
        "<h1>Save these as Hugging Face Secrets now</h1>"
        f"<p><strong>GOOGLE_DRIVE_ARCHIVE_REFRESH_TOKEN</strong></p><pre>{session['refresh_token']}</pre>"
        f"<p><strong>ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID</strong></p><pre>{session['folder_id']}</pre>"
        "<p>These values have now been removed from the server. Do not share this page.</p>"
    )

@road_run_router.post("/run-model", response_model=RunModelResponse)
async def start_road_model_run(payload: RunModelRequest):
    """
    Write the current Module 1 researcher values to leap_road_model's input_data directory,
    then launch road_workflow.py as a subprocess.

    Returns a run_id to use with the /run-model-stream SSE endpoint.
    """
    if not _ROAD_WORKFLOW.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"road_workflow.py not found at {_ROAD_WORKFLOW}. "
                "Ensure leap_road_model is cloned as a sibling of this repo."
            ),
        )

    try:
        economy_canonical = _to_canonical_economy(payload.economy)
        version = validate_version(payload.version)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        projection_scenarios = _normalise_projection_scenarios(payload.rows, payload.scenarios)
        _validate_projection_scenarios(projection_scenarios)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        csv_path = _write_module1_csv(payload.rows, payload.economy, version)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to write Module 1 CSV: {exc}") from exc

    run_id = str(uuid.uuid4())
    archive_result: dict[str, Any] = {"attempted": False, "success": None, "message": "No researcher changes detected; submission was not archived."}
    if payload.has_researcher_changes:
        archive_result = archive_submission_to_drive(
            rows=payload.rows,
            economy=economy_canonical,
            version=version,
            run_id=run_id,
            researcher_identity=payload.researcher_identity,
            original_filename=payload.original_filename,
            baseline_path=_baseline_static_csv_path(payload.economy, version),
        )
        if archive_result.get("success"):
            logger.info(f"Researcher submission archived before road run: {archive_result.get('submission_id')}")
        else:
            logger.warning(f"Researcher submission was not archived: {archive_result.get('message')}")

    lifecycle_factors_path: Path | None = None
    if payload.turnover_config:
        try:
            dest_dir = path_within(_MODULE1_INPUT_DIR, version, economy_canonical)
            lifecycle_factors_path = _write_lifecycle_factors_csv(payload.turnover_config, dest_dir)
        except Exception as exc:
            logger.warning(f"Failed to write lifecycle factors override: {exc}")

    cmd = [
        sys.executable,
        str(_ROAD_WORKFLOW),
        economy_canonical,
        "--module1-defaults-dir",
        str(_MODULE1_INPUT_DIR),
        "--module1-defaults-version",
        version,
        "--scenarios",
        *projection_scenarios,
    ]
    if payload.enable_visualisations:
        cmd.append("--vis")
    if lifecycle_factors_path and lifecycle_factors_path.exists():
        cmd.extend(["--lifecycle-factors-path", str(lifecycle_factors_path)])

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_ROAD_MODEL_REPO),
        )
        _active_runs[run_id] = (process, economy_canonical, payload.enable_visualisations)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start road_workflow: {exc}") from exc

    logger.info(
        f"Road workflow started: run_id={run_id} economy={economy_canonical} pid={process.pid}"
    )

    return RunModelResponse(
        run_id=run_id,
        status="started",
        economy_canonical=economy_canonical,
        module1_csv_path=str(csv_path),
        archive=archive_result,
    )


@road_run_router.get("/run-model-stream")
async def stream_road_model_run(run_id: str):
    """
    SSE endpoint — streams log output for a running road_workflow job.

    Each event is a JSON object with a 'type' field:
      { type: 'log',   source: 'stdout'|'stderr', text: '...' }
      { type: 'done',  return_code: int, dashboard_path: str|null }
      { type: 'error', message: '...' }

    Connect immediately after calling POST /run-model.
    """
    if run_id not in _active_runs:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or already finished.")

    return StreamingResponse(
        _sse_generator(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
