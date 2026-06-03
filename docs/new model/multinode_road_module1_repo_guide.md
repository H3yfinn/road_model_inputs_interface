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
- it records sources, review flags, and validation results; > todo sources is good to include but review and validation seem over the top
- it exports one structured package per economy for downstream road modules.

The downstream `leap_road_model` repo should treat the Module 1 output from this
repo as the input contract for Modules 2-7.

Default deployment assumption for this guide:

- run largely as a static, client-side tool (for example GitHub Pages);
- no always-on server requirement;
- upload/checkpoint behavior is browser-side file processing by default;
- backend endpoints which allow for running the road model afterwards are optional local tooling, not the primary operational mode.

Static runtime behavior in the current frontend implementation:

- selector metadata is loaded from packaged static files first;
- provided-values defaults are loaded from packaged static files first;
- optional backend fallback/helpers are enabled only by explicit opt-in
  (for example `?roadBackend=1`, disabled with `?roadBackend=0`); > todo dont know wat this means
- if neither packaged defaults nor backend fallback is available, users can still
  continue by loading a checkpoint/values file in-browser. > todo this doesnt seem necessary. defaults are a key input. should never not be available. if they are missing, the workflow should fail and request data regeneration rather than silently allowing users to upload their own defaults. this is a key point of the data-sourcing policy 

Historical context that should guide implementation choices:

- before the new Module 1 design, the project already had broad default coverage
   through the `leap_transport` pipeline;
- `leap_transport` already performed 9th-edition to LEAP recategorisation;
- recategorisation between `leap_transport` output and Module 1 / `leap_road_model`
   input is intentionally minimal; > todo in fact we want to eventually stop using leap_transport as it is a bit non-useful to be using 9th data for more than a few years afterwards
- in practice, Module 1 defaults should be treated as near-direct use of
   `leap_transport` outputs > todo this is so so. we will use the leap-transport outputs where they suit but the simplified structure of the new road model is more important. 

### Data-sourcing policy (mandatory)

Road model data values must not be hard-coded in application logic.

All operational defaults and assumptions used by Module 1 and its UI must be
provided from source files under:

```text
back-end/data/road_model/
```

Allowed data-source file types:

- `.csv`
- `.xlsx` / `.xls`

Examples include:

- `road_model_default_input_workbook.xlsx`
- `apec_reconciliation_factors.csv`
- `apec_phev_utilisation_rates.csv`
- `apec_vehicle_equivalent_weights.csv`
- `apec_passenger_vehicle_saturation.csv`

Implementation rule:

- Code may implement transformations, validation, and rendering logic.
- Code must not embed road input datasets (economy lists, reconciliation
  values, saturation/mileage/efficiency defaults, etc.) as literal tables for
  runtime use.
- If source files are missing, fail clearly and request data regeneration; do
  not silently invent replacements.

Audit helper:

- `back-end/scripts/audit_road_model_data_sourcing.py` checks that required
  source files exist and that banned hard-coded runtime data markers are not
  present in `front-end/app.js`.

Practical contract split (recommended):

- Structure/control-plane (economy IDs/names, variable names, required columns,
  dataset shape) is defined in:
  - `back-end/data/road_model/road_model_structure_contract.json`
- Numeric operational values must come from CSV/XLSX/XLS files under:
  - `back-end/data/road_model/`
- Numeric-data update provenance should be recorded in:
  - `back-end/data/road_model/UPDATE_METHOD.md`
- Additional implementation guidance:
  - `docs/new model/road_model_data_contract_v1.md` > todo is this necessary?

---

## 2. Road Model Boundary

### What this repo owns

This repo owns Module 1: todo a lot of the things noted here are missing the makr. this should be more simple/ 

- economy list and economy name aliases used by the input workflow;
- road input row schema;
- default road input generation;
- PHEV utilisation overlay; > todo huh what does this mean?
- transport LEAP export overlay; todo huh what does this mean?
- researcher override capture from the UI; todo huh what does this mean?
- source and review metadata;
- unit, key, bounds, and structure validation;
- Module 1 output package writing.

### What `leap_road_model` owns

`leap_road_model` owns Modules 2-7: > todo maybe fill this out more 

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
and documented in this guide. > todo not true. the leap_road_model has some inputs such as population data and esto energy data. but generally yes the road model will get most of its data from this repo, and the contract should be clear about what that data is.

A key strength of this approach is that Module 1 defaults already use the same
structure as the output package. Because upstream `leap_transport` outputs are
already close to Module 1 shape, this is often close to direct reuse rather
than major remapping. This means `leap_road_model` can use those defaults as a
fallback when researchers do not provide overrides. Because defaults and
outputs share one format, updates are easier to manage and the interface
between repos stays simple and stable. > todo this is not that true anymore. I thinik the benefit of trying to keep a similar strucutre by using the branch path as the key identifier between rows is useful as it helps keep everything aligned and makes it easy to understand where evertyhign fits in, but there are also many columns in the original leap workbook structure that are unnecessary and we arent using in this strucutree, and instead using other column to capoture other information. so the structure is similar but not the same, and that is ok. we should just be clear about what the structure is and how it maps to the original leap transport outputs.

The target interface is:

```text
one flat CSV per economy
road_module1_default_filled_inputs_<ECONOMY>.csv > todo we should make sure there is datestamping and versioning in the filename to make it clear when files are updated and to avoid confusion between different versions of the same economy. maybe something like road_module1_default_filled_inputs_<ECONOMY>_20260601.csv
```

where the CSV contains the core Module 1 row keys and the base-year value.
`leap_road_model` can convert this to canonical codes such as `20_USA` when
needed.

---

## 3. Current Implementation Snapshot

As of the current repo state, the Road Module 1 workflow is partially
implemented and still partly CSV-based.

### Implemented today

Key implementation files:> todo what is being used in code here vs what is old code that ai thinks we need but is not a functionality i want

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

Current default packages are CSV-first, with optional workbook-style diagnostics
only where they are useful for local review.

Primary artifact per economy:

- `road_module1_default_filled_inputs_<ECONOMY>.csv`

Default-package diagnostic CSVs are optional debug artifacts and can be ignored
for normal workflows. Use them only when troubleshooting data quality,
validation, or overlay issues.

Current researcher output is one flat CSV per economy:

- `road_module1_default_filled_inputs_<ECONOMY>.csv`

Legacy workbook-style sidecars are transitional only and are cleaned up by the
current writer.

### Target output shape

The intended target is to consolidate those pieces into one flat CSV per
economy. Workbook-style sidecars may still be useful for debugging, but they
should not be the primary handoff contract.

### Downstream integration status (`leap_road_model`)

`leap_road_model` now includes an adapter and orchestrator wiring that treat
Module 1 defaults as the default upstream source for base-year assumptions in
`codebase/road_workflow.py`.

Current adapter behavior supports both naming conventions during transition:

- `road_module1_default_filled_inputs_<ECONOMY>.csv` (current writer default)
- `road_module1_default_filled_inputs.csv` (legacy compatibility)> todo lets move out of this./

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
2. Overlay economy-specific source data where available. > todo not really true. from the beginning the economy-specific source data is the main source of truth for the defaults. while there are multiple files in the inputs folderr they are generally sorted into groups of measures, with most data in the back-end\data\road_model\leap_import_workbooks files e.g. `transport_leap_export_combined_ALL_ECONS_20260601.xlsx` being the main source of truth for defaults, and the other files being used for specific overlays such as the PHEV utilisation overlay. so the leap_transport export is the main source of truth for defaults, and the workflow should be designed to use that as much as possible, while using other files for specific overlays where needed. > todo what is meant by overlays
3. Serve default-filled rows to the researcher UI.
4. Let the researcher review and override base-year values. > todo allow them to provide comments and sources for their overrides as well. review flags may be useful but i think the comments may allow for that without needing a separate flag. but we should make that clear in the UI and in the data contract. we want to be able to trace back any override to a source or a reason, and that should be captured in the data.
5. Validate the completed input package. > doesnt really seem necessary, but if they run the model in the backend it will run validation there and report any issues. maybe we could also run some basic validation in the UI before they export they interact with backend? i dunno
6. Export one structured flat CSV per economy.
7. Let `leap_road_model` read that CSV as Module 1 input.

### 4.1 Default assumptions

Defaults are seeded primarily from `leap_transport`-derived workbook inputs
(the all-economy seed workbook) and other source datasets under
`back-end/data/road_model/`. > todo i think eventually we should extract what we need from the leap_transport repo and then continue with lighter weight data sourcing or something more similar to the transport_data_system code which is built to clean and use data from a variety of sources, rather than relying on the 9th edition outputs as the main source of truth for defaults. but in the near term, we can use the leap_transport outputs as the main source of truth for defaults, and then build out a more robust data sourcing system over time that can pull from a wider variety of sources and do more cleaning and validation.

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

### 4.3 Transport LEAP export overlay > todo i odnt uynderstand htis section. wheat is it? where are the files? 

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
for editable years, currently focused on the base year. > todo make sure its clear that new rows cant be created asnd the keys cant be changed. they can only fill in values for existing rows. But what it does help wiht is allowing the user to fill in values programmatically rather than slowly, and then upload the csv again. This allows them to use their own tools and workflows to fill in values, which may be easier for some researchers than typing in the UI. It also allows them to keep a record of their filled-in values in a CSV file that they can save, share, and re-upload later if needed.

Overrides are keyed by:

```text
Branch Path, Variable, Scenario, Region, Year > todo double check this. also i think maybe we should have a year column and a value column instead of a column called 2022. this deosnt match elap but we can fix that with a simple pivot, and this way is jsut more flexible and easier to work with in csv form. 
```

In the default static workflow, those overrides are applied in browser state and
captured in exported checkpoint files. No server persistence is required. > old values tyhe resaerrcher fille din are saved via cookies and local browser storage, but the main record of their overrides should be the checkpoint CSV that they can export and re-upload later. if they want to save their work in progress, they can export a checkpoint CSV, and then re-upload it later to continue where they left off. this allows them to keep a record of their filled-in values in a CSV file that they can save, share, and re-upload later if needed, which is a bit more robust than relying on browser storage which can be cleared or lost if they switch devices. the checkpoint CSV is the main record of their overrides, and it can be moved between computers, emailed, archived, and reloaded as needed.

Browser drafts are convenience only. The portable record is the exported
checkpoint file that the researcher keeps and can re-load later.

If the optional backend is enabled, equivalent override payloads can also be
processed by backend routes for local tooling workflows.

### 4.5 Checkpoint export and reupload

The researcher UI supports a CSV checkpoint workflow. At the end of a work
session, the researcher can export the current values as
`road_module1_default_filled_inputs.csv`. On a later day, they can select the
same version, economy, and scenario, then upload that CSV through `Upload
Checkpoint / Values File`.

This is intended to be the portable record between sessions. Browser drafts can
help during one local browser session, but the checkpoint CSV is the file that
can be moved between computers, emailed, archived, and reloaded.

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
  are applied. > todo are these actualkly done?
- Only the core columns need to be populated for a row to matter: `Branch
  Path`, `Variable`, `Scenario`, `Region`, `Scale`, `Units`, `Per...`, and
  `2022`. 
- Extra columns may be blank or absent. Blanks and non-existent values are not
  used by the loader.
- Partial files are allowed: if only some rows or some columns are filled in,
  the loader uses the populated values and ignores the rest. > todo but a error should be raised if a row is new or if key columns are missing. we want to allow them to fill in just a few values, but we dont want them to accidentally create new rows or change the structure of the data. so if they upload a file that has new rows or is missing key columns, we should raise an error and ask them to fix it rather than silently accepting it.

Upload behavior:

- XLSX/XLS files prefer row-key input from `Details` when that sheet exists,
  otherwise from `Data`, otherwise from the first worksheet. > todo unsure if this is necessary. maybe we should just require them to use the `Data` sheet and not worry about the others? it might be simpler to just have one required sheet for uploads and not try to be flexible about it. we can always add more sheets later if we want, but for now it might be easier to just have one clear place for them to put their data.
- If present, `Factors`, `Lifecycle`, and `Vintage` are also parsed client-side
  and mapped into canonical row-key updates before overlay is applied. > todo probably want to pre-explain in somehwere above that these measures dont usually belong in the data strucutre since they are either imported into leap suing a different strucutre (like the strucutre of the files back-end\data\road_model\vehicle_survival_modified_00_APEC.xlsx and back-end\data\road_model\vintage_modelled_from_survival_00_APEC.xlsx are), or they are only used in the road_model before leap, in the case of the Factors. But its good to have everything mapped into the same structure before it gets applied as defaults, so we can keep the loader simple and just have one format to deal with. 
- CSV files are read directly.
- The file must keep the key columns:
  `Branch Path`, `Variable`, `Scenario`, `Region`, `Scale`, `Units`, `Per...`,
  and `2022`.
- For workbook-style uploads, if other sheets or columns are absent or partial,
  mapped updates can still contribute updates for matching canonical Module 1
  rows. > todo this is a bit complex i think. may be s=we ask them to just upload a flat CSV with the required columns and not worry about the other sheets. that means we should also only export csvs too. so maybe jsut export the Details sheet and Data is not used at all. 
- Future-year columns may be present, but the current researcher workflow is
  base-year first; later-year changes are handled in LEAP adjustment variables.
- Uploaded checkpoint values are overlaid client-side onto the currently loaded
  selection in browser state before the UI rerenders.
- The uploaded file must match the selected version/economy/scenario row keys.
  Rows that do not match are reported instead of silently creating new rows.

Validation for upload compatibility and value checks runs client-side in static
deployments. Backend validation is optional and should mirror the same rules
when backend mode is used.

### 4.6 Validation > todo do we even have code for this? perhaps we can have some basic validation related to module 6's reconciliation checks here if its not too hard?

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

Module 1 is a base-year data request. > todo add something like this, and malke sure the code uses a base year variable rather than hard coded 2022: The current base year is recorded as the variable `BASE_YEAR` in the code and should be consistent across all source files, defaults, and outputs. Future-year columns may be present for viewing or optional input, but the researcher workflow is focused on the base year and future-year values are not required. > todo we should make sure this is clear in the UI and in the data contract. we want to avoid confusion about whether future-year values are expected or required, since that is not the focus of the current workflow. we can allow them to fill in future-year values if they want, but we should make it clear that the main focus is on the base year and that future-year values are optional and not required.

Researchers should only be asked for values less than or equal to the base year
unless the LEAP adjustment-variable workflow changes. Future years can remain in
the schema for compatibility and viewing, but the researcher review UI should
not imply that future-year values are expected inputs. > todo no this isnt true. but if we do add stuff for future years we should also add variables such as end_year and make sure the UI and the data contract are clear about what is expected and required. we can allow them to fill in future-year values if they want, but we should make it clear that the main focus is on the base year and that future-year values are optional and not required.

The standard data request intentionally keeps some measures shared above the
vehicle or fuel level.

Current scope policy (used to prevent branch/scope mismatch flags): > todo note that this is compared to the leap_transport outputs, which have a bit more branch-level detail than the current road model structure. We trried to keep the same branch paths where possible, but some of the more detailed branches in leap_transport are not used in the current road model structure, and that is ok. FOr the most part the simplifcations we did make are easy to handle allocation with.

- keep `HEV` and `EREV` only under LPV branches;
- remove `HEV` and `EREV` from non-LPV vehicle types;
- remove truck `PHEV` branches;
- continue to use LPV drive-size labels as `small` / `medium` / `large`, and 'medium' and 'large' truck. We considered getting rid of this but it seems like a useful level of detail to keep for allocation and for matching to leap_transport outputs, as well as providing real-world meaning for researchers. 
- use `Fuel Economy` as the canonical efficiency variable name; > todo its not clear what the alternative was? efficiency? we should note this.
- keep researcher mileage input at shared vehicle-type scope, then expand to
  detailed fuel-level rows in exported outputs; > this loses detail wrt differences in m,ileage between drive types but it is a lot easier for researchers to provide mileage values at the vehicle-type level rather than the fuel-level, and we can still expand to fuel-level rows in the output for leap_road_model to use. if we find that we need more detail in mileage later, we can always add more rows for researchers to fill in, but for now it seems like a good balance to have them fill in mileage at the vehicle-type level and then expand it in the output.
- keep main `Stock` reporting at transport-type scope, with optional
  drive-level stock detail on a separate sheet when requested. > todo is this true. i dont think it is. i berleive we are reporting at the drive level and only for the leap import we are aggregating to the transport-type level. this detail allows us to calcualte energy use by drive type, reconcile eff/mielage/stocks with the esto road energy data. furethmroe, leap essentially requires a stock number for the drive level by naturee of its stock share asnd device share measures at the vehicle type and drive levels. 

| Measure | Standard scope | Notes | > todo is this everyhting?s
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

## 6. Target CSV Contract

The target Module 1 handoff is one flat CSV per economy:

```text
road_module1_default_filled_inputs.csv
```

Example:

```text
road_module1_default_filled_inputs.csv
```

This flat CSV is the primary contract between `multinode_energy_balance` and
`leap_road_model`.

### Sheet: `Data`

Purpose: LEAP-compatible scalar/base-year input rows.

This CSV should contain the rows that downstream modules need as tabular road
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
| `2030`, `2040`, `2050` | Optional viewing/projection columns where applicable. These may be blank or absent and will not be used when not needed. | > todo nope. as explained earlier we will replace this with a `Year` column and a `Value` column, which is more flexible and easier to work with in csv form. we can still pivot to the wide format for leap if needed, but the long format is easier to work with in csv form and allows for more flexibility in terms of which years are included without needing to change the schema.
Advice for filling rows:

- As long as the core columns above are filled in, other cells do not need to
  be specific values.
- Partial rows are fine when the intent is clear; blanks and missing optional
  values are ignored.
- Do not invent values just to satisfy unused columns.
- If a row is not relevant, leave it blank or omit it entirely.

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

Rows that should not be stored primarily in `Data`: > todo no lets go with the new way we are doiung it where evertythying is put into one csv with the same strucutre. the measures below will jsut need to use that strucutre. then it is up to the loader in module 2 to map theseback to their requires studcutres for the code, and then later on in the outptu from moduel 6 we provide eveyrhting in the actual strucutrre that is needed for the data, such as lweaps workbook sturcutre and the profiles strucutres (profiles strucutrtres are wt is deescrived in below sheet Lifecycle and Vintage - we should reuese their deescirptions somewhere to make this clear). This way we have one clear format for the data.
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

## 7. Optional Backend API Contract  > todo its not clear to me what is actuallly needed here if all we need is to be able to run the python road_model in the backend, maybe its justa  few endpoints such as whatever allows us to run the model using what is entered in the UI, and then whatever is needed to export the results form the road model, and acces sthe dashboard too. 
> todo related to above note, i havent read any of this section. 

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

## 8. Downstream Reader Contract for `leap_road_model` > tyodo obvsiously this will take into account ntoes ive made above and how it changes the ufn iuonlity here.n 

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

Reader logic should treat the following as canonical scope rules: > todo, this definitely shouldnt be needed as it should be andled by module 1. 

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
explicit, documented conversions where unavoidable. > todo very impoirtant point. the more we can keep the same branch paths and variable names as the leap_transport outputs, the easier it will be to implement the reader and the less likely we are to introduce errors in re-deriving values. if we do need to do some recategorisation or conversion, it should be explicit and well-documented, but the overall goal should be to keep it as simple and direct as possible. this means making the units and measures and varibale names we use, simple and understandble to the users and also as close as possible to the leap_transport outputs which were originally intendeed to be imported strtaight into leap, liek teh output from module 6 will bge, so we can just reuse those values directly in the reader without needing to do a lot of complex mapping or conversion )besides the aforementioned recategorisations_.

`leap_road_model` should not depend on the current CSV sidecar layout once the
workbook writer exists. > todo not sure what thsi means. 

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
tests first. > todo not sure what 'too many jobs' means. how can we simpligfy it? a lot of that stufdf seems like it may not be requried if our inptus and outptus are sturcutred right and the way things work is simplified/systematrised right?

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
enabled, backend checks should mirror the same rules. > todo we should look for ways to make this so less needs to be done by the backend, while keeping things fast. the mroe things here the lgihter the whole thing is and the less we need the backend to begin with . 

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

### Phase 2: Add workbook writer without removing CSV outputs > todo is this required after what was mentioned in my notes above

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
> todo right now i think having 3 .md files is a bit much. iuf we can create a single comprehensive guide that covers the workflow, the design, and the implementation details all in one place, that might be easier to maintain and reference than having separate files for each aspect. we can use clear section headings and a table of contents to make it easy to navigate within a single document. this way we have one go-to reference for everything related to Module 1, and we can keep it updated as the design evolves without needing to worry about keeping multiple documents in sync.
---

## 12. Rules for Future Changes > todo im not sure about this section as its hard for me to predct where things will go. i think the msot important thing is to keep things simple, keep relying on the csvs and workboks as sources of truth, and avoid adding too much complex logic in the code that is not also reflected in the data. if we can keep the data as the main source of truth and keep the code as simple as possible, that will make it easier to maintain and update in the future. we can also make sure to document any changes clearly in this guide so that future developers understand the rationale and the impact of any changes made to Module 1 behavior. And make sure eveyrhtiung always is built with modules 2-7 in mind, so we dont end up with a situation where we have to go back and change module 1 because we forgot about how it interacts with the other modules.

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
11. Do not hard-code road input data in frontend/backend runtime code; add or
  update source files in `back-end/data/road_model/` instead.

---

## 13. Open Design Questions

These need explicit decisions before the workbook becomes the only handoff: > todo none of these are relvant. but i am interested in whether we need a json file between the processing of the csv and xlsx inputs from back-end\data\road_model and the writing of the data to the UI. is it gfoing to be jsut as fast to have code which extrtacts data form the csv and xlsx files and then writes it directly to the UI, or do we need to have an intermediate json file that is written to disk and then read by the UI? if we can do it without the intermediate json file, that would be simpler and faster, but if we find that we need it for some reason (for example if the data processing is too slow to do on the fly), then we can add it in as a way to cache the processed data and make it faster for the UI to load. but ideally we would want to avoid adding an extra step of writing and reading from disk if we can just process the data in memory and pass it directly to the UI. > theres an extra bonus of having internmediate data, in that when we update data inputs then we can double chekc its formatted right and so on buy creating the intemedite inputs before pushing the enw data to the site, thereofr enotuiciung issues before they go live. 

| Question | Current leaning |
| --- | --- |
| Should `Data` include `Expression` and Level columns, matching strict LEAP import format? | Eventually yes if `Data` is meant to be directly importable to LEAP. For Module 1 reader use, the current tabular year-column format may be enough. |
| Should survival/vintage also remain in `Data` as rows for UI rendering? | They may remain internally for UI convenience, but the workbook contract should expose them through `Lifecycle` and `Vintage`. |
| Should `Factors` be generated from current rows or from a separate parameter table? | Generate from current rows first, then migrate to a clearer parameter table if needed. |
| Should `Details` include lifecycle and factor source metadata too? | Prefer yes, either in `Details` or separate diagnostic sheets. |
| Should the workbook contain all scenarios or one scenario? | Prefer all scenarios in one economy workbook unless file size or reviewer workflow argues otherwise. |
| Should `leap_road_model` tolerate old CSV packages? | Yes during transition, but workbook should be the preferred path. |

---

## 14. Quick Navigation > im not sure about this but i trust u i guess

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
