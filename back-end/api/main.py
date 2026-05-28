from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Imported data_ingestor alongside the router to handle eager loading
from api.routers import router, road_router, data_ingestor
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
