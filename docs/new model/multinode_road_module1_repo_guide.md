# Road Module 1 comprehensive guide

This is the main design and implementation guide for Road Module 1 in
`road_model_inputs_interface`. Keep this file as the source of truth for Module
1 behavior. The shorter docs in this folder should point back here rather than
restate the same contract.

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

Use "supplemental source merge" for this behavior: the transport export supplies
most defaults, and specific files supply measures that are absent or weaker
there. Only describe something as an ordered replacement operation if the code
actually implements that ordering.

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

![Road Module 1 workflow diagram](Road%20Module%201%20workflow%20diagram.png)

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
| `Stock Share` | Vehicle type and, where present, lower vehicle/drive levels | Vehicle-type stock split uses the five LEAP rows `Demand\Passenger road\LPVs`, `Demand\Passenger road\Motorcycles`, `Demand\Passenger road\Buses`, `Demand\Freight road\Trucks`, and `Demand\Freight road\LCVs`; lower-level stock-share rows are not used for Module 3 vehicle-type splits. Base-year shares are derived automatically from base-year Stock rows. Default anchor values at 2040 and 2060 are seeded to the base-year share; researchers can edit them to define a trajectory. Anchor years are fixed at 2040 and 2060 (`STOCK_SHARE_PROJECTION_YEARS`) — making them researcher-configurable was considered but not implemented. |
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

Module 6 remains responsible for final ESTO energy reconciliation checks,
Device Share validation, PHEV utilisation diagnostics, and scalar-bound
diagnostics.

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

## 12. Current implementation map

Current files that matter:

| File | Current role |
|---|---|
| `back-end/core/road_module1_defaults.py` | Main default-generation logic and source readers. |
| `back-end/build_road_model_static_defaults.py` | Strict source-backed generation script for static deployment. |
| `back-end/road_module1_defaults_workflow.py` | Notebook-style workflow for package/static-bundle generation. |
| `back-end/api/run_model_router.py` | Optional local backend route for writing Module 1 rows and launching `leap_road_model`. |
| `front-end/road-module1-static/` | Generated static CSV bundle (long-row format) served to the browser UI. |
| `back-end/data/road_model/UPDATE_METHOD.md` | Numeric data update method log. |

Some older code and output folders still use names such as
`road_module1_default_filled_inputs.csv` and produce wide year columns. Treat
that as current implementation debt. The target contract is the long CSV
described here.

## 13. Roadmap

### Phase 1: Stabilize documentation and source policy

- Keep this guide as the single comprehensive Module 1 guide.
- Clarify that source files in `back-end/data/road_model/` are mandatory.
- Clarify that researcher uploads edit existing rows only.

### Phase 2: Move generated outputs to long CSV

- Add a long CSV writer with `Year` and `Value`.
- Keep any old wide CSV output only as a temporary compatibility artifact.
- Add strict upload validation against the long-row key.
- Keep generated output filenames stable and overwrite in place.

### Phase 3: Improve source processing from leap_transport exports

- Build a clear script for processing `leap_transport` output into Module 1
  rows.
- Current preprocessing entry point: `back-end/scripts/prepare_road_source.py`.
  It writes per-economy intermediate CSVs under
  `back-end/data/road_model/processed_source/` with columns
  `Branch Path, Variable, Scenario, Year, Value, Units`.
- Record the transformation in `UPDATE_METHOD.md`.
- Document any recategorization needed to fit the simpler road model structure.
- Keep branch paths and variable names close to source where practical.

### Phase 4: Align leap_road_model reader

- Update the Module 1 reader in `leap_road_model` to consume the long CSV
  package.
- Map lifecycle/vintage rows into Module 4 profile inputs.
- Update the `leap_road_model` Markdown once the Module 1 contract is stable.

### Phase 5: Decide whether a static CSV cache remains necessary

- Measure whether direct processing is fast enough for the UI/backend.
- Keep the static CSV bundle if it remains useful for GitHub Pages deployment,
  validation, or pre-publication checks.
- Do not add extra cache layers unless they solve a real performance or
  validation problem.

## 14. Open questions

These are the only open questions that seem worth keeping after the note pass:

1. ~~Should `Profile Index` be the final name for lifecycle/vintage age/profile
   rows, or should it be split into `Age` and `Vintage Year`?~~ Resolved: no
   separate column. Profile rows use branch path prefixes `Age Profile/<index>/...`
   and `Vintage Profile/<index>/...` instead.
2. ~~Should the canonical Module 1 economy code be no-underscore (`20USA`) or
   underscore (`20_USA`)?~~ Resolved: always use underscore economy codes in this
   repo and downstream code.
3. ~~Do we want partial researcher CSV uploads, or should every reupload be a
   full exported template?~~ Resolved: partial uploads are allowed only when they
   contain a subset of existing keys and all required key columns. Add a small UI
   note explaining this rule.
4. ~~How much future-year input should Module 1 support in the first long-CSV
   implementation, beyond optional rows for variables that already have future
   source values?~~ Resolved for `Stock Share`: 2040 and 2060 anchor rows are
   generated automatically. For other variables, future-year rows remain optional
   and are present only when source data includes them.
5. Should the static CSV bundle remain the normal UI artifact, or should a
   backend serve the long rows directly when available? (The formats are now
   identical so there is no format migration cost either way.)
6. Should this guide include front-end UI guidance: target user experience, the
   most important fields to show, how much source and validation detail to show
   per row, and how much help text to include?
