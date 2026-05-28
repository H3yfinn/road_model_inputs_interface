# Multinode Road Module 1 Repo Guide

**Status:** Working source-of-truth guide for how `multinode_energy_balance`
operates as Module 1 of the road transport model.

**Primary audience:** Developers and agents working in this repo, plus
developers in `leap_road_model` who need to understand what Module 1 will hand
to the rest of the road model.

**Related repos:**

| Repo | Role |
| --- | --- |
| `multinode_energy_balance` | Researcher input tool and Module 1 writer. It collects, defaults, validates, audits, and exports road input data. |
| `leap_transport` | Upstream transport data preparation system. It maps and recategorizes 9th-edition outputs into LEAP-oriented transport outputs that are close to Module 1 / road-model needs. |
| `transport_model_9th_edition` | Original upstream model whose outputs are transformed by `leap_transport`. |
| `leap_road_model` | Road model reader and downstream Modules 2-7. It should consume the Module 1 output package and build LEAP-ready road model inputs. |

---

## 1. Purpose

`multinode_energy_balance` has two related purposes:

1. General multinode energy balancing for user-defined demand trees. This was originally built for the buildings sector but is adaptable to other demand sectors.
2. Designed as a fork of the original repo, the Road Model section is for Road Model input collection and defaults for `leap_road_model`.

The second purpose is the important one for the road model. In that workflow,
this repo is not just a UI. It is the canonical Module 1 system:

- it defines the researcher-facing data request;
- it loads and documents default assumptions;
- it overlays better provided values where available;
- it records sources, review flags, and validation results;
- it exports one structured package per economy for downstream road modules.

The downstream `leap_road_model` repo should treat the Module 1 output from this
repo as the input contract for Modules 2-7.

Default deployment assumption for this guide:

- run as a static, client-side tool (for example GitHub Pages);
- no always-on server requirement;
- upload/checkpoint behavior is browser-side file processing by default;
- backend endpoints are optional local tooling, not the primary operational mode.

Static runtime behavior in the current frontend implementation:

- selector metadata is loaded from packaged static files first;
- provided-values defaults are loaded from packaged static files first;
- optional backend fallback/helpers are enabled only by explicit opt-in
  (for example `?roadBackend=1`, disabled with `?roadBackend=0`);
- if neither packaged defaults nor backend fallback is available, users can still
  continue by loading a checkpoint/values file in-browser.

Historical context that should guide implementation choices:

- before the new Module 1 design, the project already had broad default coverage
   through the `leap_transport` pipeline;
- `leap_transport` already performed most 9th-edition to LEAP recategorisation;
- recategorisation between `leap_transport` output and Module 1 / `leap_road_model`
   input is intentionally minimal;
- in practice, Module 1 defaults should be treated as near-direct use of
   `leap_transport` outputs, with hard-coded assumptions retained mainly as
   explicit fallback/bootstrap logic.

---

## 2. Road Model Boundary

### What this repo owns

This repo owns Module 1:

- economy list and economy name aliases used by the input workflow;
- road input row schema;
- default road input generation;
- PHEV utilisation overlay;
- transport LEAP export overlay;
- researcher override capture from the UI;
- source and review metadata;
- unit, key, bounds, and structure validation;
- Module 1 output package writing.

### What `leap_road_model` owns

`leap_road_model` owns Modules 2-7:

- base-year road structure mapping;
- stock target projection;
- sales, survival, vintage, and turnover;
- sales share preparation;
- fuel allocation and reconciliation;
- LEAP input package creation;
- optional Python mirror and post-LEAP validation.

### Interface principle

Module 1 should output a clean, explicit, and documented package. That package
is the only contract that `leap_road_model` should rely on. If
`leap_road_model` needs new inputs, they should be added to the Module 1 output
and documented in this guide.

A key strength of this approach is that Module 1 defaults already use the same
structure as the output package. Because upstream `leap_transport` outputs are
already close to Module 1 shape, this is often close to direct reuse rather
than major remapping. This means `leap_road_model` can use those defaults as a
fallback when researchers do not provide overrides. Because defaults and
outputs share one format, updates are easier to manage and the interface
between repos stays simple and stable.

The target interface is:

```text
one workbook per economy
road_module1_inputs_{ECONOMY}.xlsx
```

where `{ECONOMY}` uses the no-underscore code used in this repo, for example
`20USA`. `leap_road_model` can convert this to canonical codes such as
`20_USA` when needed.

---

## 3. Current Implementation Snapshot

As of the current repo state, the Road Module 1 workflow is partially
implemented and still partly CSV-based.

### Implemented today

Key implementation files:

| File | Purpose |
| --- | --- |
| `back-end/core/road_module1_defaults.py` | Main Module 1 defaults, overlays, validation, optional local backend save/export helpers, and lifecycle export logic. |
| `back-end/road_module1_defaults_workflow.py` | Notebook-style workflow script that writes all-economy default packages. |
| `back-end/api/routers.py` | Optional FastAPI endpoints for local/non-static deployments. |
| `front-end/app.js` | Road Module 1 researcher UI state, rendering, overrides, browser-draft handling, client-side upload validation/overlay, and client-side checkpoint export. |
| `front-end/api.js` | Optional API client methods for backend-enabled runs (not required for static-first workflow). |
| `front-end/road-module1-static/index.json` | Packaged static selector metadata used as the primary runtime source in static mode. |
| `front-end/road-module1-static/README.md` | Static bundle layout and defaults-file naming/schema contract for static packaging. |
| `back-end/data/road_model_default_input_workbook.xlsx` | All-economy seed workbook for default input rows. |
| `back-end/data/apec_phev_utilisation_rates.csv` | PHEV electric utilisation source data. |
| `back-end/data/transport_leap_exports/` | Transport LEAP export workbooks used to overlay existing values where paths match. |

Current default outputs are written here:

```text
back-end/outputs/road_module1_defaults/{version}/{economy}/
```

Current researcher outputs (when optional backend save/export tooling is used) are written here:

```text
back-end/outputs/road_module1_researcher_outputs/{version}/{economy}/
```

### Current output shape

Current default packages are workbook-first, with optional CSV diagnostics.

Primary artifact per economy:

- `road_module1_inputs_{ECONOMY}.xlsx`

Default-package diagnostic CSVs are optional debug artifacts and can be ignored
for normal workflows. Use them only when troubleshooting data quality,
validation, or overlay issues.

Current researcher output is one workbook per economy:

- `road_module1_inputs_{ECONOMY}.xlsx`

Legacy researcher CSV/lifecycle sidecars are now treated as transitional and
are cleaned up by the current writer.

### Target output shape

The intended target is to consolidate those pieces into one workbook per
economy. CSV sidecars may still be useful for debugging, but they should not be
the primary handoff contract.

### 3.1 Repo folder structure and archive policy

To keep the repo easy to navigate, treat folders as one of these classes:

| Class | Path pattern | Purpose | Commit expectation |
| --- | --- | --- | --- |
| Runtime code | `back-end/`, `front-end/` | Application logic and UI | Commit normally |
| Canonical inputs | `back-end/data/` | Source datasets/workbooks used by workflows | Commit intentionally |
| Current packaged defaults | `front-end/road-module1-static/` | Static client bundle used by deployed UI | Commit intentionally |
| Current generated outputs | `back-end/outputs/road_module1_defaults/v*/`, `back-end/outputs/road_module1_researcher_outputs/v*/` | Current run outputs used for review/testing | Commit only when needed |
| Archive | `archive/`, `back-end/outputs/archive/` | Historical logs, snapshots, and temporary run artifacts | Prefer keep out of active workflows |

Current archive locations used in this repo:

```text
archive/logs/
archive/input_snapshots/
back-end/outputs/archive/road_module1_defaults_tmp/
```

What should be moved to archive (instead of staying in active folders):

- root-level server logs (`backend_server*.log`, `frontend_server*.log`);
- ad-hoc input snapshots not used by active loaders;
- temporary defaults runs/folders (for example `_tmp_*` under defaults outputs);
- one-off diagnostics that are not part of the handoff contract.

What should stay out of archive:

- active source inputs under `back-end/data/`;
- latest deployable static defaults under `front-end/road-module1-static/`;
- latest versioned output package under `back-end/outputs/road_module1_defaults/v*/`.

Lightweight housekeeping rule:

1. Keep only current run artifacts in active output folders.
2. Move exploratory or temporary runs to `back-end/outputs/archive/...`.
3. Keep operational logs in `archive/logs/` so project root stays clean.

---

## 4. Module 1 Data Flow

The Module 1 process should be understood as this sequence:

1. Build or load default assumptions.
2. Overlay economy-specific source data where available.
3. Serve default-filled rows to the researcher UI.
4. Let the researcher review and override base-year values.
5. Validate the completed input package.
6. Export one structured workbook per economy.
7. Let `leap_road_model` read that workbook as Module 1 input.

### 4.1 Default assumptions

Defaults are seeded primarily from `leap_transport`-derived workbook inputs
(the all-economy seed workbook), with hard-coded tables and helper functions in
`road_module1_defaults.py` acting as fallback/bootstrap logic when needed.

Design intent: because `leap_transport` has already done most category mapping,
the translation from that output into Module 1 and then into
`leap_road_model` should be minimal.

Defaults include:

- stock;
- sales share;
- mileage;
- fuel economy;
- vehicle equivalent weight;
- passenger vehicle saturation;
- PHEV electric driving share;
- reconciliation bounds;
- reconciliation weights;
- survival rate;
- vintage profile share.

Every default row should carry:

- `input_source`;
- `source_type`;
- `source_name`;
- `source_scope`;
- `source_date`;
- `default_version`;
- `researcher_review_recommended`;
- `review_reason`;
- `notes`.

### 4.2 PHEV utilisation overlay

`apec_phev_utilisation_rates.csv` provides economy-level PHEV electric driving
share assumptions. The overlay updates `PHEV Electric Driving Share` rows for
the base year and clears future-year values because future changes are expected
to be handled by LEAP adjustment variables.

If a PHEV source row is missing or malformed, the workflow should create a
report row rather than silently falling back.

This data was generated using AI and is explained here: C:\Users\Work\github\leap_road_model\docs\Estimating PHEV electric-mode utilisation across APEC economies.docx
There is a chance the Russia and PNG PHEV utilisation rates are conservative
because of limited data. The current assumption is still preferred over broad
fallback values from other economies. If better data becomes available, update
the source CSV and the overlay will refresh automatically.

### 4.3 Transport LEAP export overlay

Transport LEAP export workbooks are used as the best available source where
their rows match Module 1 branch paths and variables. In normal operations,
this is expected to be the dominant source for many measures, not a marginal
add-on.

The loader looks for all-economy exports matching:

```text
transport_leap_export_combined_ALL_ECONS*.xlsx
```

and reads the `FOR_VIEWING` sheet with LEAP-style headers.

The overlay is path-based:

- match on `Branch Path`;
- match on `Variable`;
- match on economy region names and aliases;
- use APEC fallback rows for selected non-absolute variables where allowed.

This overlay should remain conservative. If row identity is ambiguous, prefer a
report flag over a silent update. Where row identity is clear, direct reuse of
`leap_transport` output should be preferred over re-deriving values.

### 4.4 Researcher override layer

The UI serves default-filled rows to researchers. Researchers can type values
for editable years, currently focused on the base year.

Overrides are keyed by:

```text
Branch Path, Variable, Scenario, Region, Year
```

In the default static workflow, those overrides are applied in browser state and
captured in exported checkpoint files. No server persistence is required.

Browser drafts are convenience only. The portable record is the exported
checkpoint file that the researcher keeps and can re-load later.

If the optional backend is enabled, equivalent override payloads can also be
processed by backend routes for local tooling workflows.

### 4.5 Checkpoint export and reupload

The researcher UI supports a workbook checkpoint workflow. At the end of a work
session, the researcher can export the current values as
`road_module1_inputs_{ECONOMY}.xlsx`. On a later day, they can select the same
version, economy, and scenario, then upload that workbook through
`Upload Checkpoint / Values File`.

This is intended to be the portable record between sessions. Browser drafts can
help during one local browser session, but the checkpoint workbook is the file
that can be moved between computers, emailed, archived, and reloaded.

Checkpoint export behavior (static/client-side-first):

- The frontend exports the complete current base-year state from browser
  memory, not only fields typed during the current session.
- Blank UI fields are exported as their grey provided value from the current
  browser state.
- If the researcher started from a previously uploaded checkpoint or values
  file, those uploaded values are preserved in the next checkpoint export.
- Shared mileage values are expanded to the detailed LEAP-like mileage rows
  before export, unless a detailed row override is present.
- Upload compatibility and value-bound checks are run client-side before values
  are applied.

Upload behavior:

- XLSX/XLS files prefer row-key input from `Details` when that sheet exists,
  otherwise from `Data`, otherwise from the first worksheet.
- If present, `Factors`, `Lifecycle`, and `Vintage` are also parsed client-side
  and mapped into canonical row-key updates before overlay is applied.
- CSV files are read directly.
- The file must keep the key columns:
  `Branch Path`, `Variable`, `Scenario`, `Region`.
- The file must include the base-year column, currently `2022`.
- For workbook uploads, if `Details`/`Data` is absent or partial, mapped updates
  from `Factors`/`Lifecycle`/`Vintage` can still contribute updates for matching
  canonical Module 1 rows.
- Future-year columns may be present, but the current researcher workflow is
  base-year first; later-year changes are handled in LEAP adjustment variables.
- Uploaded checkpoint values are overlaid client-side onto the currently loaded
  selection in browser state before the UI rerenders.
- The uploaded file must match the selected version/economy/scenario row keys.
  Rows that do not match are reported instead of silently creating new rows.

Validation for upload compatibility and value checks runs client-side in static
deployments. Backend validation is optional and should mirror the same rules
when backend mode is used.

### 4.6 Validation

Module 1 validation should check:

- required columns are present;
- column order matches the contract;
- required values are populated;
- key columns are unique;
- year values are numeric where present;
- values obey variable-specific bounds;
- reconciliation lower bounds do not exceed upper bounds;
- variables are known;
- units match the variable contract;
- input sources are known;
- label statuses are known.

Validation reports should be stored in the output package and exposed to the UI.

In static mode, validation messages should be generated in-browser and shown in
the UI before export/download.

---

## 5. Measure Scope Contract

Module 1 is a base-year data request. The current base year is `2022`.

Researchers should only be asked for values less than or equal to the base year
unless the LEAP adjustment-variable workflow changes. Future years can remain in
the schema for compatibility and viewing, but the researcher review UI should
not imply that future-year values are expected inputs.

The standard data request intentionally keeps some measures shared above the
vehicle or fuel level.

Current scope policy (used to prevent branch/scope mismatch flags):

- keep `HEV` and `EREV` only under LPV branches;
- remove `HEV` and `EREV` from non-LPV vehicle types;
- remove truck `PHEV` branches;
- use LPV drive-size labels as `small` / `medium` / `large` in downstream mapping;
- use `Fuel Economy` as the canonical efficiency variable name;
- keep researcher mileage input at shared vehicle-type scope, then expand to
  detailed fuel-level rows in exported outputs;
- keep main `Stock` reporting at transport-type scope, with optional
  drive-level stock detail on a separate sheet when requested.

| Measure | Standard scope | Notes |
| --- | --- | --- |
| Reconciliation Bound Lower | Whole road sector | One value for Passenger road and one value for Freight road. |
| Reconciliation Bound Upper | Whole road sector | One value for Passenger road and one value for Freight road. |
| Reconciliation Weight | Whole road sector | One value for Passenger road and one value for Freight road. |
| Survival Rate | Whole road-sector age series | One passenger road series and one freight road series. |
| Vintage Profile Share | Whole road-sector age series | One passenger road series and one freight road series, normalized before use. |
| PHEV Electric Driving Share | Passenger LPV PHEV series | Applied to LPV PHEV branches; freight truck PHEV is out of scope. |
| Passenger Vehicle Saturation | Passenger road sector | One passenger road value. Not used for freight road. |
| Mileage | Vehicle type series (input), fuel-level rows (output) | Researchers provide one shared series per road vehicle type; exports expand to detailed branch rows unless detailed overrides are provided. |

A later detailed mode can request vehicle-type or fuel-level values for these
measures, but the standard mode should stay deliberately simpler.

---

## 6. Target Workbook Contract

The target Module 1 handoff is one workbook per economy:

```text
road_module1_inputs_{ECONOMY}.xlsx
```

Example:

```text
road_module1_inputs_20USA.xlsx
```

This workbook is the primary contract between `multinode_energy_balance` and
`leap_road_model`.

### Sheet: `Data`

Purpose: LEAP-compatible scalar/base-year input rows.

This sheet should contain the rows that downstream modules need as tabular road
inputs. It should avoid audit-only metadata columns.

Columns:

| Column | Meaning |
| --- | --- |
| `Branch Path` | Full LEAP-style branch path with backslashes. |
| `Variable` | LEAP variable name. |
| `Scenario` | Scenario name, usually `Reference` or `Target`. |
| `Region` | Economy long name. |
| `Scale` | LEAP scale setting. |
| `Units` | Unit string. |
| `Per...` | Denominator unit where needed. |
| `2022` | Base-year value. |
| `2030`, `2040`, `2050` | Optional viewing/projection columns where applicable. |

Rows that belong in `Data`:

- `Stock`
- `Mileage`
- `Fuel Economy`
- `Sales Share`
- `Vehicle Equivalent Weight`
- `Passenger Vehicle Saturation`

Stock convention for downstream consumers:

- `Data` should keep the transport-type stock rows used in core workflows.
- If drive-level stock rows are exported for diagnostics/review, place them on
  a separate detail sheet (for example `Stock_Drive_Detail`) rather than
  replacing the main stock rows.

Rows that should not be stored primarily in `Data`:

- survival rates;
- vintage profiles;
- PHEV utilisation;
- reconciliation factors.

Those belong in dedicated sheets below.

### Sheet: `Lifecycle`

Purpose: LEAP lifecycle-format survival profiles.

Each profile block uses this layout:

```text
Row 0:  Area:       <economy long name or LEAP area name>
Row 1:  Profile:    <profile name>
Row 2:  blank
Row 3:  Year        Value
Row 4+: <age>       <cumulative survival percent>
```

Required profiles:

| Profile | Meaning |
| --- | --- |
| `Passenger road survival` | Survival curve for passenger road vehicles. |
| `Freight road survival` | Survival curve for freight road vehicles. |

Values should be percentages from 0 to 100. Age 0 should be 100 unless there is
a documented reason to do otherwise.

### Sheet: `Vintage`

Purpose: LEAP lifecycle-format base-year fleet age distribution profiles.

Layout is the same as `Lifecycle`.

Required profiles:

| Profile | Meaning |
| --- | --- |
| `Passenger road vintage` | Passenger road fleet age distribution. |
| `Freight road vintage` | Freight road fleet age distribution. |

Values should sum to 100 across ages after normalization.

### Sheet: `Factors`

Purpose: scalar configuration values that apply above the branch/fuel row level.

Columns:

| Column | Meaning |
| --- | --- |
| `Parameter` | Stable parameter name. |
| `Transport Type` | `passenger`, `freight`, or `all`. |
| `Vehicle Type` | Vehicle type or `all`. |
| `Scenario` | Scenario or `all`. |
| `Value` | Numeric value. |
| `Unit` | Unit label. |
| `Notes` | Short explanation. |

Parameters expected here:

- `phev_electric_utilisation_rate`;
- `reconciliation_bound_lower`;
- `reconciliation_bound_upper`;
- `stock_reconciliation_weight`;
- `mileage_reconciliation_weight`;
- `efficiency_reconciliation_weight`;
- `freight_elasticity` if Module 1 owns the default value.

Reconciliation weights should sum to 1.0 for each applicable group.

### Sheet: `Details`

Purpose: audit trail for the rows in `Data`.

`Details` should preserve the full row set and row order from `Data`, then add
metadata columns:

- `input_source`;
- `standardized_label_status`;
- `notes`;
- `source_type`;
- `source_name`;
- `source_scope`;
- `source_date`;
- `default_version`;
- `researcher_review_recommended`;
- `review_reason`.

This sheet is for researchers, reviewers, and audit. Downstream code should use
it only for diagnostics, not for core model logic.

### Optional diagnostic sheets

The workbook may also include diagnostic sheets if useful:

- `Validation`
- `Override_Report`
- `Source_Flags`
- `Missing_Data`
- `Unit_Check`
- `Transport_LEAP_Overlay`

These are not part of the minimum reader contract unless explicitly promoted.

---

## 7. Optional Backend API Contract

This section applies only when running an optional backend deployment.

The optional Road Module 1 API is under:

```text
/api/v1/road-module1
```

Current endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /versions` | List available default package versions. |
| `GET /economies` | List economies available for a version. |
| `GET /defaults` | Return default-filled rows for UI rendering. |
| `GET /provided_values_template` | Download the current provided-values template workbook or CSV fallback. |
| `GET /builtin_provided_values` | Apply built-in transport LEAP export values and return rows. |
| `POST /provided_values` | Upload CSV/XLSX provided values or a checkpoint workbook and overlay them onto defaults. |
| `POST /researcher_output` | Save the current researcher values and write the completed checkpoint workbook. |
| `GET /researcher_output_file` | Download the current completed checkpoint workbook. |

The optional API behavior is workbook-first for researcher handoff:

- template download returns the generated provided-values workbook when available;
- researcher output writes the complete current base-year state and returns that workbook path;
- checkpoint reupload accepts that workbook and reads the `Details` sheet;
- CSV paths can remain for debugging and backward compatibility.

Optional backend mode is explicit. The current frontend enables backend fallback
and helper actions only when opted in (for example `?roadBackend=1`).

---

## 8. Downstream Reader Contract for `leap_road_model`

`leap_road_model` should implement a reader adapter, conceptually:

```python
load_multinode_road_defaults(workbook_path, economy, scenario)
```

The adapter should:

1. Read `Data` for scalar road inputs.
2. Read `Lifecycle` for survival curves used by Module 4.
3. Read `Vintage` for base-year vintage profiles used by Module 4.
4. Read `Factors` for PHEV utilisation and reconciliation settings used by
   Modules 4 and 6.
5. Optionally read `Details` and diagnostics for warnings and source reporting.

The adapter should parse branch paths into downstream dimensions:

- transport type;
- vehicle type;
- drive type;
- size where represented (LPV: `small` / `medium` / `large`);
- fuel.

Reader logic should treat the following as canonical scope rules:

- non-LPV `HEV`/`EREV` rows are legacy and should be ignored;
- truck `PHEV` rows are legacy and should be ignored;
- `Fuel Economy` is canonical (legacy `Final On-Road Fuel Economy` may appear
  in historical packages and should be treated as an alias).

The adapter should convert units explicitly. Known conversions include:

- `MJ/100 km` to whatever efficiency basis Modules 2-7 require;
- percent shares from 0-100 to fractions from 0-1 where needed;
- lifecycle/vintage percentages to fractions if the module expects fractions.

Because recategorisation from `leap_transport` output into Module 1 is designed
to be minimal, the adapter should prefer direct field mapping and only apply
explicit, documented conversions where unavoidable.

`leap_road_model` should not depend on the current CSV sidecar layout once the
workbook writer exists.

---

## 9. Code Ownership Map

### Backend road Module 1

`back-end/core/road_module1_defaults.py` currently owns most logic:

- constants and schema columns;
- economy metadata;
- branch path construction;
- default assumption construction;
- PHEV source loading and overlay;
- transport LEAP export loading and overlay;
- workbook seed loading;
- structure validation;
- source flags and reports;
- researcher override application;
- lifecycle and vintage export writing;
- all-economy package writing.

This file is doing too many jobs, but it is currently the correct starting point
for understanding Module 1 behavior. Any refactor should preserve behavior and
tests first.

### Backend routes

`back-end/api/routers.py` connects Module 1 functions to the UI.

Road routes should stay thin:

- validate request basics;
- call functions in `road_module1_defaults.py` or its future split modules;
- return rows, reports, and output paths.

For static-first deployments, these routes are optional and should not be
assumed by the core researcher workflow.

### Frontend

`front-end/app.js` owns the researcher interaction:

- economy/version/scenario selection;
- row rendering and grouping;
- editing base-year values;
- shared mileage behavior;
- local browser draft;
- client-side checkpoint upload parsing and overlay;
- client-side validation before export;
- override payload construction;
- save/export actions.

The frontend is the primary runtime in static mode. Validation and scope checks
needed for safe researcher input should exist client-side. If backend mode is
enabled, backend checks should mirror the same rules.

---

## 10. Versioning and Naming

Current default version:

```text
v2026_05_25_best_guess
```

Version strings should identify the default package, not the researcher export
time. Timestamped fallback files are acceptable when an output file is locked,
but the canonical path should remain stable.

Economy codes in this repo use no underscores:

```text
01AUS, 08JPN, 20USA
```

Where `leap_road_model` expects canonical APEC codes, the reader should convert:

```text
20USA -> 20_USA
```

Region names should use the economy long names expected by LEAP, with alias
handling for cases such as:

- `20USA`: `United States`, `United States of America`
- `05PRC`: `China`, `People's Republic of China`
- `09ROK`: `Korea`, `Republic of Korea`

---

## 11. Implementation Roadmap

### Phase 1: Document and stabilize current CSV workflow

Done when:

- this guide exists;
- current CSV outputs are documented;
- validation expectations are clear;
- current module boundaries are explicit.

### Phase 2: Add workbook writer without removing CSV outputs

Add functions that convert a completed Module 1 dataframe into:

- `Data`;
- `Lifecycle`;
- `Vintage`;
- `Factors`;
- `Details`;
- optional diagnostics.

The writer should be called from `write_economy_package()` and
`write_researcher_completed_package()`.

CSV outputs should remain during the transition so existing UI and debugging
paths are not broken.

### Phase 3: Make workbook the primary API artifact

Update the static workflow first so workbook checkpoint upload/export works end
to end in-browser, with no backend dependency.

If backend mode is used, keep API endpoints aligned with the same workbook
artifact and row-key rules.

### Phase 4: Implement or update `leap_road_model` reader

In `leap_road_model`, update the Module 1 adapter so it reads the workbook
contract directly.

The road workflow guide in `leap_road_model` should then point to this document
for Module 1 details instead of duplicating the input-tool design.

### Phase 5: Keep docs consolidated

Once this guide and the workbook writer are stable:

- update `README.md` to link here.
- keep any future Module 1 design updates in this file unless there is a clear
  reason to split out a narrower reference.

---

## 12. Rules for Future Changes

When changing Module 1 behavior:

1. Update this guide in the same change.
2. Keep researcher-facing scope simple unless a detailed mode is explicitly
   added.
3. Preserve the workbook reader contract or version it deliberately.
4. Do not let frontend-only logic become the only record of model behavior.
5. In static deployments, frontend validation logic is operationally primary;
  document it clearly and keep optional backend checks aligned.
6. Prefer report rows and validation flags over silent fallbacks.
7. Preserve source metadata whenever values are overlaid or overridden.
8. Keep base-year researcher input separate from future LEAP adjustment
   variables.
9. Make new assumptions visible in `Details`, `Factors`, or diagnostics.
10. Treat `leap_transport` output as the primary default source and avoid
   re-deriving values in Module 1 unless a gap is documented.

---

## 13. Open Design Questions

These need explicit decisions before the workbook becomes the only handoff:

| Question | Current leaning |
| --- | --- |
| Should `Data` include `Expression` and Level columns, matching strict LEAP import format? | Eventually yes if `Data` is meant to be directly importable to LEAP. For Module 1 reader use, the current tabular year-column format may be enough. |
| Should survival/vintage also remain in `Data` as rows for UI rendering? | They may remain internally for UI convenience, but the workbook contract should expose them through `Lifecycle` and `Vintage`. |
| Should `Factors` be generated from current rows or from a separate parameter table? | Generate from current rows first, then migrate to a clearer parameter table if needed. |
| Should `Details` include lifecycle and factor source metadata too? | Prefer yes, either in `Details` or separate diagnostic sheets. |
| Should the workbook contain all scenarios or one scenario? | Prefer all scenarios in one economy workbook unless file size or reviewer workflow argues otherwise. |
| Should `leap_road_model` tolerate old CSV packages? | Yes during transition, but workbook should be the preferred path. |

---

## 14. Quick Navigation

Use these files first:

- `docs/new model/multinode_road_module1_repo_guide.md`
- `back-end/core/road_module1_defaults.py`
- `back-end/road_module1_defaults_workflow.py`
- `back-end/api/routers.py`
- `front-end/app.js`
- `C:/Users/Work/github/leap_road_model/docs/new model/road_transport_model_workflow_guide.md`

For output inspection:

- `back-end/outputs/road_module1_defaults/`
- `back-end/outputs/road_module1_researcher_outputs/`
- `back-end/outputs/archive/road_module1_defaults_tmp/` (temporary exploratory runs)
- `back-end/data/road_model_default_input_workbook.xlsx`
- `back-end/data/transport_leap_exports/`
- `archive/input_snapshots/` (ad-hoc historical input files)
