# Road model numeric data update method log

---

## Required rows manifest and structural validation (2026-06-05)

### What this is

`road_module1_required_rows.csv` (in this directory) is the authoritative
specification of what `(Branch Path, Variable)` pairs must be present in every
economy's frontend output CSV.  It covers the **fixed structure** of the model:
transport-level rows (reconciliation, passenger saturation), vehicle-type-level
rows (Stock Share, Sales Share, Vehicle Equivalent Weight), age-level rows
(Survival Rate, Vintage Profile Share), and drive-level rows (Sales Share,
Stock Share, PHEV Electric Driving Share).

Mileage and Fuel Economy are **not** in the manifest because their branches are
economy-specific (fuel mix varies by economy).  They are instead validated by a
rule: every depth-5 branch present in an economy's output must have both Mileage
and Fuel Economy.

### How it is enforced

`build_road_model_static_defaults.py` runs `_validate_output_completeness()`
after writing every economy's static CSV.  This function:

1. Loads `road_module1_required_rows.csv` and checks every listed
   `(Branch Path, Variable)` pair is present in the output.
2. Checks that every fuel-level branch (depth-5 branch path) has both
   `Mileage` and `Fuel Economy`.

If either check fails the build **errors and exits**.  No silent gaps.

### When to update the manifest

Edit `road_module1_required_rows.csv` directly whenever:

- A new vehicle type, drive, or supplemental variable is added to the model.
- A branch is removed or renamed.
- A new age range is introduced (change the age rows in the manifest).

Do not regenerate the manifest from the pipeline output — the manifest is the
spec that the pipeline is checked against, not a record of what happened to be
generated.

---

Use this file to record how numeric source files in `back-end/data/road_model/`
are produced or updated.

For a folder-level explanation of how the files in this directory are used, see
`back-end/data/road_model/README.md`.

The intended style is script-by-script record keeping. We do not need a large
general ingestion framework yet. We do need a clear audit trail for every source
file or generated default package that changes.

## Output versioning and tall CSV package

- Date: 2026-06-05
- Author: Codex, with user review required
- Change summary: Switched the active generated output version from the older
  `v2026_05_25_best_guess` folder to the dated
  `v2026_06_05_road_module1_sources` package, and documented that production
  generations should use immutable dated version folders.
- Source inputs:
  - `back-end/data/road_model/processed_source/road_module1_source_<ECONOMY>.csv`
  - `back-end/data/road_model/manually_filled_rows/`
  - `back-end/data/road_model/supplemental_source_files/`
  - `back-end/data/road_model/final_value_overrides/`
- Generation method:
  - Set `DEFAULT_VERSION = "v2026_06_05_road_module1_sources"` in
    `back-end/core/road_module1_defaults.py`.
  - Run `back-end/build_road_model_static_defaults.py` to regenerate all
    economy packages and the frontend static bundle from the same version.
- Recategorizations or mappings:
  - No new mapping changes. This is a packaging/versioning change.
- Output files changed:
  - `back-end/outputs/road_module1_defaults/v2026_06_05_road_module1_sources/`
  - `front-end/road-module1-static/`
  - `back-end/data/road_model/README.md`
  - `docs/new model/multinode_road_module1_repo_guide.md`
- Validation checks run:
  - Confirm all economy outputs use `road_module1_values_<ECONOMY>.csv`.
  - Confirm generated files use the tall `Economy, Scenario, Branch Path,
    Variable, Year, Value, Units, Source, Comment` format.
  - Run static source schema validation before generation.
- Notes/limitations:
  - Older files named `road_module1_default_filled_inputs_<ECONOMY>.csv` in
    older version folders are legacy wide-format artifacts. Treat them as
    historical snapshots, not the active package.

## Archived seed defaults (archived; not used by current Module 1 generation)

- Date: 2026-06-02
- Author: Codex, with user review required
- Change summary: Historical seed CSV files for Module 1 default vehicle
  types, drive shares, valid drive combinations, mileage, efficiency, and
  scalar assumptions. These files are archived and are not used when current
  Module 1 defaults are generated.
- Source inputs: Old hard-coded Python constants that used to live in
  `back-end/core/road_module1_defaults.py`. These were copied out only to
  preserve an audit record of the previous implementation.
- Generation method: Manual extraction from the previous Python constants into
  CSV files. This was a one-time archival step, not a current data-generation
  method.
- Output files changed:
  - `road_module1_default_vehicle_types.csv`
  - `road_module1_default_drive_shares.csv`
  - `road_module1_valid_drives_by_vehicle_type.csv`
  - `road_module1_default_mileage_km_per_year.csv`
  - `road_module1_default_efficiency_mj_per_km.csv`
  - `road_module1_default_assumptions.csv`
- Validation checks run: Import smoke check for `core.road_module1_defaults`;
  `back-end/scripts/audit_road_model_data_sourcing.py`.
- Notes/limitations: These archived seed defaults are retained only for
  historical traceability. They should not be treated as active sources or as
  fallback data.

- Archive update: On 2026-06-04, these seed CSVs were moved to
  `back-end/data/road_model/archive/seed_csv_defaults/`. Runtime Module 1
  generation no longer imports them. The active primary source path is
  `back-end/data/road_model/processed_source/road_module1_source_<ECONOMY>.csv`,
  with `road_model_default_input_workbook.xlsx` retained as a fallback while
  processed-source coverage is incomplete.

## Active supplemental source files

Active files in `back-end/data/road_model/supplemental_source_files/` and what they supply:

- `apec_phev_utilisation_rates.csv` — PHEV electric driving share by economy
- `apec_reconciliation_factors.csv` — reconciliation weights and scalar bounds (required by Module 6)
- `apec_vehicle_equivalent_weights.csv` — LPV-equivalent weights by vehicle type (Module 3)
- `apec_passenger_vehicle_saturation.csv` — saturation level by economy (Module 3)
- `apec_lifecycle_profile_factors.csv` — survival curve calibration parameters (Module 4)
- `vehicle_survival_modified_00_APEC.xlsx` — age-based survival probabilities (Module 4)
- `vintage_modelled_from_survival_00_APEC.xlsx` — base-year vintage age distribution (Module 4)

When any of these files is updated, add a dated entry to this log.

## Individual per-economy LEAP workbooks removed

- Date: 2026-06-05
- Author: Finn Maunsell
- Change summary: Confirmed that the 21 individual per-economy LEAP export
  workbooks (`transport_leap_export_combined_XX_*.xlsx`) are byte-for-byte
  equivalent to the combined all-economies workbook when processed through
  `prepare_road_source.py`. Both produce the same 855,243 long rows across the
  same 21 regions. The individual files were deleted to remove redundancy.
- Source inputs: All 21 individual workbooks compared against
  `transport_leap_export_combined_ALL_ECONS_domestic_international_Target_20260526.xlsx`
- Generation method: Automated comparison via `prepare_road_source.load_road_export_rows`
  and `expand_export_to_long`; output DataFrames sorted and compared element-wise.
- Output files changed:
  - Deleted: `back-end/data/road_model/leap_import_workbooks/transport_leap_export_combined_01_AUS_*.xlsx`
    through `transport_leap_export_combined_21_VN_*.xlsx`
  - The combined all-economies workbook remains as the sole upstream source.
- Notes/limitations: The combined workbook and the default input workbook are kept
  locally and gitignored. Run `prepare_road_source.py` to regenerate
  `processed_source/` CSVs if the upstream workbook changes.

## Road source preprocessing and vehicle-type Stock Share rows

- Date: 2026-06-04
- Author: Codex, with user review required
- Change summary: Added the preprocessing entry point for converting a LEAP
  export workbook into per-economy processed source CSVs and aligned
  vehicle-type stock split inputs to LEAP `Stock Share` rows.
- Source inputs:
  - `back-end/data/road_model/leap_import_workbooks/transport_leap_export_combined_ALL_ECONS_domestic_international_Target_20260526.xlsx`
- Generation method:
  - Run `back-end/scripts/prepare_road_source.py` from an interactive Python
    session after setting `RUN_PREPARE_ROAD_SOURCE = True`.
  - The script reads the `FOR_VIEWING` sheet, filters to
    `Demand\Passenger road` and `Demand\Freight road`, melts annual year
    columns into long rows, and writes one CSV per economy.
  - Output files are written to
    `back-end/data/road_model/processed_source/road_module1_source_<ECONOMY>.csv`.
- Recategorizations or mappings:
  - Preserve the exact vehicle-type stock-share rows:
    `Demand\Freight road\Trucks`, `Demand\Freight road\LCVs`,
    `Demand\Passenger road\Motorcycles`, `Demand\Passenger road\Buses`, and
    `Demand\Passenger road\LPVs`, all with `Variable = Stock Share`.
- Output files changed:
  - `back-end/scripts/prepare_road_source.py`
  - `back-end/data/road_model/processed_source/road_module1_source_<ECONOMY>.csv`
    for all 21 APEC economies.
  - generated Module 1 packages now use `road_module1_values_<ECONOMY>.csv`.
- Validation checks run:
  - Confirmed 21 regions and 105 canonical vehicle-type `Stock Share` rows in
    the all-economies source workbook.
  - Confirmed each processed-source file has five canonical stock-share rows;
    Russia uses the latest prior year (`2021`) as the `2022` base fallback for
    those rows because the source workbook has those values at `2021`.
  - Python compile checks for the backend modules.
  - Frontend JavaScript syntax check.
- Notes/limitations:
  - `Stock Share` values are LEAP-style percentages and should sum to 100
    within passenger and freight groups.
  - The old USA-only `C:\Users\Work\github\leap_utilities\data\full model export.xlsx`
    remains useful as a format reference, but it is not the all-economies
    processed-source input.

## Final value overrides

- Date: 2026-06-05
- Author: Codex, with user review required
- Change summary: Added an optional spreadsheet overlay folder for replacing
  final generated Module 1 values after all processed-source and supplemental
  source overlays have been applied.
- Source inputs:
  - `back-end/data/road_model/processed_source/road_module1_source_<ECONOMY>.csv`
  - Active supplemental source files in
    `back-end/data/road_model/supplemental_source_files/`
  - Optional override files in
    `back-end/data/road_model/final_value_overrides/`
- Generation method:
  - Create a CSV/XLSX file named
    `module1_final_value_overrides_<ECONOMY>.csv` or
    `module1_final_value_overrides_<ECONOMY>.xlsx`.
  - Use LEAP-facing final row columns:
    `Branch Path`, `Variable`, `Scenario`, `Year`, `Value`, and `Units`.
  - Add the required override-control column `share_decreased_from`.
  - Optional `Region` values may be blank, the economy code, or the LEAP
    region name for the same economy.
  - Override rows must match existing generated rows by `Branch Path`,
    `Variable`, `Scenario`, and `Year`, after all normal source overlays have
    run.
- Recategorizations or mappings:
  - For `Sales Share` and `Stock Share`, overrides are checked within the
    sibling branch group: same parent `Branch Path`, same `Variable`, same
    `Scenario`, and same `Year`.
  - If the group no longer sums to 100, a non-empty `share_decreased_from`
    identifies the sibling branch that should absorb the difference. It can be
    a full branch path or just the sibling branch name, such as `ICE large`.
  - If `share_decreased_from` is blank, the sibling group is normalized to sum
    to 100.
- Output files changed:
  - `back-end/core/road_module1_defaults.py`
  - `back-end/build_road_model_static_defaults.py`
  - `back-end/data/road_model/road_model_structure_contract.json`
  - `back-end/data/road_model/final_value_overrides/README.md`
  - `back-end/data/road_model/final_value_overrides/.gitkeep`
- Validation checks run:
  - Override file headers are checked during static-default generation when
    override files are present.
  - Active final overrides write
    `road_module1_final_value_override_report.csv` and
    `road_module1_final_value_override_report.html` beside the generated
    economy output file, with before/after values and simple inline-SVG charts.
  - Python compile checks for the backend modules.
- Notes/limitations:
  - Override files replace existing generated rows only; they do not create new
    LEAP branches or new row keys.
  - A share adjustment fails if the requested `share_decreased_from` sibling is
    missing or would be reduced below zero.

## Static bundle switched from JSON to CSV

- Date: 2026-06-05
- Author: Finn Maunsell
- Change summary: Replaced the per-economy JSON static bundle
  (`{version}/{economy}.json`) with plain CSV files (`{version}/{economy}.csv`)
  using the same long-row schema as the 'download filled CSV' and
  'upload filled CSV' actions. This removes a separate serialisation step and
  makes the static bundle, the CSV download, and the CSV upload share one schema.
- Source inputs:
  - `back-end/outputs/road_module1_defaults/` (versioned per-economy packages)
- Generation method:
  - `write_frontend_static_bundle()` in `back-end/road_module1_defaults_workflow.py`
    now calls `long_defaults_df[MODULE1_LONG_COLUMNS].to_csv()` instead of
    building a JSON payload. Column order:
    `Economy, Scenario, Branch Path, Variable, Year, Value, Units, Source, Comment`
  - `front-end/app.js` `loadRoadModule1DefaultsFromStaticBundle()` now fetches
    the `.csv` path and parses it with the existing `parseCsvText()` helper,
    coercing `Year` and `Value` to numbers.
  - `index.json` format is unchanged; it still lists versions and economies.
- Output files changed:
  - `back-end/road_module1_defaults_workflow.py`
  - `front-end/app.js`
  - `front-end/road-module1-static/README.md`
  - All per-economy static bundle files converted from `.json` to `.csv`
- Validation checks run:
  - Confirmed `write_frontend_static_bundle` writes 21 `.csv` files per version
    for both `v2026_05_25_best_guess` and `v2026_06_05_road_module1_sources`.
  - Confirmed CSV column order matches `MODULE1_LONG_COLUMNS`.
- Notes/limitations:
  - The `_json_safe_value` helper and `from typing import Any` import were removed
    from `road_module1_defaults_workflow.py` as no longer needed.
  - Any cached `.json` bundle files from previous runs can be deleted; they are
    no longer fetched by the frontend.

## Required entry template

- Date:
- Author:
- Change summary:
- Source inputs:
- Generation method:
- Recategorizations or mappings:
- Output files changed:
- Validation checks run:
- Notes/limitations:
