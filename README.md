---
title: Road Model Inputs Interface
emoji: 🚗
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

## Road Model Inputs Interface

> **Hugging Face Spaces deployment config** — the table above is required by HF Spaces and contains the app metadata. [![Hugging Face Spaces](https://img.shields.io/badge/HuggingFace-Spaces-orange)](https://huggingface.co/spaces/H3yfinn/road_model_inputs_interface)

This repository hosts the researcher-facing interface and source-data package
for Road Module 1 in the APEC road transport model workflow.

In plain English: this site shows researchers the default road-model input rows,
lets them fill values and comments without changing the row structure, and
exports a Module 1 package for `leap_road_model`.

## Overview diagrams

![End-to-end road model workflow](docs/new%20model/End-to-end%20road%20model%20workflow%208062026.png)

## What this site is for

`road_model_inputs_interface` is the Module 1 input collection and packaging
layer for `leap_road_model`.

It is designed to:

- build default values from documented files in `back-end/data/road_model/`;
- present default rows by economy and scenario;
- let researchers review and edit values, mainly for the base year;
- capture source notes and comments for researcher-provided overrides;
- validate row keys and simple value constraints; and
- export one flat CSV per economy in the Module 1 contract format.

The target handoff format is a long CSV with these core columns:

```text
Economy, Scenario, Branch Path, Variable, Year, Value, Units, Source, Comment, Input Status
```

Generated per-economy files use stable underscore economy codes and overwrite in
place:

```text
road_module1_values_<ECONOMY>.csv
road_module1_values_20_USA.csv
```

Researchers can edit value/comment/source fields. They should not create rows or
change key columns such as `Branch Path`, `Variable`, `Scenario`, `Economy`, or
`Year`.

Vehicle-type stock splits use LEAP's existing `Stock Share` rows, not custom
Module 1 variable names. The canonical split rows are:

```text
Demand\Freight road\Trucks          Stock Share
Demand\Freight road\LCVs            Stock Share
Demand\Passenger road\Motorcycles   Stock Share
Demand\Passenger road\Buses         Stock Share
Demand\Passenger road\LPVs          Stock Share
```

These values are LEAP-style percentages and each transport group should sum to
100.

## Repo setup — both repos must be siblings

Both repos must be cloned into the **same parent folder**:

```text
parent_folder/
    road_model_inputs_interface/  ← this repo
    leap_road_model/              ← sibling repo
```

Keep both repos open together in one VS Code multi-root workspace
(`File → Add Folder to Workspace`). Each repo uses its own `.venv`.

`leap_road_model` reads Module 1 outputs from:

```text
back-end/outputs/road_module1_defaults/
```

These outputs are committed to this repo and are always up to date without
running the website. `leap_road_model` can run its full Modules 2-7 pipeline
offline using those static files — see `scripts/offline_workflow.py` in the
sibling repo.

## Where it fits in the multi-repo workflow

| Repo | Role |
| --- | --- |
| `transport_model_9th_edition` | Original upstream transport model outputs. |
| `leap_transport` | Near-term source of processed transport outputs close to LEAP branch structure. |
| `road_model_inputs_interface` | Module 1 writer: source files, defaults, UI, validation, researcher export. |
| `leap_road_model` | Reads the Module 1 package and runs Modules 2-7. |

## Source of truth

Default values must come from files in:

```text
back-end/data/road_model/
```

If required default files are missing, generation should fail. Researcher
uploads are for filling existing rows, not for replacing the default data source.

The full contract and roadmap are in:

```text
docs/new model/multinode_road_module1_repo_guide.md
```

## Runtime model

Default operation is static-first:

- generated UI data are served from `front-end/road-module1-static/`;
- the frontend can run as a static site;
- backend routes are optional helpers for local validation and model runs.

The static CSV bundle is a UI artifact, not a separate source of truth. It uses
the same long-row format as the downstream Module 1 package and should be
regenerated from `back-end/data/road_model/`.

## Quick start

### Frontend

Serve `front-end/` with a simple static server and open it in your browser.

### Optional backend

The backend is useful for local helper flows, especially running
`leap_road_model` from the UI. It is not required for the static researcher
review workflow.

Install Python dependencies from `requirements.txt`, then run:

```bash
python back-end/run.py
```

## Recommended update process

Before committing Road Module 1 default updates:

1. Update or add source files under `back-end/data/road_model/`.
2. Record the method in `back-end/data/road_model/UPDATE_METHOD.md`.
3. Regenerate Module 1 packages and the static CSV bundle with `python back-end/workflow.py`.
4. Review changed static files under `front-end/road-module1-static/`.
5. Commit source/method/docs/static-bundle changes together when intentional.

For normal edits in `manually_filled_rows/`, run `back-end/workflow.py` as-is.
Only set `RUN_PREPARE_SOURCE_FROM_LEAP_EXPORT = True` when the upstream workbook
in `back-end/data/road_model/leap_import_workbooks/` has changed.

## Current focus and boundaries

This repo owns:

- Module 1 source-data handling;
- default package generation;
- researcher input capture;
- simple validation and diagnostics;
- static UI bundle generation; and
- optional model-run integration.

This repo does not own downstream road simulation logic. Modules 2-7 belong in
`leap_road_model`.

## Documentation index

- Main Module 1 guide:
  - `docs/new model/multinode_road_module1_repo_guide.md`
- Numeric update method log:
  - `back-end/data/road_model/UPDATE_METHOD.md`
- Cross-repo docs:
  - `docs/CROSS_REPO_DOCS.md`
