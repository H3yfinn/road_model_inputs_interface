---
description: Launch the road model inputs interface (FastAPI backend + static frontend) and verify it is serving at http://localhost:8000, then confirm the road model subprocess is importable.
---

## Launch

From `back-end/`:

```bash
cd C:\Users\Work\github\road_model_inputs_interface\back-end && python run.py
```

Run in the background. Verify the server is up:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
```

A `200` means the site is live at **http://localhost:8000**.

## Verify road model backend

After the server is up, confirm the road model (the subprocess backend) has no syntax errors:

```bash
C:\Users\Work\github\leap_road_model\.venv\Scripts\python.exe -m py_compile C:\Users\Work\github\leap_road_model\codebase\road_workflow.py
```

No output = clean. If it errors, fix the syntax issue before reporting success.

## Dependencies

```bash
pip install fastapi uvicorn pandas numpy scipy openpyxl pydantic python-multipart httpx
```

## Notes

- Root `index.html` redirects to `front-end/index.html`.
- Port can be overridden with the `PORT` env var; hot reload with `RELOAD=true`.
- `leap_road_model` must be a sibling directory — the interface invokes `road_workflow.py` as a subprocess.
