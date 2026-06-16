# Road Module 1 comprehensive guide

This is the main design and implementation guide for Road Module 1 in
`road_model_inputs_interface`. Keep this file as the source of truth for Module
1 behavior. The shorter docs in this folder should point back here rather than
restate the same contract.

![End-to-end road model workflow](End-to-end%20road%20model%20workflow%208062026.png)

*Primary reference for the full end-to-end workflow. Some implementation detail is not shown.*
 
## Contents

1. [Purpose](#1-purpose)
2. [System boundary](#2-system-boundary)
3. [Data sourcing policy](#3-data-sourcing-policy)
4. [Canonical data flow](#4-canonical-data-flow)
5. [Canonical CSV contract](#5-canonical-csv-contract)
6. [Measure and branch scope](#6-measure-and-branch-scope)
7. [Researcher UI workflow](#7-researcher-ui-workflow)
8. [Validation and review](#8-validation-and-review)
9. [Optional backend and model run integration](#9-optional-backend-and-model-run-integration)
10. [Downstream interface to leap_road_model](#10-downstream-interface-to-leap_road_model)
11. [Versioning and update method](#11-versioning-and-update-method)
12. [Current implementation map](#12-current-implementation-map)
13. [Roadmap](#13-roadmap)
14. [Open questions](#14-open-questions)

## 1. Purpose

Road Module 1 is the data request and default-input layer for the new road
transport model.

It has four jobs:

- collect and present the road-model input rows researchers need to review;
- build default values from documented source files;
- capture researcher values, comments, and source notes without changing the row
  structure; and
- export a package that `leap_road_model` can use as the upstream input contract
  for Modules 2-7.

Module 1 is not the road model calculation engine. It should stay simple: most
numeric assumptions should live in CSV/XLSX source files, and code should mainly
read, normalize, validate, and export those values.

## 2. System boundary

### Repo layout — both repos must be siblings

Clone both repos into the **same parent folder**:

```text
parent_folder/
    road_model_inputs_interface/   ← this repo
    leap_road_model/               ← sibling repo
```

Keep both open in one VS Code multi-root workspace (`File → Add Folder to Workspace`).
`leap_road_model` resolves the Module 1 output path as
`../road_model_inputs_interface/back-end/outputs/road_module1_defaults/` by
convention. The offline workflow in `leap_road_model/scripts/offline_workflow.py`
uses that path automatically.

### This repo owns Module 1

`road_model_inputs_interface` owns:

- the road input source files under `back-end/data/road_model/`;
- the rules used to convert those source files into Module 1 rows;
- the static CSV bundle used by the browser UI (same format as the output long CSV);
- the researcher UI for reviewing and filling existing rows;
- export/reupload behavior for researcher-filled CSVs; and
- optional backend endpoints used to run `leap_road_model` from the UI.

### leap_road_model owns Modules 2-7

`leap_road_model` owns:

- parsing the Module 1 output package into model tables;
- loading other model inputs that do not belong in Module 1, such as population,
  GDP, and ESTO road energy;
- projecting passenger and freight stock targets;
- calculating sales, survival, vintage, and turnover;
- preparing sales shares;
- reconciling base-year road fuel energy to ESTO;
- calculating Device Shares; and
- writing the final LEAP import workbook and diagnostics.

The boundary is important: Module 1 should provide road-branch assumptions and
metadata. It should not try to replicate the reconciliation, stock-turnover, or
LEAP handoff logic from `leap_road_model`.

## 3. Data sourcing policy

### Mandatory rule

Default values must come from files in:

```text
back-end/data/road_model/
```

For a concise folder-by-folder explanation of that data package, see:

```text
back-end/data/road_model/README.md
```

If required default files are missing, generation must fail and request data
regeneration. The UI should not silently allow users to upload an alternative
defaults package.

Researcher uploads are for filling or commenting on existing rows. They are not
a replacement source-of-truth mechanism for the defaults.

### Near-term main source

The near-term primary numeric source is the processed `leap_transport` export in:

```text
back-end/data/road_model/leap_import_workbooks/
```

The preferred all-economy source file pattern is:

```text
transport_leap_export_combined_ALL_ECONS_*.xlsx
```

The older per-economy `transport_leap_export_combined_<ECONOMY>_...xlsx` files
can still be used as fallback or reference material.

These files contain data on transport measures that were prepared for LEAP
imports. In this repo, they are a source for Module 1 defaults, which are then
exported to `leap_road_model` and eventually written into a final LEAP import
workbook. The point is to keep the default values documented, traceable, and
auditable from source file to final LEAP input. The `leap_transport` export is a
good near-term source because it is close to the final structure and reduces the
need for remapping. It is not a permanent ideal data system, because source data
will need to be updated and some measures can later be replaced by newer or more
direct sources. Each replacement should be documented in `UPDATE_METHOD.md`.

These `leap_transport` outputs were built to map 9th edition transport outputs
into LEAP-style branch paths and variables. The branch paths are mostly close to
the final road model structure, but some will need slight recategorization to
fit the simpler road model taxonomy used in this new model. Any recategorization
should be explicit and documented in `UPDATE_METHOD.md`.

### Supplemental source files

Some measures are not in the transport LEAP export and are sourced from specific
CSV/XLSX files in `back-end/data/road_model/supplemental_source_files/`
instead. Current active supplemental files are:

- `apec_phev_utilisation_rates.csv`
- `apec_passenger_vehicle_saturation.csv`
- `apec_reconciliation_factors.csv`
- `apec_vehicle_equivalent_weights.csv`
- `vehicle_survival_modified_00_APEC.xlsx`
- `vintage_modelled_from_survival_00_APEC.xlsx`
- `apec_lifecycle_profile_factors.csv`

`road_model_default_input_workbook.xlsx` is not an active supplemental source
file; it is only an optional legacy fallback. `apec_drive_fuel_split_defaults.csv`
is not part of the active supplemental source package.

Use "source merge" for this behavior: all source folders (`processed_source/`,
`manually_filled_rows/`, `supplemental_source_files/`) are combined into a single
priority-ranked pool. The transport export supplies most defaults; supplemental
files supply measures absent from the export. Only describe something as an
ordered replacement operation if the code actually implements that ordering.

### Update method record

Every scripted numeric data update should be documented in:

```text
back-end/data/road_model/UPDATE_METHOD.md
```

The method log should explain:

- what source was used;
- what script or manual process was run;
- what mappings or recategorizations were applied;
- what outputs changed;
- what checks were run; and
- why the change was made.

This script-by-script record is intentionally lightweight. The point is a clear
audit trail without forcing a large reusable data-ingestion framework too early.

## 4. Canonical data flow

The intended flow is (as well as the intended division of labor between stages of the process):

```text
source CSV/XLSX files in back-end/data/road_model/
#LOCALLY:
  -> Module 1 source processing
  -> canonical long Module 1 rows
  -> validation and diagnostics
  -> static CSV bundle for the UI (same format as the output long CSV)
#CLIENT_SIDE:
  -> browser parses CSV into in-memory JS objects
  -> researcher fills existing rows and comments
  -> researcher export CSV
#BACKEND:
  -> leap_road_model Module 1 package
  -> Modules 2-7
```

The static CSV bundle is a served UI artifact, not a new source of truth. It is
the same long-row format as the researcher output CSV and the downstream
`leap_road_model` input, so it is not a separate format to maintain. Serving
the same CSV format for both the UI and the downstream package keeps the
pipeline simple and means the UI is always exercising the real output format.

The browser parses the CSV (using a library such as Papa Parse) into in-memory
JS objects on load. This is slightly more work than native `JSON.parse`, but the
parse cost is negligible for the data sizes expected and the format benefit
outweighs it.

If a backend is added later, it can serve the same long CSV rows directly. The
generated static CSV bundle can remain as a cache and audit artifact for GitHub
Pages deployment, validation, and pre-publication review.

### Data loading and processing pattern

Use this as the formal pattern for this repo:

```text
source package
  -> source merge (processed_source + manually_filled_rows + supplemental_source_files, priority-ranked)
  -> stock share derivation
  -> final override
  -> build (generated default package per economy)
  -> static sync (frontend static bundle)
  -> browser working copy
  -> researcher overlay
  -> exported/model-run long CSV
```

The important distinction is between processing and loading. Processing happens
offline in Python before deployment or review. Browser loading is intentionally
simple: fetch the generated long CSV, parse it, and convert it to the temporary
UI-wide shape used for editing.

| Stage | Owner | Contract |
| --- | --- | --- |
| Source package | `back-end/data/road_model/` | Documented CSV/XLSX inputs. Missing required files should fail generation. |
| Source merge | `back-end/core/road_module1_defaults.py` | Combines `processed_source/`, `manually_filled_rows/`, and `supplemental_source_files/` into a single priority-ranked row set. Missing required rows are a hard error. |
| Build (generated default package) | `back-end/outputs/road_module1_defaults/<version>/<economy>/` | Per-economy generated output. This is not hand-authored source data. |
| Static sync (frontend static bundle) | `front-end/road-module1-static/<version>/<economy>.csv` | Canonical long CSV filtered to static-eligible variables and tagged with row-level interface visibility. |
| Browser working copy | `front-end/app.js` | Parsed long rows converted to UI-wide rows for display and editing only. |
| Researcher overlay | `front-end/app.js` state maps and upload preview | Edits existing row keys, validates values, and marks researcher-modified rows. |
| Model handoff | `convertRoadWideUiRowsToLongRows()` and `run_model_router.py` | Converts the UI working copy back to the canonical long CSV and sends it to `leap_road_model`. |

Rules:

- The canonical long CSV is the boundary format. It is used for the static
  bundle, download/upload, and model handoff.
- `Input Status` is part of the canonical long CSV. Downstream readers should
  still tolerate older 9-column files where it is absent.
- `Shown In Interface` is part of the static/download/upload CSV contract. It
  controls browser visibility only; hidden rows remain part of the model handoff.
- The internal wide schema is a Python processing convenience, not the public
  contract.
- The UI-wide rows are a browser view model, not an output package.
- The browser must not decide default values, source priority, branch
  construction, or supplemental-source merging.
- Uploads fill existing template rows. They must not introduce new row keys.
- Static CSVs are generated artifacts. Change source files and regenerate
  rather than editing `front-end/road-module1-static/` by hand.
- If the handoff contract changes, update Python `MODULE1_LONG_COLUMNS`,
  JavaScript `ROAD_MODULE1_LONG_COLUMNS`, upload validation, and the model
  adapter as needed.

## 5. Canonical CSV contract

### Why long CSV

Use a long CSV format with `Year` and `Value` columns for Module 1 handoff and
researcher export/reupload. This is easier to validate and edit than a wide file
with columns such as `2022`, `2030`, and `2050`. Because the base year will
usually be the only required year, the long format avoids the risk of users
leaving future-year columns blank or filling them with placeholders. It also
makes it easier to add future-year values later without changing the format.

The LEAP-style wide or expression format can be produced later by
`leap_road_model` when writing the final LEAP workbook.

### Required key columns

The logical row key is:

| Column | Meaning |
|---|---|
| `Economy` | Canonical APEC economy code with underscore, such as `20_USA`. Use this format throughout this repo and downstream code. The road model can later convert the economy code to the LEAP region name where needed. |
| `Scenario` | Scenario label. Current Module 1 defaults usually use `Current Accounts`. |
| `Branch Path` | Road-model branch path or structured pseudo-branch for non-LEAP measures. |
| `Variable` | Measure name, close to LEAP naming where possible. |
| `Year` | Model year for time-series values. Current Module 1 work is base-year first; future years may be present but are optional unless a measure explicitly requires them. |

Researchers must not change key columns. Upload validation should fail if key
columns are missing, renamed, or modified, or if uploaded rows introduce new
keys that were not in the exported template.

### Required value columns

| Column | Meaning |
|---|---|
| `Value` | Numeric or text value used by the model. |
| `Units` | Human-readable units, where applicable. |
| `Source` | Source label or source file used for the default. |
| `Comment` | Researcher or processor comment. Required when a researcher overrides a default if a source is not obvious. |

### Recommended metadata columns

| Column | Meaning |
|---|---|
| `Input Status` | `default`, `researcher_provided`, `missing`, `not_applicable`, or similar. |
| `Shown In Interface` | `True` to show the row in the editable browser UI; `False` to hide it while preserving it in downloads/uploads and model runs. |
| `Source Method` | Short method label such as `transport_leap_export`, `supplemental_csv`, `researcher_override`, or `manual_review`. |
| `Original Value` | Default value before researcher edit, useful for comparison. |
| `Validation Message` | Short message from validation, blank when valid. |
| `Last Updated` | Source-data update date or package generation date. |
| `Version` | Module 1 package version. |

Separate `review_flag` columns are optional. In many cases, `Input Status`,
`Validation Message`, `Source`, and `Comment` are enough and easier for
researchers to understand.

### Static and profile values

Most rows use `Year = BASE_YEAR`. For non-time-series values such as factors,
use `Year = BASE_YEAR` unless the value is explicitly year-specific.

### Fitting new rows into the LEAP branch structure

Lifecycle and vintage profiles live in the same single CSV as all other rows.
This is also true for supplemental source files that cannot be imported to LEAP
directly. These rows are identified by branch path prefixes such as
`Age Profile/<age>/...`, `Vintage Profile/<vintage_year>/...`, or
`PHEV Electric Utilisation Rate/...`. This allows them to coexist with vehicle
and drive rows without reserving a special branch-path position for profiles,
which would be more brittle and require more remapping from the transport
export.

The convention is:

```text
Age Profile/<age>
Vintage Profile/<vintage_year>
PHEV Electric Utilisation Rate/<passenger_or_freight>
Reconciliation/<weight_or_bound>/<measure_or_fuel>
```

Examples:

```text
Age Profile/5
Vintage Profile/2015
PHEV Electric Utilisation Rate/passenger
Reconciliation/weight/Fuel Economy
```

The prefix, such as `Age Profile`, `Vintage Profile`, `PHEV Electric
Utilisation Rate`, or `Reconciliation`, signals the row type. Downstream readers
detect profile rows by checking whether the path starts with a known profile
prefix, then extract the index from the next path segment. No positional
assumptions are needed about the rest of the path.

Factors and scalars that are not year-specific can also be put in the same long
CSV with `Year = BASE_YEAR` and a clear variable name, such as `PHEV Electric
Utilisation Rate`. This avoids the need for a separate profile file or format,
and it keeps all Module 1 assumptions in one place.

### File naming

Generated CSV files use a fixed economy-only name and overwrite on each
regeneration:

```text
road_module1_values_<ECONOMY>.csv
```

Example:

```text
road_module1_values_20_USA.csv
```

Old names such as `road_module1_default_filled_inputs.csv` should be treated as
legacy compatibility only and phased out of documentation and new workflows.

## 6. Measure and branch scope

### Base-year focus

Module 1 is mainly a base-year data request. The current base year is recorded
in code as `BASE_YEAR` and should be consistent across source files, generated
defaults, UI labels, and downstream exports.

Future-year rows may be present for viewing, optional future assumptions, or
future UI expansion. They are not required for the current researcher workflow
unless the variable explicitly says so.

One future option is allowing researchers to fill future-year values for
variables such as sales shares or fuel economy improvements. Those values could
then be used by `leap_road_model` to project future stock and energy before
LEAP handoff. For now, the focus is on getting the base-year defaults right and
allowing optional future-year values without making them a requirement. If
future-year values become a normal input, add explicit `START_YEAR`,
`BASE_YEAR`, and `END_YEAR` constants and document which variables require which
years.

### Branch structure principle

Keep branch paths and variable names as close as practical to the
`leap_transport` export and final LEAP import structure. This reduces remapping
and makes values easier to trace.

Some simplification is expected because the new road model structure is simpler
than the older `leap_transport` output. Any recategorization should be explicit
and documented in `UPDATE_METHOD.md`.

### Current scope policy

Current road scope:

- Passenger: LPVs, Motorcycles, Buses.
- Freight: Trucks, LCVs.
- LPVs use `small`, `medium`, and `large` size labels within their drive types
  (e.g., `ICE small`, `BEV medium`).
- Trucks use `medium` and `heavy` size labels within their drive types
  (e.g., `ICE medium`, `BEV heavy`).
- `HEV` and `EREV` are LPV-only.
- PHEV is only used for LPV and LCVs, not trucks. The `PHEV Electric
  Utilisation Rate` variable captures the degree of electric use for PHEVs and
  is specified for passenger and freight separately.
- LCVs are freight.

### Vehicle/drive/size validity matrix

The current intended branch matrix is:

| Vehicle type | Valid drive families | Valid size labels |
|---|---|---|
| LPVs | ICE, HEV, EREV, PHEV, BEV, FCEV | small, medium, large |
| Motorcycles | ICE, BEV, FCEV | none |
| Buses | ICE, BEV, FCEV | none |
| LCVs | ICE, PHEV, BEV, FCEV | none |
| Trucks | ICE, BEV, FCEV | medium, heavy |

`ICE` is a drive family here and may include fuel-specific source rows such as
gasoline, diesel, LPG, or CNG where those source rows exist. This matrix should
be the validation reference for Module 1 row generation and the branch-building
reference for `leap_road_model` Module 2. Source rows outside this matrix should
be rejected during Module 1 generation or handled by an explicit documented
recategorization rule before export.

### Measures needed by Modules 2-7

Core base-year measures:

| Variable | Typical branch level | Notes |
|---|---|---|
| `Stock` | Vehicle/drive/size where available | Needed by Module 2 and Module 6 energy calculations. |
| `Mileage` or `Average Mileage` | Vehicle or vehicle/drive | Use clear units, usually km/vehicle/year. |
| `Fuel Economy` | Vehicle/drive/fuel where available | Canonical Module 1 name. Legacy `Final On-Road Fuel Economy` can be read as an alias. |
| `Sales Share` | Vehicle/drive | Used by Module 5. |
| `Stock Share` | Vehicle type and, where present, lower vehicle/drive levels | Vehicle-type stock split uses the five LEAP rows `Demand\Passenger road\LPVs`, `Demand\Passenger road\Motorcycles`, `Demand\Passenger road\Buses`, `Demand\Freight road\Trucks`, and `Demand\Freight road\LCVs`; lower-level stock-share rows are not used for Module 3 vehicle-type splits. Base-year shares are derived automatically from base-year Stock rows. Default anchor values at 2040 and 2060 are seeded to the base-year share; researchers can edit them to define a trajectory. Anchor years are fixed at 2040 and 2060 (`STOCK_SHARE_PROJECTION_YEARS`) - making them researcher-configurable was considered but not implemented. |
| `Device Share` | Drive/fuel | Useful for fuel split defaults and checking. |
| `PHEV Electric Utilisation Rate` | Vehicle-level factor only for LPV and LCVs since they are the only vehicle types using PHEVs | Used by Module 6 before normal fuel reconciliation. |
| `Passenger Saturation` | Economy-level factor | Used by Module 3. |
| `Vehicle Equivalent Weight` | Vehicle type | Used by Module 3. |
| `Reconciliation Weight` and scalar bounds | Transport/fuel/measure factor | Used by Module 6. |
| Survival profile values | Profile branch | Used by Module 4. |
| Vintage profile values | Profile branch | Used by Module 4. |

This table is not exhaustive. When adding a measure, first ask which Module 2-7
function needs it and what branch level that function expects.

## 7. Researcher UI workflow

### What the UI should do

The UI should:

- load generated defaults from the static CSV bundle or backend;
- show branch paths, variables, units, source notes, and comments clearly;
- let researchers fill or edit `Value`, `Comment`, and source-related fields;
- prevent key columns from being edited;
- export the current rows as a flat CSV;
- allow the same flat CSV to be reuploaded later; and
- report validation issues before a model run is attempted.

### What the UI should not do

The UI should not:

- create new data rows;
- let users change branch paths, variables, scenarios, economies, or years;
- silently accept missing default packages;
- silently accept new uploaded keys;
- accept uploads that are missing key columns; or
- require researchers to understand the full LEAP workbook format.

### CSV reupload rule

Reupload should be strict:

1. Require the canonical CSV columns.
2. Match uploaded rows to existing rows by key.
3. Apply changes only to editable value/comment/source columns.
4. Raise an error for new keys or modified key columns.
5. Keep a summary of changed values for review.

A partial upload can be allowed only if it clearly contains a subset of existing
keys and all required key columns are present.

The browser and backend validate reuploads against the long-row key
`Economy, Scenario, Branch Path, Variable, Year`. Uploads may update only
`Value`, `Comment`, and `Source`; new keys, duplicate uploaded keys, and missing
key columns are rejected before any values are applied.

## 8. Validation and review

Validation should start small and be useful. It does not need to duplicate every
Module 6 reconciliation check.

Module 1 validation should include:

- required source files exist;
- source CSVs have required columns;
- generated rows have complete key columns;
- no duplicate keys;
- values are numeric where the variable requires numeric input;
- units are present for important numeric measures;
- uploaded CSVs do not add or mutate keys;
- required base-year rows have values;
- shares are between 0 and 1 where applicable;
- obvious share groups sum to 1 where the grouping is unambiguous; and
- comments or source notes are present for researcher overrides where possible.

### Static row contract

`back-end/data/road_model/config/road_module1_static_contract.csv` is the
authoritative static row contract. It has one row per `(Branch Path, Variable)`
pair and controls four things:

- `Current Accounts`: whether the row must be present in the **Current Accounts**
  scenario output for every economy.
- `Projected Scenario`: whether the row must also be present in every
  **non-Current Accounts scenario** (Target and any other projected scenarios
  included in a run). Set this to `True` for any variable that researchers
  supply forward projections for, not just a base-year value.
- `Shown In Interface`: whether the row is visible in the editable browser UI.
  Hidden rows remain part of downloads/uploads and model runs.
- `Units`: the units in which the user must provide values, after the scale
  factor from `road_module1_default_parameters.json` has been applied. This
  string is displayed in the interface.

`build_road_model_static_defaults.py` enforces the contract as a hard error at
the end of every build. Three checks run per economy:

1. **No uncontracted rows** — every (Branch Path, Variable) in the output must
   appear in the contract.
2. **Current Accounts completeness** — every row with `Current Accounts = True`
   must be present in the Current Accounts scenario output.
3. **Projected scenario completeness** — every row with
   `Projected Scenario = True` must be present in every non-Current Accounts
   scenario output.

Checks 2 and 3 allow an exemption for fuel-level rows (`Mileage`, `Fuel Economy`)
that are explicitly excluded for that economy via
`road_module1_static_fuel_branch_exclusions.csv`.

Additionally, a fuel-level rule applies independently of the contract: every
fuel-level branch path (depth 5) that appears in the output must have **both**
`Mileage` and `Fuel Economy` rows. These variables are not listed individually
in the contract because the active fuel branches differ by economy.

Currently all 581 contract rows have `Current Accounts = True`. The 41
`Sales Share` rows also have `Projected Scenario = True` — Sales Share is the
main researcher policy lever and must be supplied for both the base year and
all forward projection years. All other variables are base-year calibration
inputs that are fixed across scenarios.

**When to update the contract:** edit `config/road_module1_static_contract.csv`
directly in any text editor or spreadsheet tool whenever the row set, required
status, projected status, units, or interface visibility changes. The file is a
plain CSV with no formulas or hidden structure. Update
`config/road_module1_static_fuel_branch_exclusions.csv` only when the ESTO-zero
fuel evidence changes. Module 6 remains responsible for final ESTO energy
reconciliation checks, Device Share validation, PHEV utilisation diagnostics,
and scalar-bound diagnostics.

## 9. Optional backend and model run integration

The static browser workflow is the current default. The site may eventually be
merged into a larger application with a backend, but ideally the Module 1 UI
should be kept deployable as a static GitHub Pages site without a rewrite. That
means the backend must read the same source files or generated CSV package that
the static bundle uses; it should not become a second source of truth for
defaults.

The backend is currently useful mainly for running `leap_road_model`. There are
no other functionalities that have been identified as needing a backend at this
time.

## 10. Downstream interface to leap_road_model

`leap_road_model` should receive a versioned Module 1 data package with:

- the canonical long Module 1 CSV for each economy;
- a manifest with version, generation date, base year, source files, and script
  names;
- any validation report generated during packaging; and
- optional static CSV files only if needed for UI caching, not as the primary
  downstream contract (the long CSV package is already the primary artifact).

The downstream reader should:

- fail on duplicate keys;
- fail on missing required columns;
- require canonical underscore economy codes, with temporary legacy conversion
  only if old no-underscore packages still need to be read;
- parse `Year`/`Value` long rows into the tables Modules 2-7 need;
- convert aliases and structures where necessary, such as `Final On-Road Fuel Economy` to `Fuel Economy` or profile rows into Module 4 profile tables; and
- preserve source and comment metadata for diagnostics.

### Running Modules 2-7 without the website

The website does not need to be running for `leap_road_model` to run. The
pre-generated Module 1 outputs committed to this repo under
`back-end/outputs/road_module1_defaults/` are sufficient. Use
`leap_road_model/scripts/offline_workflow.py` to run the full Modules 2-7
pipeline offline — it discovers the sibling repo's outputs automatically.

`leap_road_model` still loads population, GDP, ESTO energy, and other non-Module
1 inputs from its own data/config pathways. These are datapoints that we do not
expect the researcher to edit. If any of those measures need to be editable by
researchers in the future, add them to Module 1 and have `leap_road_model` read
them from the same package.

## 11. Versioning and update method

### Generated output naming

Generated files are written into dated version folders under
`back-end/outputs/road_module1_defaults/`. Treat old version folders as
immutable snapshots; do not keep writing new production runs into an old
version folder. Per-economy CSV files use a fixed name inside each version:

```text
road_module1_values_<ECONOMY>.csv
```

The static CSV bundle served to the UI lives at a fixed path inside
`front-end/road-module1-static/` and is replaced on each regeneration. It must
be regenerated from the same backend output version before uploading/deploying
the website.

Use a version name like:

```text
vYYYY_MM_DD_<short_label>
```

Use `_tmp_...` version names or `back-end/outputs/archive/` for exploratory
runs that should not be committed or served.

### Updating source data

When the source files in `back-end/data/road_model/` are updated:

1. Archive old source files if they are being replaced.
2. Add or update the script that transforms the source into canonical rows.
3. Record the method in `UPDATE_METHOD.md`.
4. Regenerate the Module 1 packages.
5. Regenerate the static CSV bundle for the UI.
6. Run validation and inspect changed rows.
7. Commit source files, method notes, generated outputs, and docs together.

### Regenerating defaults and static values

Use this workflow when source data changes, when the static row contract changes,
or when operator visibility flags such as `Shown In Interface` are edited.

1. Update source/config files under `back-end/data/road_model/`.
   - Numeric source changes belong in source folders such as
     `processed_source/`, `supplemental_source_files/`, or
     `final_value_overrides/`.
   - Static row scope, projected-scenario requirements, units, and browser
     visibility belong in `config/road_module1_static_contract.csv`.
   - Economy-specific missing fuel branch exceptions belong in
     `config/road_module1_static_fuel_branch_exclusions.csv` and must use the
     reason `0 data for fuel in esto dataset`.
2. Run the single generation entry point from `road_model_inputs_interface`:

```powershell
python back-end\build_road_model_static_defaults.py
```

3. Confirm the script reports generated economies and:

```text
Static contract check passed
```

4. Inspect the regenerated backend packages under:

```text
back-end/outputs/road_module1_defaults/<VERSION>/<ECONOMY>/
```

5. Inspect the regenerated browser package under:

```text
front-end/road-module1-static/<VERSION>/<ECONOMY>.csv
```

The static CSV is what the browser loads. Editing the workbook alone is not
enough; the generator must be rerun so the CSVs receive the updated
`Shown In Interface` values.

### Showing or hiding rows in the interface

The operator-facing switch for browser visibility is the `Shown In Interface`
column in:

```text
back-end/data/road_model/config/road_module1_static_contract.csv
```

To show or hide a row, open the CSV in any text editor or spreadsheet tool,
set `Shown In Interface` to `True` or `False` for the relevant
`(Branch Path, Variable)` rows, save, then regenerate:

```powershell
python back-end\build_road_model_static_defaults.py
```

Then reload the browser page so it fetches the regenerated static CSV.

Hidden rows are still preserved in downloads/uploads and still sent to
`leap_road_model`; they are only removed from the editable browser view.

To require a variable in projected (Target) scenarios, set its
`Projected Scenario` to `True` in the same CSV and regenerate.

## 12. Current implementation map

Current files that matter:

| File | Current role |
|---|---|
| `back-end/core/road_module1_defaults.py` | Main default-generation logic and source readers. |
| `back-end/build_road_model_static_defaults.py` | Single source-backed generation script for Module 1 packages, the filtered static bundle, and static-bundle validation. |
| `back-end/api/run_model_router.py` | Optional local backend route for writing Module 1 rows and launching `leap_road_model`. |
| `front-end/road-module1-static/` | Generated static CSV bundle (long-row format) served to the browser UI. |
| `back-end/data/road_model/UPDATE_METHOD.md` | Numeric data update method log. |

Some older code and output folders still use names such as
`road_module1_default_filled_inputs.csv` and produce wide year columns. Treat
that as current implementation debt. The target contract is the long CSV
described here.

## Appendix A: Road Branch Tree and Module 1 Measures

This appendix summarizes the implemented road branch structure and the Module 1
measures required at each level of the tree. It is intended as a compact
reference for diagrams, static-contract checks, and handoff discussions.

The taxonomy comes from `codebase/config/vehicle_mappings.yaml` and
`codebase/config/fuel_mappings.yaml` in `leap_road_model`. The measure placement
reflects the current Module 1 static contract used by the interface. One current
mismatch is worth noting: the model taxonomy allows `FCEV` for `Motorcycles` and
`LCVs`, but the current static contract does not require `Motorcycles\FCEV` or
`LCVs\FCEV` rows.

Data density labels show the minimum interface density at which each measure is
visible in the researcher UI: **[Less]** = visible at the default (Less) density;
**[More]** = requires More density; **[Ultra]** = requires Ultra density.

```text
Demand

  Passenger road
    Measures:
      Passenger Vehicle Saturation                          [More]
      Passenger Saturation Reached                          [More]
      Passenger Stock Growth Rate Adjustment                [More]
      Reconciliation Weight Stock                           [More]
      Reconciliation Weight Mileage                         [More]
      Reconciliation Weight Efficiency                      [More]
      Reconciliation Bound Lower Mileage                    [More]
      Reconciliation Bound Upper Mileage                    [More]
      Reconciliation Bound Lower Efficiency                 [More]
      Reconciliation Bound Upper Efficiency                 [More]
      PHEV Electric Driving Share                           [More]

    Turnover calibration
      Measures:
        Turnover Rate Bound Lower                           [More]
        Turnover Rate Bound Upper                           [More]

    Age <0-37>
      Measures:
        Survival Rate                                       [More]
        Vintage Profile Share                               [More]

    LPVs [sizes: small, medium, large]
      Measures:
        Stock                                               [Less]
        Stock Share                                         [Less]
        Sales Share                                         [Less]
        Vehicle Equivalent Weight                           [More]

      ICE <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Motor gasoline, Gas and diesel oil, Natural gas, LPG, LNG,
          Biogasoline, Biodiesel, Biogas, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      HEV <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Motor gasoline, Gas and diesel oil,
          Biogasoline, Biodiesel, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      EREV <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Electricity, Motor gasoline, Biogasoline, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      PHEV <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Electricity, Motor gasoline, Biogasoline, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      BEV <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Electricity
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      FCEV <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Hydrogen
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

    Motorcycles
      Measures:
        Stock                                               [Less]
        Stock Share                                         [Less]
        Sales Share                                         [Less]
        Vehicle Equivalent Weight                           [More]
        Vehicle Equivalent Weight Lower Bound               [More]
        Vehicle Equivalent Weight Upper Bound               [More]

      ICE
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Motor gasoline, Gas and diesel oil, Natural gas, LPG, LNG,
          Biogasoline, Biodiesel, Biogas, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      BEV
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Electricity
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      FCEV
        Note:
          Valid in model taxonomy, but not currently present in the static contract.

    Buses
      Measures:
        Stock                                               [Less]
        Stock Share                                         [Less]
        Sales Share                                         [Less]
        Vehicle Equivalent Weight                           [More]
        Vehicle Equivalent Weight Lower Bound               [More]
        Vehicle Equivalent Weight Upper Bound               [More]

      ICE
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Motor gasoline, Gas and diesel oil, Natural gas, LPG, LNG,
          Biogasoline, Biodiesel, Biogas, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      BEV
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Electricity
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      FCEV
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Hydrogen
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

  Freight road
    Measures:
      Freight GDP Elasticity Adjustment                     [More]
      Reconciliation Weight Stock                           [More]
      Reconciliation Weight Mileage                         [More]
      Reconciliation Weight Efficiency                      [More]
      Reconciliation Bound Lower Mileage                    [More]
      Reconciliation Bound Upper Mileage                    [More]
      Reconciliation Bound Lower Efficiency                 [More]
      Reconciliation Bound Upper Efficiency                 [More]
      PHEV Electric Driving Share                           [More]

    Turnover calibration
      Measures:
        Turnover Rate Bound Lower                           [More]
        Turnover Rate Bound Upper                           [More]

    Age <0-37>
      Measures:
        Survival Rate                                       [More]
        Vintage Profile Share                               [More]

    Trucks [sizes: medium, heavy]
      Measures:
        Stock                                               [Less]
        Stock Share                                         [Less]
        Sales Share                                         [Less]

      ICE <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Motor gasoline, Gas and diesel oil, Natural gas, LPG, LNG,
          Biogasoline, Biodiesel, Biogas, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      BEV <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Electricity
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      FCEV <size>
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Hydrogen
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

    LCVs
      Measures:
        Stock                                               [Less]
        Stock Share                                         [Less]
        Sales Share                                         [Less]

      ICE
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Motor gasoline, Gas and diesel oil, Natural gas, LPG, LNG,
          Biogasoline, Biodiesel, Biogas, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      PHEV
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Electricity, Motor gasoline, Biogasoline, Efuel
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      BEV
        Measures:
          Stock Share                                       [Less]
          Sales Share                                       [Ultra]
        Fuels:
          Electricity
        Fuel-level measures:
          Mileage                                           [Less]
          Fuel Economy                                      [Less]
          Mileage correction factor                         [Ultra]
          Fuel Economy correction factor                    [Ultra]

      FCEV
        Note:
          Valid in model taxonomy, but not currently present in the static contract.
```

## Appendix B: Module 1 Measures by Branch Level

This appendix describes the same Module 1 measure placement without dictating
the actual branch taxonomy. Use it when designing diagrams or validation logic
that should apply to branch levels rather than to specific vehicle, drive, or
fuel names.

Data density labels are the same as Appendix A: **[Less]**, **[More]**, **[Ultra]**.

```text

Transport level
  Example path shape:
    Demand\<Passenger road or Freight road>
  Measures:
    Passenger-only:
      Passenger Vehicle Saturation                          [More]
      Passenger Saturation Reached                          [More]
      Passenger Stock Growth Rate Adjustment                [More]
    Freight-only:
      Freight GDP Elasticity Adjustment                     [More]
    Passenger and freight:
      Reconciliation Weight Stock                           [More]
      Reconciliation Weight Mileage                         [More]
      Reconciliation Weight Efficiency                      [More]
      Reconciliation Bound Lower Mileage                    [More]
      Reconciliation Bound Upper Mileage                    [More]
      Reconciliation Bound Lower Efficiency                 [More]
      Reconciliation Bound Upper Efficiency                 [More]
      PHEV Electric Driving Share                           [More]

Turnover-calibration level
  Example path shape:
    Demand\<transport>\Turnover calibration
  Measures:
    Turnover Rate Bound Lower                               [More]
    Turnover Rate Bound Upper                               [More]

Age-profile level
  Example path shape:
    Demand\<transport>\Age <0-37>
  Measures:
    Survival Rate                                           [More]
    Vintage Profile Share                                   [More]

Vehicle-type level
  Example path shape:
    Demand\<transport>\<vehicle type>
  Measures:
    Stock                                                   [Less]
    Stock Share                                             [Less]
    Sales Share                                             [Less]
    Vehicle Equivalent Weight                               [More]
    Vehicle Equivalent Weight Lower Bound                   [More]
    Vehicle Equivalent Weight Upper Bound                   [More]
  Notes:
    Vehicle Equivalent Weight bounds are currently used for some passenger
    vehicle types. Freight vehicle types currently require Stock, Stock Share,
    and Sales Share only.

Drive or drive-size level
  Example path shapes:
    Demand\<transport>\<vehicle type>\<drive>
    Demand\<transport>\<vehicle type>\<drive> <size>
  Measures:
    Stock Share                                             [Less]
    Sales Share                                             [Ultra]

Fuel level
  Example path shapes:
    Demand\<transport>\<vehicle type>\<drive>\<fuel>
    Demand\<transport>\<vehicle type>\<drive> <size>\<fuel>
  Measures:
    Mileage                                                 [Less]
    Fuel Economy                                            [Less]
    Mileage correction factor                               [Ultra]
    Fuel Economy correction factor                          [Ultra]
```

Condensed rule of thumb:

```text
Transport level:
  growth controls [More], reconciliation controls [More], turnover controls [More], age profiles [More]

Vehicle-type level:
  Stock [Less], Stock Share [Less], Sales Share [Less], vehicle-equivalent weights [More]

Drive or drive-size level:
  Stock Share [Less], Sales Share [Ultra]

Fuel level:
  Mileage [Less], Fuel Economy [Less], correction factors [Ultra]
```
