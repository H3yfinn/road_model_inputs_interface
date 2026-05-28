# Road Model Inputs Interface (Module 1)

This repository hosts the **researcher-facing site for Road Module 1** in the APEC road transport modeling workflow.

In plain English: this site is where researchers review defaults, provide/override base-year road input values, and export a structured package that downstream road modules consume.

---

## What this site is for

`road_model_inputs_interface` is the **Module 1 input collection and packaging layer** for `leap_road_model`.

It is designed to:

- present default road-model inputs by economy/version/scenario;
- let researchers review and edit key inputs (primarily base year);
- preserve source/audit context;
- validate row keys and value constraints;
- export one flat CSV per economy in the expected Module 1 contract format.

For researcher review and handoff, the important columns are:

- `Branch Path`
- `Variable`
- `Scenario`
- `Region`
- `Scale`
- `Units`
- `Per...`
- `2022`

As long as those columns are filled in for the rows you care about, the other
columns do not need specific values. Partial files are acceptable too: blanks
and non-existent values are ignored by the loader, so you only need to fill in
the rows and fields that actually matter for the review.

If you only remember one thing: **this is the canonical handoff tool for Road Module 1 outputs**, not just a UI demo.

---

## Where it fits in the multi-repo workflow

| Repo | Role |
| --- | --- |
| `transport_model_9th_edition` | Original upstream transport model outputs. |
| `leap_transport` | Transforms/matches those outputs toward LEAP and Module 1 needs. |
| `road_model_inputs_interface` | **Module 1 writer**: collect defaults + researcher inputs, validate, export package. |
| `leap_road_model` | Reads Module 1 package and runs downstream Modules 2-7. |

---

## Core purpose of the site (researcher workflow)

1. Select **version**, **economy**, and **scenario**.
2. Load default values (static bundle first, optional backend fallback).
3. Review/edit researcher-provided values (base-year-first workflow).
4. Upload checkpoint/value files when continuing prior work.
5. Run validation checks on structure and values.
6. Export `road_module1_default_filled_inputs.csv`-style output as the Module 1 handoff.

That flat CSV is what downstream road modeling should consume.

---

## Runtime model (important)

Default operation is **static-first**:

- the frontend is expected to run as a static site;
- packaged defaults and selector metadata are loaded from `front-end/road-module1-static/`;
- backend routes are optional helpers for local workflows.

This means the site can run without a persistent server in many normal use cases.

---

## What is considered the source of truth

For full technical details (folder policy, output contract, overlays, validation behavior, and roadmap), use:

- `docs/new model/multinode_road_module1_repo_guide.md`

That guide is the detailed implementation/source-of-truth document.

---

## Quick start

### Frontend (typical)

Serve `front-end/` with any simple static server and open it in your browser.

### Optional backend

Backend is available for local helper flows (API routes, optional save/export paths), but is **not required** for static-first usage.

Install Python dependencies from `requirements.txt`, then run `back-end/run.py` if you need backend-assisted behavior.

---

## Git data policy (recommended)

To keep repository size healthy, this repo is configured to:

- **not track** heavy raw input datasets and generated backend output files under:
  - `back-end/data/`
  - `back-end/outputs/`
- **track** the frontend static defaults bundle under:
  - `front-end/road-module1-static/`

### Recommended pre-commit refresh process

Before committing/pushing Road Module 1 default updates:

1. Rebuild static defaults JSON bundle:
   - run `back-end/build_road_model_static_defaults.py`
2. Review changed files under `front-end/road-module1-static/`
3. Commit only code/docs + static JSON changes needed for the release.

This keeps Git history focused on deployable artifacts while allowing local raw-data refresh workflows.

---

## Output contract (high level)

Expected Module 1 handoff artifact:

- `road_module1_default_filled_inputs.csv`

This flat CSV is intended to carry the core row keys and the base-year value.
Downstream consumers should ignore blank cells and missing optional fields, and
they should not rely on extra columns being present.

---

## Current focus and boundaries

This repo owns Module 1 concerns:

- defaults and overlays;
- researcher input capture;
- validation and diagnostics;
- Module 1 workbook export.

This repo does **not** own downstream road simulation logic (Modules 2-7); that belongs in `leap_road_model`.

---

## Notes for contributors

- Keep the researcher workflow base-year-first unless the contract changes deliberately.
- Prefer explicit validation/reporting over silent fallbacks.
- Preserve source metadata when values are overlaid or overridden.
- Update the guide doc when behavior/contracts change.

---

## Documentation index

- Main Module 1 guide:
  - `docs/new model/multinode_road_module1_repo_guide.md`
- Backend implementation entry points:
  - `back-end/core/road_module1_defaults_workflow.py`
  - `back-end/api/routers.py`
- Frontend implementation entry points:
  - `front-end/app.js`
  - `front-end/api.js`
