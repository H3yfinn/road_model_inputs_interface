# Road Model Data Folder Guide

This folder is the source-data package for Road Module 1. The code reads files
here, combines them into final Module 1 rows, validates them, and writes outputs
under `back-end/outputs/road_module1_defaults/`.

## Quick Mental Model

```text
processed_source + manually_filled_rows
  -> choose rows by source priority
  -> apply supplemental source overlays
  -> derive or clean special rows
  -> apply final_value_overrides
  -> write road_module1_values_<ECONOMY>.csv and reports
```

## Folder Roles

| Path | Role | Edit directly? |
|---|---|---|
| `processed_source/` | Main per-economy source rows in LEAP-like long format. These are generated from transport LEAP exports. | Usually no; regenerate from source workbooks. |
| `manually_filled_rows/` | Manual rows used to fill known gaps before supplemental overlays and final overrides. | Yes, when documenting missing-row fixes. |
| `supplemental_source_files/` | Source-specific CSV/XLSX files for measures that are absent or weaker in the processed source. | Yes, but document provenance in `UPDATE_METHOD.md`. |
| `final_value_overrides/` | Optional final row overrides applied last, after every normal source has run. | Yes, for temporary or researcher-controlled final changes. |
| `leap_import_workbooks/` | Upstream LEAP-style transport export workbooks used to create `processed_source/`. | Replace when upstream export updates. |
| `archive/` | Historical files not active in current generation. | No, except to add retired files. |

## Control Files

| File | Role |
|---|---|
| `road_model_structure_contract.json` | Lists active datasets, required file patterns, and required columns. |
| `road_module1_default_parameters.json` | Structure/control-plane metadata only; not a numeric source of truth. |
| `road_module1_source_priorities.csv` | Decides which row source wins when the same final row exists in multiple pre-overlay sources. |
| `road_module1_required_rows.csv` | **Required rows manifest.** Lists every `(Branch Path, Variable)` pair that must appear in every economy's frontend output CSV. Covers fixed structure (transport, vehicle-type, age, drive levels). Mileage and Fuel Economy are validated separately by rule. Enforced as a hard error by `build_road_model_static_defaults.py`. Edit directly when the tree or measure scope changes; never regenerate from output. |
| `UPDATE_METHOD.md` | Audit log for numeric source updates and generated-source methods. See the "Required rows manifest" section for how the manifest works and when to update it. |

## Source Priority

`processed_source/` and `manually_filled_rows/` can both provide final row-shaped
data. When duplicate rows exist, priority comes from:

```text
road_module1_source_priorities.csv
```

Lower numeric priority wins. After this priority step, supplemental source files
can still overwrite or add specific measures. `final_value_overrides/` always
runs last.

## Final Overrides

Use `final_value_overrides/` when you want final say over a generated value.
Files are named:

```text
module1_final_value_overrides_<ECONOMY>.csv
```

Required columns:

```text
Branch Path, Variable, Scenario, Year, Value, Units, share_decreased_from, note, DO_NOT_USE
```

Rows with `DO_NOT_USE = TRUE` are ignored by the final override loader. Use this
to keep example or inactive rows in a spreadsheet without applying them.

For `Sales Share` and `Stock Share`, `share_decreased_from` can name a sibling
branch that should absorb the change. If it is blank, the remaining sibling
shares are scaled so the group still sums to 100.

When final overrides are applied, the build writes visibility outputs beside the
generated economy CSV:

```text
road_module1_final_value_override_report.csv
road_module1_final_value_override_report.html
```

Open the HTML report to see before/after charts.

## Outputs

Generated files are not written inside this data folder. They go to:

```text
back-end/outputs/road_module1_defaults/<VERSION>/<ECONOMY>/
```

`<VERSION>` should be a dated, immutable folder such as:

```text
v2026_06_05_road_module1_sources
```

Do not keep writing new production runs into an old version folder. If a run is
exploratory, use a `_tmp_...` version name or an archive output folder and do
not point the frontend at it.

The main generated CSV is:

```text
road_module1_values_<ECONOMY>.csv
```

This is the current tall format, with `Year` and `Value` columns. Older files
named `road_module1_default_filled_inputs_<ECONOMY>.csv` use the legacy wide
format with year columns such as `2022`; treat those as stale unless you are
intentionally reading a historical version.

After generating backend outputs, regenerate `front-end/road-module1-static/`
from the same version so the website reads the same data package.

## Where The Code Lives

The main reader and overlay logic is in:

```text
back-end/core/road_module1_defaults.py
```

The static/default build entry point is:

```text
back-end/build_road_model_static_defaults.py
```

For the broader Module 1 design, see:

```text
docs/new model/multinode_road_module1_repo_guide.md
```
