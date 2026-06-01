import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Disable reload in production (HF Spaces, any server).
    # For local development, set RELOAD=true in your environment.
    reload = os.environ.get("RELOAD", "false").lower() == "true"
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=reload)
