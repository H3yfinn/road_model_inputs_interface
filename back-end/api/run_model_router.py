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
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.logger import get_logger

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

# In-memory registry of active subprocess handles keyed by run_id.
_active_runs: dict[str, tuple[asyncio.subprocess.Process, str, bool]] = {}


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _to_canonical_economy(economy: str) -> str:
    """Convert no-underscore economy code to canonical form: '20USA' → '20_USA'."""
    if "_" in economy:
        return economy
    match = re.match(r"^(\d+)([A-Za-z].*)$", economy)
    return f"{match.group(1)}_{match.group(2)}" if match else economy


def _write_module1_csv(rows: list[dict[str, Any]], economy: str, version: str) -> Path:
    """Write completed Module 1 rows as CSV into leap_road_model's input_data directory."""
    economy_no_underscore = economy.replace("_", "")
    dest_dir = _MODULE1_INPUT_DIR / version / economy_no_underscore
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / f"road_module1_default_filled_inputs_{economy_no_underscore}.csv"

    if not rows:
        raise ValueError("No rows provided — cannot write empty Module 1 input file.")

    headers = list(rows[0].keys())
    with dest_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Module 1 CSV written: {dest_file} ({len(rows)} rows)")
    return dest_file


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
            candidate = (
                _ROAD_MODEL_REPO / "results" / economy_canonical
                / "diagnostics" / "dashboard" / "index.html"
            )
            if candidate.exists():
                dashboard_url = (
                    f"/road-results/{economy_canonical}/diagnostics/dashboard/index.html"
                )

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

        yield (
            f"data: {json.dumps({'type': 'done', 'return_code': return_code, 'dashboard_url': dashboard_url, 'workbook_url': workbook_url})}\n\n"
        )


# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #

class RunModelRequest(BaseModel):
    economy: str
    version: str
    rows: list[dict[str, Any]]
    enable_visualisations: bool = True


class RunModelResponse(BaseModel):
    run_id: str
    status: str
    economy_canonical: str
    module1_csv_path: str


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #

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

    economy_canonical = _to_canonical_economy(payload.economy)

    try:
        csv_path = _write_module1_csv(payload.rows, payload.economy, payload.version)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to write Module 1 CSV: {exc}") from exc

    cmd = [sys.executable, str(_ROAD_WORKFLOW), economy_canonical]
    if payload.enable_visualisations:
        cmd.append("--vis")

    run_id = str(uuid.uuid4())
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
