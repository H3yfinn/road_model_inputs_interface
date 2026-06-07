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
Economy, Scenario, Branch Path, Variable, Year, Value, Units, Source, Comment, Input Status
```

This means the static bundle, the CSV download, and the CSV upload all share one
schema — there is no separate JSON serialisation step.

Example row:

```csv
Economy,Scenario,Branch Path,Variable,Year,Value,Units,Source,Comment
01AUS,Current Accounts,Demand\Passenger road\LPVs,Stock Share,2022,96.517,Share,transport_leap_export_combined_ALL_ECONS...xlsx,Loaded from preprocessed Road Module 1 source.
```

## How it is generated

Run `back-end/build_road_model_static_defaults.py` (or the equivalent workflow
cells in `back-end/road_module1_defaults_workflow.py`) after any change to source
files in `back-end/data/road_model/`. The script calls
`write_frontend_static_bundle()`, which:

1. Reads the versioned per-economy output packages from `back-end/outputs/road_module1_defaults/`.
2. Converts each economy's wide output to long format.
3. Filters to only variables listed in `FRONTEND_ALLOWED_VARIABLES` (defined in `build_road_model_static_defaults.py`).
4. Writes one `{economy}.csv` per economy into `front-end/road-module1-static/{version}/`.
5. Rewrites `index.json` to list all available versions and economies.
6. Validates every economy's output against the **required rows manifest** (see below) and exits with an error if anything is missing.

## Structural validation

After writing the static bundle, `build_road_model_static_defaults.py` runs two
checks against `back-end/data/road_model/road_module1_required_rows.csv`:

1. **Fixed structure check** — every `(Branch Path, Variable)` pair listed in
   the manifest must be present in every economy's output CSV.  This covers
   transport-level, vehicle-type-level, age-level, and drive-level rows.

2. **Fuel-level rule** — every depth-5 branch (fuel-level, e.g.
   `Demand\Passenger road\LPVs\ICE large\Motor gasoline`) must have both
   `Mileage` and `Fuel Economy`.  These rows are not in the manifest because the
   fuel mix is economy-specific.

Both checks are hard errors — the build fails loudly if anything is missing.
The manifest is the spec; never regenerate it from output.  Edit it directly
when the branch tree or measure scope changes.

## Optional backend mode

Static mode is the default. Optional backend helpers are only used when enabled
explicitly, for example:

```text
?roadBackend=1
```

The backend should read the same generated/source-backed rows as static mode. It
should not provide an alternative defaults source.
