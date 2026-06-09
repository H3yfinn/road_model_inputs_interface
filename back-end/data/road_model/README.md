# Road Model Data Folder Guide

This folder is the source-data package for Road Module 1. The code reads files
here, combines them into final Module 1 rows, validates them, and writes outputs
to the build (see [Outputs](#outputs) below).

## Quick Mental Model

There are two phases:

**Source prep** — run once per upstream export update, not part of the regular build:

```text
leap_import_workbooks/  ->  scripts/prepare_road_source.py  ->  processed_source/
```

**Build** — run to regenerate defaults for all economies:

```text
source merge     (all source folders combined, ranked by source priority)
  -> stock share derivation  (Stock Share % computed from base-year Stock rows)
  -> final override          (final_value_overrides/ applied last)
  -> build                   (back-end/outputs/road_module1_defaults/<VERSION>/<ECONOMY>/)
  -> static sync             (front-end/road-module1-static/)
```

### Source merge

All three source folders contribute rows to a single priority-ranked pool:

| Folder | What it provides |
|---|---|
| `processed_source/` | Main LEAP-shaped rows for every standard variable |
| `manually_filled_rows/` | Any row that is absent from processed source, including model-assumption rows |
| `supplemental_source_files/` | Economy-wide or APEC-wide CSVs for variables the LEAP export does not cover (PHEV utilisation, saturation, reconciliation factors, survival/vintage profiles) |

Priority between rows covering the same key is resolved by `road_module1_source_priorities.csv`.
Lower numeric priority wins. Use negative numbers to push a row in front of the default.
If a required row is absent from all source folders, the build fails with an error.

### Stock share derivation

`Stock Share` rows are always computed from the base-year `Stock` rows already in the
merged data — they cannot come from a source file. `final_value_overrides/` can still
override them after derivation.

## Folder Roles

| Path | Role | Edit directly? |
|---|---|---|
| `config/` | Operator-maintained control files for static row validation and visibility. | Yes, when changing static row scope or visibility. |
| `processed_source/` | Main per-economy source rows in LEAP-like long format, generated from `leap_import_workbooks/` by `scripts/prepare_road_source.py`. | Usually no; regenerate from source workbooks. |
| `manually_filled_rows/` | Rows absent from processed source — missing-row fixes and model-assumption parameters (e.g. `Passenger Stock Growth Rate Adjustment`). | Yes. Document the reason and value. |
| `supplemental_source_files/` | APEC-wide CSV/XLSX files for variables the LEAP export does not cover (e.g. PHEV utilisation, reconciliation factors, survival profiles). | Yes, but document provenance in `UPDATE_METHOD.md`. |
| `final_value_overrides/` | Optional final row overrides applied last, after every normal source has run. | Yes, for temporary or researcher-controlled final changes. |
| `leap_import_workbooks/` | Upstream LEAP-style transport export workbooks. Used only by `scripts/prepare_road_source.py` to regenerate `processed_source/`. | Replace when upstream export updates. |
| `archive/` | Historical files not active in current generation. | No, except to add retired files. |

## Control Files

| File | Role |
|---|---|
| `road_model_structure_contract.json` | Lists active datasets, required file patterns, and required columns. |
| `road_module1_default_parameters.json` | Structure/control-plane metadata and generated CSV scale defaults. It is not a numeric source of truth. |
| `road_module1_source_priorities.csv` | Decides which row source wins when the same final row exists in multiple sources. |
| `config/road_module1_static_contract.csv` | **Static row contract.** One row per (Branch Path, Variable). Controls which rows must exist in each scenario and what units the interface displays. See [Static Row Contract](#static-row-contract) below. |
| `config/road_module1_static_fuel_branch_exclusions.csv` | Economy-specific fuel branch exclusions generated from zero road-fuel data in ESTO. This is the only supported reason a globally required fuel branch may be missing for an economy. |
| `UPDATE_METHOD.md` | Audit log for numeric source updates and generated-source methods. |

## Static Row Contract

`config/road_module1_static_contract.csv` is the single source of truth for what rows may exist in the static output and how they behave. It is enforced as a hard error by `build_road_model_static_defaults.py`.

### Columns

| Column | Type | Meaning |
|---|---|---|
| `Branch Path` | string | LEAP branch path (e.g. `Demand\Passenger road\LPVs\BEV large`) |
| `Variable` | string | Variable name (e.g. `Sales Share`) |
| `branch_level` | string | Descriptive only — `transport`, `vehicle_type`, `drive_or_size`, `age`, `fuel`. Not used by code. |
| `Current Accounts` | bool | If `True`, this row must exist in the **Current Accounts** scenario output. |
| `Projected Scenario` | bool | If `True`, this row must exist in **all non-Current Accounts scenario outputs** (Target and any other projected scenarios run). |
| `Shown In Interface` | bool | If `True`, the **Current Accounts** row is exposed to the user in the frontend interface for editing. If `False`, it is passed to the model run but hidden. |
| `Shown In Interface Projected` | bool | Same as `Shown In Interface` but controls visibility for **projected scenario** rows (Target etc.). Defaults to `True` if absent. |
| `Units` | string | The units in which the user must enter values, after applying the scale factor from `road_module1_default_parameters.json`. Displayed in the interface. |
| `Notes` | string | Optional operator note. Not used by code. |

### How Validation Works

`build_road_model_static_defaults.py` runs three checks against every economy's generated output:

1. **No uncontracted rows** — every (Branch Path, Variable) pair in the output must appear in the contract. Rows that are not in the contract cause a hard failure.

2. **Current Accounts completeness** — every row with `Current Accounts = True` must be present in the Current Accounts scenario output, unless it is a fuel-level row for an economy where that fuel is excluded via `road_module1_static_fuel_branch_exclusions.csv`.

3. **Projected scenario completeness** — every row with `Projected Scenario = True` must be present in every non-Current Accounts scenario output (Target etc.), subject to the same fuel-branch exclusion allowance.

### Current Values

Currently all 581 rows have `Current Accounts = True`. The 41 `Sales Share` rows also have `Projected Scenario = True` — Sales Share is the main user policy lever and must be supplied for both the base year and all forward projection years. All other variables are base-year calibration inputs that are fixed across scenarios.

The 41 `Sales Share` rows have `Shown In Interface = True` (the base-year CA row is editable) and `Shown In Interface Projected = False` (projected years 2023–2060 are seeded from the LEAP export but hidden from direct editing — users adjust them via the policy lever sliders, not the row editor).

To require a variable in projected scenarios, set its `Projected Scenario` to `True` in the CSV. To hide a row from the interface, set `Shown In Interface` (CA) or `Shown In Interface Projected` (non-CA scenarios) to `False`.

## Source Priority

Lower numeric priority wins. Use -1, -2 etc to push something in front of 0. Use a
large number like 100000 as a low-priority fallback.

`manually_filled_rows/` supports a `share_decreased_from` column for `Sales Share`
and `Stock Share` rows. Set it to a sibling branch name (short leaf or full path)
and the loader will subtract the introduced share value from that sibling automatically.

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

Rows with `DO_NOT_USE = TRUE` are ignored. Use this to keep example or inactive rows
in a spreadsheet without applying them.

For `Sales Share` and `Stock Share`, `share_decreased_from` can name a sibling
branch that should absorb the change. If blank, remaining sibling shares are scaled
so the group still sums to 100.

When final overrides are applied, the build writes visibility outputs beside the
generated economy CSV:

```text
road_module1_final_value_override_report.csv
road_module1_final_value_override_report.html
```

Open the HTML report to see before/after charts.

## Outputs

**Build** writes per-economy results to:

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

**Static sync** reads the build output and writes filtered, frontend-ready CSVs to:

```text
front-end/road-module1-static/
```

Always regenerate the static sync from the same version folder immediately after
a build so the website reads the same data package.

## Where The Code Lives

The main reader and overlay logic is in:

```text
back-end/core/road_module1_defaults.py
```

The static/default build entry point is:

```text
back-end/build_road_model_static_defaults.py
```

The source prep script (run separately, not part of the build) is:

```text
back-end/scripts/prepare_road_source.py
```

For the broader Module 1 design, see:

```text
docs/new model/multinode_road_module1_repo_guide.md
```



const VARIABLE_EXPLANATIONS = {
  "stock": "Number of vehicles in the fleet. Often economies have these values recorded as 'registered vehicles' or 'vehicles in use'.",

  "mileage": "Average distance travelled per vehicle per year. Not often available from the economy directly.",

  "sales": "Number of new vehicles added to the fleet in that year (i.e. vehicle registrations).",

  "fuel economy": "Energy used per 100 km. Lower values mean better efficiency. Not often available from the economy directly.",

  "sales share": "Share of new vehicle sales assigned to this drive or technology in that year. Related rows should sum to 100%, otherwise you will need to normalise them.",

  "stock share": "Share of the vehicle stock assigned to this drive or technology. Related rows should sum to 100%, otherwise you will need to normalise them.",

  "vehicle equivalent weight": "Conversion weight used to compare different vehicle types in a common vehicle-equivalent ownership measure. For example, buses count as more than one car-equivalent.",

  "passenger vehicle saturation": "Long-run passenger vehicle ownership level used to shape future stock and sales growth.",

  "phev electric driving share": "Share of PHEV driving assumed to be powered by electricity rather than liquid fuel. Be careful to assume the share of activity rather than share of energy, which is different due to the lower fuel economy of PHEV electric driving.",

  "reconciliation weight": "Relative priority given to changing this measure during reconciliation. Higher weights mean the value is changed more aggressively.",

  "reconciliation bound lower": "Lower limit used during reconciliation. The adjusted value should not normally fall below this bound. Good for ensuring mileage and fuel economy values do not get adjusted to unrealistically low levels during reconciliation, which can happen if the stock share (or energy value) is far off what it needs to be.",

  "reconciliation bound upper": "Upper limit used during reconciliation. The adjusted value should not normally rise above this bound. Good for ensuring mileage and fuel economy values do not get adjusted to unrealistically high levels during reconciliation, which can happen if the stock share (or energy value) is far off what it needs to be.",

  "survival rate": "Share of vehicles that remain in the fleet at each age. Used to calculate retirements and turnover.",

  "vintage profile share": "Share of the base-year fleet assigned to each vehicle age. Used to represent the starting age structure of the fleet."
};

const BRANCH_ELEMENT_EXPLANATIONS = {
  "demand": "the LEAP demand-side model area.",

  "passenger road": "the passenger road transport segment.",
  "freight road": "the freight road transport segment.",

  "lpvs": "light passenger vehicles, including cars, SUVs and similar passenger vehicles.",
  "motorcycles": "two- and three-wheelers in the passenger road fleet.",
  "buses": "passenger buses.",
  "trucks": "freight trucks. Broken into Heavy and Medium within the drive categories for this vehicle type.",
  "lcvs": "light commercial vehicles used for freight road transport.",

  "ice": "internal-combustion engine vehicles.",
  "ice small": "small internal-combustion engine vehicles. Generally assumed for regular cars if the economy doesnt have a more specific segment of smaller cars, such as Kei cars in Japan.",
  "ice medium": "medium internal-combustion engine vehicles. Generally assumed for SUVs cars if the economy doesnt have a specific segment of ICE small cars, in which case this segment is used for regular cars. For trucks this is generally assumed for trucks > 3.5t and < 16t if the economy doesnt have more specific segments of medium freight trucks.",
  "ice large": "large internal-combustion engine vehicles. Generally assumed for pickup trucks if the economy doesnt have a specific segment of ICE small cars, in which case this segment is used for SUVs and pickup trucks.",
  "ice heavy": "heavy internal-combustion engine vehicles. Generally assumed for trucks > 16t if the economy doesnt have more specific segments of heavy freight trucks.",

  "hev": "hybrid electric vehicles without plug-in charging.",
  "hev small": "small hybrid electric vehicles.",
  "hev medium": "medium hybrid electric vehicles.",
  "hev large": "large hybrid electric vehicles.",

  "phev": "plug-in hybrid electric vehicles.",
  "phev small": "small plug-in hybrid electric vehicles.",
  "phev medium": "medium plug-in hybrid electric vehicles.",
  "phev large": "large plug-in hybrid electric vehicles.",

  "erev": "extended-range electric vehicles.",
  "erev small": "small extended-range electric vehicles.",
  "erev medium": "medium extended-range electric vehicles.",
  "erev large": "large extended-range electric vehicles.",

  "bev": "battery electric vehicles.",
  "bev small": "small battery electric vehicles.",
  "bev medium": "medium battery electric vehicles.",
  "bev large": "large battery electric vehicles.",
  "bev heavy": "heavy battery electric vehicles.",

  "fcev": "fuel-cell electric vehicles.",
  "fcev small": "small fuel-cell electric vehicles.",
  "fcev medium": "medium fuel-cell electric vehicles.",
  "fcev large": "large fuel-cell electric vehicles.",
  "fcev heavy": "heavy fuel-cell electric vehicles."
};