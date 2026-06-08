# Road Module 1 static bundle

This folder contains generated UI data for static/client-side deployments.

The files here are not the source of truth. They are generated from source files
in:

```text
back-end/data/road_model/
```

If required source files are missing, regenerate/fix the source package rather
than hand-editing this static bundle.

## Required files

- `index.json`
  - available versions, economies, and the default version.
- Defaults CSV files by version/economy, for example:
  - `v2026_06_05_road_module1_sources/20USA.csv`

## CSV format

Each per-economy CSV uses the same long-row format as the 'download filled CSV'
and 'upload filled CSV' actions in the browser UI. The columns are:

```text
Economy, Scenario, Branch Path, Variable, Year, Value, Scale, Units, Source, Comment, Input Status, Shown In Interface
```

This means the static bundle, the CSV download, and the CSV upload all share one
schema â€” there is no separate JSON serialisation step.

The static CSV is also the source used for interface-driven model runs. When the
browser calls the local run-model API, it sends the completed long rows from the
currently loaded static package; the backend writes those rows to
`leap_road_model/input_data/module1_defaults/<version>/<economy>/` before
launching `road_workflow.py`. The model-side file is therefore a runtime cache
of the interface package, not a separate defaults source.

Example row:

```csv
Economy,Scenario,Branch Path,Variable,Year,Value,Scale,Units,Source,Comment,Input Status,Shown In Interface
01AUS,Current Accounts,Demand\Passenger road\LPVs,Stock Share,2022,96.517,%,Share,transport_leap_export_combined_ALL_ECONS...xlsx,Loaded from preprocessed Road Module 1 source.,default,True
```

`Scale` is optional in older files. For numeric quantities, LEAP-style scale
labels such as `Thousand`, `Million`, or `Billion` are interpreted by the road
model as multipliers. Plural labels such as `Millions` are also accepted. `%`
is kept as a display/import scale for share rows.

Default generated scale labels are configured in
`back-end/data/road_model/road_module1_default_parameters.json` under
`scale_defaults_by_variable`. Current defaults emit `Stock` and `Sales` in
`Millions`, mileage variables in `Thousands`, and percentage/share variables
with `%`.

## How it is generated

Run `back-end/build_road_model_static_defaults.py` after any change to source
files in `back-end/data/road_model/`. This is the single supported generation
entrypoint. The script calls
`write_frontend_static_bundle()`, which:

1. Reads the versioned per-economy output packages from `back-end/outputs/road_module1_defaults/`.
2. Converts each economy's wide output to long format.
3. Filters to only `(Branch Path, Variable)` pairs listed in `back-end/data/road_model/config/road_module1_static_contract.csv`.
4. Applies `back-end/data/road_model/config/road_module1_static_contract.csv`, which verifies every generated static row key and fills `Shown In Interface`.
5. Writes one `{economy}.csv` per economy into `front-end/road-module1-static/{version}/`.
6. Rewrites `index.json` to list all available versions and economies.
7. Validates every economy's output against the **static row contract** (see below) and exits with an error if anything is missing or uncontracted.

## Row preservation

The static bundle generation step is allowed to filter rows to the documented
frontend contract:

- `back-end/data/road_model/config/road_module1_static_contract.csv` defines
  allowed `(Branch Path, Variable)` pairs, scenario required status, units, and
  whether each static row is shown in the interface.
- `back-end/data/road_model/config/road_module1_static_fuel_branch_exclusions.csv`
  defines economy-specific fuel branches that may be absent because ESTO has
  zero road data for the fuel in that economy.
- The fuel-level completeness rule in `build_road_model_static_defaults.py`
  requires every economy-specific fuel branch to have both `Mileage` and
  `Fuel Economy`.
- Branch parsing and normalisation in `back-end/core/road_module1_defaults.py`
  determines how source rows map into the road model tree.

After a row is present in a static CSV, the browser should preserve it
losslessly through load, edit, download/upload, and run-model export. Rows with
`Shown In Interface = False` are hidden from the editor but still carried to the
model run.

Some source-backed defaults may mostly be preserved rather than actively edited,
but the model still needs them to run. Examples include:

- `PHEV Electric Driving Share` for Module 6 PHEV electricity/liquid handling.
- `Survival Rate` and `Vintage Profile Share` for Module 4 turnover.
- passenger saturation, reconciliation weights/bounds, and vehicle equivalent
  weights for Modules 3 and 6.

For example, the `20USA.csv` static file in
`v2026_06_05_road_module1_sources` should include PHEV utilisation rows plus
age-profile rows. If `leap_road_model/input_data/module1_defaults/...` lacks
those variables while the static CSV has them, that model-side CSV is stale or
the browser/API hand-off dropped rows. It should be rewritten from the current
interface payload; do not treat the stale runtime file as source data.

## Structural validation

After writing the static bundle, `build_road_model_static_defaults.py` runs
checks against `back-end/data/road_model/config/road_module1_static_contract.csv`:

1. **Static contract check** - every generated `(Branch Path, Variable)` pair
   must exist in the CSV, and every CSV row flagged for `Current Accounts` or
   `Projected Scenario` must exist in the matching scenario output.

2. **Visibility application** - `Shown In Interface` is copied from the CSV
   into each generated static CSV. Operators can hide or show rows by editing
   this CSV, then regenerating the static bundle.

3. **Fuel-level rule** - every depth-5 branch (fuel-level, e.g.
   `Demand\Passenger road\LPVs\ICE large\Motor gasoline`) must have both
   `Mileage` and `Fuel Economy`. Missing fuel branches are allowed only when
   listed in `road_module1_static_fuel_branch_exclusions.csv` with reason
   `0 data for fuel in esto dataset`.

The checks are hard errors: the build fails loudly if anything is missing or a
generated row is not in the workbook. The workbook is the spec; edit it directly
when the branch tree, year coverage, or interface visibility changes.
## Optional backend mode

Static mode is the default. Optional backend helpers are only used when enabled
explicitly, for example:

```text
?roadBackend=1
```

The backend should read the same generated/source-backed rows as static mode. It
should not provide an alternative defaults source.

