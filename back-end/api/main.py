from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
        logger.warning(f"APEC database not found — energy-model tab will be unavailable. ({e})")
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
