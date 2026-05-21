import uvicorn

if __name__ == "__main__":
    # We point to the FastAPI instance 'app' located in api/main.py
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)