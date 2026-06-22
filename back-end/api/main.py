from contextlib import asynccontextmanager
import os
import re
from pathlib import Path
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
import uvicorn

# Imported data_ingestor alongside the router to handle eager loading
from api.routers import router, road_router, data_ingestor
from api.run_model_router import road_run_router
from core.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to handle startup and shutdown events.
    Loads the APEC database eagerly at startup to ensure thread-safety 
    and prevent race conditions under concurrent initialization requests.
    """
    logger.info("API boot sequence initiated: Eagerly pre-loading APEC macroeconomic database...")
    try:
        data_ingestor.load_data()
        logger.info("APEC macroeconomic database successfully cached in memory.")
    except FileNotFoundError as e:
        # Data file not present (e.g. on HF Spaces before data is committed).
        # The energy-model tab will be unavailable, but Road Module 1 still works.
        logger.debug(f"APEC database not found — energy-model tab will be unavailable. ({e})")
    except Exception as e:
        logger.critical(f"Critical failure during API boot sequence: Database failed to load. Details: {str(e)}", exc_info=True)
        raise e
    yield
    logger.info("API shutdown sequence initiated: Releasing allocated system resources...")

app = FastAPI(
    title="Multinode Energy Modeler API",
    description="Optimization backend for reconciling bottom-up user weights with top-down APEC macroeconomic data.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (including 'null' from local files)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

app.include_router(router)
app.include_router(road_router)
app.include_router(road_run_router)


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    """Cheap readiness endpoint for container platforms such as HF Spaces."""
    return JSONResponse({"status": "ok"})

# --- STATIC FILE SERVING ---
# _interface_dir works for both layouts:
#   local:     .../road_model_inputs_interface/back-end/api/main.py  → parent×3
#   HF Spaces: /app/back-end/api/main.py                             → parent×3 = /app/
_interface_dir = Path(__file__).resolve().parent.parent.parent

# leap_road_model path: env var wins (set in Dockerfile), falls back to sibling repo for local dev.
_road_model_repo = Path(
    os.getenv("LEAP_ROAD_MODEL_DIR") or str(_interface_dir.parent / "leap_road_model")
)

# Serve leap_road_model results over HTTP so the dashboard can be opened from the browser.
_results_dir = _road_model_repo / "results"
_results_dir.mkdir(parents=True, exist_ok=True)
app.mount("/road-results", StaticFiles(directory=str(_results_dir)), name="road-results")


_DASHBOARD_DIR_RE = re.compile(r"^dashboard_\d{8}_\d{6}$")


def _latest_dashboard_file(economy_dir: Path, filename: str) -> tuple[Path | None, str | None]:
    """Find filename in the most recent timestamped dashboard dir.

    Returns (absolute path, relative path from economy_dir) or (None, None).
    """
    diag_dir = economy_dir / "diagnostics"
    if not diag_dir.is_dir():
        return None, None
    candidates = sorted(
        (d for d in diag_dir.iterdir() if d.is_dir() and _DASHBOARD_DIR_RE.match(d.name)),
        key=lambda d: d.name,
        reverse=True,
    )
    for d in candidates:
        p = d / filename
        if p.exists():
            return p, f"diagnostics/{d.name}/{filename}"
    return None, None


@app.get("/api/v1/road-results-info/{economy}", include_in_schema=False)
async def road_results_info(economy: str) -> JSONResponse:
    """Return existence and modification times for key result files in an economy."""
    import time
    economy_dir = _results_dir / economy
    info = {"economy": economy, "results_dir": str(_results_dir), "files": {}}

    # Dashboard — resolve to the latest timestamped dashboard dir
    dash_path, dash_rel = _latest_dashboard_file(economy_dir, "module6.html")
    if dash_path and dash_rel:
        mtime = dash_path.stat().st_mtime
        info["files"][dash_rel] = {
            "exists": True,
            "modified": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(mtime)),
            "size_kb": round(dash_path.stat().st_size / 1024, 1),
        }
    else:
        info["files"]["diagnostics/dashboard/module6.html"] = {"exists": False}

    for rel in [f"module6/T8_fuel_allocation.csv", f"module6/T11_leap_ready.csv"]:
        p = economy_dir / rel
        if p.exists():
            mtime = p.stat().st_mtime
            info["files"][rel] = {
                "exists": True,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(mtime)),
                "size_kb": round(p.stat().st_size / 1024, 1),
            }
        else:
            info["files"][rel] = {"exists": False}
    return JSONResponse(info)

_road_model_docs_dir = _road_model_repo / "docs" / "new model"

_MD_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
  <style>
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         margin:0;padding:0;background:#f5f5f5;color:#333;line-height:1.6}}
    .page-wrap{{max-width:860px;margin:0 auto;padding:32px 24px 60px}}
    h1,h2,h3,h4{{color:#1a237e}}
    h1{{border-bottom:2px solid #e0e0e0;padding-bottom:10px}}
    h2{{border-bottom:1px solid #e0e0e0;padding-bottom:6px}}
    a{{color:#1a237e}}
    pre{{background:#f0f4ff;border:1px solid #c5cae9;border-radius:6px;padding:14px;overflow-x:auto}}
    code{{background:#f0f4ff;border-radius:3px;padding:2px 5px;font-size:.9em}}
    pre code{{background:none;padding:0}}
    blockquote{{border-left:4px solid #7986cb;margin:0;padding:8px 16px;background:#e8eaf6;border-radius:0 4px 4px 0}}
    img{{max-width:100%;height:auto;border-radius:6px;border:1px solid #e0e0e0;margin:12px 0;display:block}}
    table{{border-collapse:collapse;width:100%}}
    th,td{{border:1px solid #e0e0e0;padding:8px 12px;text-align:left}}
    th{{background:#e8eaf6}}
    tr:nth-child(even){{background:#f5f5f5}}
  </style>
</head>
<body>
<div class="page-wrap" id="content"></div>
<script>
const md = {content_json};
document.getElementById('content').innerHTML = marked.parse(md);
</script>
</body>
</html>
"""

_DOC_TITLE_OVERRIDES = {
    "road_transport_model_overview": "Road Transport Model Overview",
    "road_transport_model_simplified": "Road Transport Model Guide",
    "road_transport_model_detailed": "Road Transport Model Workflow",
}


@app.get("/road-model-docs/{filepath:path}", include_in_schema=False, response_model=None)
async def serve_road_model_docs(filepath: str) -> HTMLResponse | FileResponse:
    if not _road_model_docs_dir.exists():
        raise HTTPException(status_code=404, detail="Docs directory not available")
    full_path = (_road_model_docs_dir / filepath).resolve()
    if not full_path.is_relative_to(_road_model_docs_dir.resolve()):
        raise HTTPException(status_code=403)
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404)
    if filepath.lower().endswith(".md"):
        content = full_path.read_text(encoding="utf-8-sig")
        title = _DOC_TITLE_OVERRIDES.get(
            full_path.stem,
            full_path.stem.replace("_", " ").title(),
        )
        html = _MD_PAGE_TEMPLATE.format(
            title=title,
            content_json=json.dumps(content),
        )
        return HTMLResponse(html)
    return FileResponse(str(full_path))

# Serve the frontend — must be last so API routes take precedence.
_frontend_dir = _interface_dir / "front-end"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")

# --- GLOBAL EXCEPTION HANDLERS ---

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Catches data-related errors (e.g., missing database records, bad years)."""
    logger.error(f"Data Error on {request.url}: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content={"error": "Bad Request", "detail": str(exc)}
    )

@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    """Catches mathematical or optimization engine failures."""
    logger.error(f"Optimization Engine Error on {request.url}: {str(exc)}")
    return JSONResponse(
        status_code=422,
        content={"error": "Unprocessable Entity", "detail": str(exc)}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Safety net for any completely unhandled server crashes."""
    logger.critical(f"Unhandled Server Crash on {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred."}
    )

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
