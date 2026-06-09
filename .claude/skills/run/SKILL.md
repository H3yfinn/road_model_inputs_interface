---
description: Launch the road model inputs interface (FastAPI backend + static frontend) and verify it is serving at http://localhost:8000
---

## Launch

From the repo root (`C:\Users\Work\github\road_model_inputs_interface`):

```bash
cd back-end && python run.py
```

This starts uvicorn on port 8000 (default). Run it in the background, then verify with:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
```

A `200` means the server is up and the site is accessible at **http://localhost:8000**.

## Dependencies

All deps are in `requirements.txt` at the repo root. If `uvicorn` is missing:

```bash
pip install fastapi uvicorn pandas numpy scipy openpyxl pydantic python-multipart httpx
```

## Notes

- The root `index.html` redirects to `front-end/index.html`.
- Port can be overridden with the `PORT` env var.
- Hot reload is off by default; set `RELOAD=true` for development.
