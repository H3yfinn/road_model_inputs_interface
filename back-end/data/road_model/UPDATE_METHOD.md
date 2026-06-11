# Road Module 1 Data Update Method

This file describes the current method for updating numeric source files and
regenerating the Road Module 1 default package. It is written as operating
guidance, not as a change log.

For a folder-level guide to this data package, see `README.md` in this
directory.

## Current Pipeline

Module 1 defaults are generated in two stages.

Source prep is only needed when the upstream LEAP export workbook changes:

```text
leap_import_workbooks/
  -> back-end/scripts/prepare_road_source.py
  -> processed_source/
```

The regular build is used after any source, supplemental, override, contract, or
visibility change:

```text
processed_source/ + manually_filled_rows/ + supplemental_source_files/
  -> source merge with priority rules
  -> Stock Share derivation from base-year Stock rows
  -> final_value_overrides/
  -> back-end/outputs/road_module1_defaults/<VERSION>/<ECONOMY>/
  -> front-end/road-module1-static/
```

The recommended operator entry point is the notebook-friendly workflow:

```powershell
cd C:\Users\Work\github\road_model_inputs_interface
python back-end\workflow.py
```

The same file is designed to be opened in VS Code/Jupyter interactive mode and
run cell-by-cell or all at once. For routine edits in `manually_filled_rows/`,
`supplemental_source_files/`, `final_value_overrides/`, or `config/`, leave
`RUN_PREPARE_SOURCE_FROM_LEAP_EXPORT = False`. That skips source prep and runs
the regular build/static sync.

Set `RUN_PREPARE_SOURCE_FROM_LEAP_EXPORT = True` only when the upstream workbook
in `leap_import_workbooks/` has changed and `processed_source/` must be
regenerated first.

The lower-level build entry point is still available:

```powershell
cd C:\Users\Work\github\road_model_inputs_interface
python back-end\build_road_model_static_defaults.py
```

Static CSVs are generated outputs and should be recreated from the source
package, not edited as source data.

## Source Files

The active source folders under `back-end/data/road_model/` are:

| Path | Purpose | Update method |
|---|---|---|
| `leap_import_workbooks/` | Upstream LEAP-style transport export workbooks. | Replace when upstream exports change, then run source prep. |
| `processed_source/` | Per-economy LEAP-shaped rows generated from the upstream export workbook. | Regenerate with `prepare_road_source.py`; do not hand-edit for normal updates. |
| `manually_filled_rows/` | Rows absent from the processed source, including model assumption rows. | Edit directly and document the value/provenance. |
| `supplemental_source_files/` | APEC-wide or economy-wide inputs not covered by the LEAP export. | Edit directly and document the source/provenance. |
| `final_value_overrides/` | Optional final replacements applied after normal source generation. | Edit directly for reviewed overrides; overrides must match existing generated rows. |
| `config/` | Static row contract, visibility, and fuel-branch exclusions. | Edit directly when the frontend/model hand-off contract changes. |
| `archive/` | Historical files not used by current generation. | Do not use as an active source. |

`road_module1_default_parameters.json` is control-plane metadata. It provides
economy names, canonical variable names, aliases, and default scale labels. It
is not a numeric source of truth.

`road_module1_source_priorities.csv` resolves conflicts when more than one
source provides the same final row. Lower numeric priority wins. Use negative
priorities for deliberate high-priority rows and large positive priorities for
fallback rows.

## Source Prep

Run source prep only when the upstream LEAP export workbook in
`leap_import_workbooks/` changes.

The prep script reads the LEAP `FOR_VIEWING` sheet, filters road transport rows,
reshapes annual values into long rows, and writes:

```text
processed_source/road_module1_source_<ECONOMY>.csv
```

The current upstream source is the combined all-economies workbook in
`leap_import_workbooks/`. The individual per-economy export workbooks are not
part of the active source package.

After source prep, run the regular build so generated outputs and frontend
static CSVs use the refreshed processed sources. `back-end/workflow.py` does
both steps in order when `RUN_PREPARE_SOURCE_FROM_LEAP_EXPORT = True`.

## Source Merge

`back-end/core/road_module1_defaults.py` owns source merge behavior.

The merge treats `processed_source/`, `manually_filled_rows/`, and
`supplemental_source_files/` as one priority-ranked source pool. Supplemental
files are not a late overlay; they are normal source inputs with priority rules.

Required rows must come from the source pool or from an explicitly supported
derivation. Missing required rows should fail the build. Do not add silent
row-completion fallbacks.

## Stock Share Derivation

`Stock Share` rows are derived from base-year `Stock` rows after the source
merge. They should not be maintained as ordinary source rows.

Final overrides can still replace derived `Stock Share` values after derivation.

## Supplemental Sources

Active supplemental source files include:

| File | Supplies |
|---|---|
| `apec_phev_utilisation_rates.csv` | PHEV electric driving share by economy |
| `apec_reconciliation_factors.csv` | Module 6 reconciliation weights and scalar bounds |
| `apec_vehicle_equivalent_weights.csv` | Vehicle equivalent weights for Module 3 |
| `apec_passenger_vehicle_saturation.csv` | Passenger vehicle saturation for Module 3 |
| `apec_lifecycle_profile_factors.csv` | Survival curve calibration parameters |
| `vehicle_survival_modified_00_APEC.xlsx` | Age-based survival probabilities |
| `vintage_modelled_from_survival_00_APEC.xlsx` | Base-year vintage age distribution |

When any supplemental source changes, record the source, method, affected file,
and validation checks in a new entry at the end of this file.

## Final Value Overrides

Use `final_value_overrides/` when a reviewed value must replace the generated
value after all normal source processing has run.

Override files are named:

```text
module1_final_value_overrides_<ECONOMY>.csv
module1_final_value_overrides_<ECONOMY>.xlsx
```

Required row-matching columns are:

```text
Branch Path, Variable, Scenario, Year, Value, Units, share_decreased_from
```

Optional region values may be blank, the compact economy code, the canonical
economy code, or the LEAP region name for the same economy.

Overrides can only replace existing generated rows. They do not create new row
keys, new branches, or new variables.

For `Sales Share` and `Stock Share`, `share_decreased_from` can identify the
sibling branch that absorbs the balancing change. It may be a full branch path
or a sibling branch leaf name. If it is blank, sibling shares are normalized so
the group sums to 100.

When overrides are applied, the build writes review outputs beside the generated
economy CSV:

```text
road_module1_final_value_override_report.csv
road_module1_final_value_override_report.html
```

Open the HTML report before treating an override run as reviewed.

## Static Row Contract

`config/road_module1_static_contract.csv` is the active static row contract. It
is the only allow-list for `(Branch Path, Variable)` pairs in the frontend static
bundle.

The contract controls:

- Whether a row is required for `Current Accounts`.
- Whether a row is required for projected scenarios such as `Target`.
- Whether each scenario's row is shown in the browser editor.
- The units displayed by the interface.

The static bundle writer filters generated rows to the contract and then runs
hard completeness checks. Every row present in the generated static CSV is part
of the browser/model hand-off contract, even if `Shown In Interface` is `False`.
Hidden rows must still be preserved through load, edit, download/upload, and
model run export.

`config/road_module1_static_fuel_branch_exclusions.csv` is the only supported
economy-specific exception list for missing fuel branches. The accepted reason
is exactly:

```text
0 data for fuel in esto dataset
```

Fuel-level branches are globally required. A missing fuel branch is valid only
when the economy/fuel combination has zero road data in
`leap_road_model/input_data/esto_transport_2000_2022.csv` and is listed in the
exclusion config.

## Scale Labels

Generated long Module 1 CSVs use LEAP-style display scales. The default scale
labels are configured in `road_module1_default_parameters.json` under
`scale_defaults_by_variable`.

Typical defaults are:

| Variable | Scale |
|---|---|
| `Stock` | `Millions` |
| `Sales` | `Millions` |
| `Mileage` | `Thousands` |
| `Average Mileage` | `Thousands` |
| `Final On-Road Mileage` | `Thousands` |
| Share and percentage rows | `%` |

Internal generation uses raw model units. Long CSV output divides by the display
scale, and long CSV loading multiplies supported numeric scales back to raw
units before model calculations.

## Static Bundle And Model Hand-Off

The frontend static CSV is the authoritative Module 1 package for local
interface-driven model runs.

```text
front-end/road-module1-static/<VERSION>/<ECONOMY_COMPACT>.csv
```

When the user runs the model from the interface, the backend writes the browser's
completed long CSV payload to:

```text
leap_road_model/input_data/module1_defaults/<VERSION>/<ECONOMY>/road_module1_values_<ECONOMY>.csv
```

That model-side file is a runtime copy, not a separate source of defaults. If it
is missing rows that exist in the static CSV, treat it as stale or as evidence of
a browser/API hand-off issue. Do not add model-side fallbacks to compensate for a
stale runtime copy.

## Generated Outputs

The build writes versioned per-economy packages to:

```text
back-end/outputs/road_module1_defaults/<VERSION>/<ECONOMY>/
```

The main generated file is:

```text
road_module1_values_<ECONOMY>.csv
```

The static sync writes browser-ready long CSVs and `index.json` to:

```text
front-end/road-module1-static/
```

Production versions should use immutable dated names, for example:

```text
v2026_06_05_road_module1_sources
```

For exploratory work, use a temporary version name and do not point the frontend
at it unless that is the intended test.

## Validation Checklist

After changing source data or the static contract:

1. Run `python back-end\workflow.py`.
2. Confirm the generated package exists under
   `back-end/outputs/road_module1_defaults/<VERSION>/`.
3. Confirm `front-end/road-module1-static/index.json` points to the intended
   version and economies.
4. Inspect at least one affected economy CSV in
   `front-end/road-module1-static/<VERSION>/`.
5. For hand-off changes, confirm `leap_road_model` can load the long CSV for an
   affected economy.
6. For model-impacting changes, run a direct road model smoke test for at least
   one affected economy.

Example direct model smoke test:

```powershell
cd C:\Users\Work\github\leap_road_model
python codebase\road_workflow.py 20_USA --scenario Target --no-vis
```

## Update Entry Template

Use this template when a numeric source file, source-prep method, supplemental
source, final override, or static hand-off contract changes.

```text
## <Short update name>

- Date:
- Author:
- Change summary:
- Source inputs:
- Update method:
- Recategorizations or mappings:
- Output files changed:
- Validation checks run:
- Notes/limitations:
```
