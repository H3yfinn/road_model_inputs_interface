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

The current upstream source prep combines the latest combined all-economies
Target and Reference workbooks in `leap_import_workbooks/`. The individual
per-economy export workbooks are not used for `processed_source/`, but the
static bundle can use them to load scenario-specific projected sales-share rows
when a matching economy/scenario workbook exists.

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

### Structured provenance and year policy

Source-prep and source-merge inputs may carry these optional columns in addition
to the numeric row fields:

```text
Source, Comment, Source Data Year, Source Classification,
Base Year Treatment, Derivation Method
```

They are preserved through the internal wide form and the canonical-long build
output. Malformed years, classifications, or treatments fail validation instead
of being repaired silently.

The build then applies the pure normaliser in
`back-end/core/road_module1_provenance.py`:

- an explicit `Source Data Year` always wins;
- a missing year becomes 2022 only for a source/package combination in the
  explicit, version-scoped 9th Outlook lineage mapping;
- blank dates and legacy-looking filenames are not evidence by themselves;
- uncertain lineage stays blank/`legacy_unknown` and receives “original source
  detail not yet recorded” guidance;
- proven, version-scoped 9th Outlook lineage points users to the archived
  transport data system for investigation on demand, while retaining
  `legacy_unknown` internally and staying non-native unless explicit source
  metadata establishes another classification;
- a literal Russia 2022 source remains 2022 for the 2021 base year and is marked
  `carried_backward` / `future_year_seed`;
- derived and generated rows record the derivation, including `Stock Share`
  from `Stock` and generated correction-factor defaults.

The current 9th Outlook mapping applies only to the checked-in
`v2026_06_05_road_module1_sources` package: its documented processed-source
files and the dated Target 20260526 / Reference 20260615 transport export
packages. Do not broaden it to every `processed_source/` file or LEAP export.
Before adding a new mapping, trace the exact workbook/source generation path,
confirm that the folder is active, and record the supporting document.

Supplemental overlays safely copy an explicit four-digit `data_year` into
`Source Data Year`. Evidence grades and estimation-status text remain in source
notes unless the source itself provides a valid canonical classification; they
do not imply a native observation.

Use `audit_module1_source_quality()` for an in-memory quality summary. Pass a
temporary caller-owned path only when a CSV is needed for review. The audit does
not update generated defaults, the frontend static bundle, Drive, or any source
file.

### Recovering archived 9th Outlook provenance

The original 9th-edition transport data system is preserved for provenance
recovery at:

- [APERC code archive folder](https://drive.google.com/drive/folders/1K--aSZYmolHb0Kl3m9ANjw11jWFdpj9u)
- [transport_data_system.zip](https://drive.google.com/file/d/103sIJ1L1mbQpGfL2shlB8nrIOTkbyFz3/view?usp=drive_link)

The same folder contains `transport_model_9th_edition.7z`. Its relevant combined
source snapshot is:

```text
transport_model_9th_edition/input_data/transport_data_system/combined_data_DATE20250122.csv
```

Treat these archives as read-only recovery evidence, not as runtime inputs or
automatically approved defaults. The combined snapshot preserves row-level
`dataset` and `comment` labels, but later 9th-model code explicitly removed those
fields and could transform the values through unit conversion, non-road splits,
aggregation, estimation and ESTO reconciliation.

Do not plan or run a bulk row-by-row provenance recovery. Leave current legacy
records unchanged and replace them gradually through normal reviewed source
updates. If a specific value needs investigation, extract only the required
archive files into a temporary or reviewed local workspace and look it up using
the full archived key `(economy, date, medium, measure, vehicle_type,
transport_type, drive, fuel)`. Preserve the current numeric value and canonical
key unless that investigation leads to a separately reviewed source update.

Do not commit the multi-gigabyte archive or wholesale combined-data snapshot to
this repository. `combined_data_DATE20230902.csv` is an older comparison copy
and must not override the 2025 snapshot merely because it is locally available.

## Stock Share Derivation

`Stock Share` rows are derived from base-year `Stock` rows after the source
merge. They should not be maintained as ordinary source rows.

Final overrides can still replace derived `Stock Share` values after derivation.

## Supplemental Sources

Active supplemental source files include:

| File | Supplies |
|---|---|
| `apec_phev_utilisation_rates.csv` | PHEV electric driving share by economy and vehicle type; LPVs feed passenger road and LCVs feed freight road |
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

## Researcher submission review workflow

- Date: 2026-08-24
- Author: Codex
- Change summary: Added immutable researcher-submission archiving and a separate review workflow.
- Source inputs: An archived complete canonical Module 1 CSV and its metadata record, plus the exact static/default package version named in that record.
- Update method: Use `back-end/scripts/review_researcher_submission.py` from a notebook/VS Code interactive session. It normalizes canonical long or legacy wide CSVs, writes a per-row changed/added/removed review report, an internal-unit final-override candidate, and a source-promotion plan. Reviewers choose and apply a source owner manually; this tool deliberately does not edit source folders or generated versions.
- Recategorizations or mappings: Compact economy codes are normalized to canonical underscore codes. Legacy wide Stock/Mileage values use their scale labels to convert internal values to website/display values before comparison.
- Output files changed: `outputs/researcher_submission_reviews/` only, unless a reviewer separately approves and places an override/source update.
- Validation checks run: Automated canonical, legacy-wide, scale, duplicate, diff, override-unit, and mocked archive tests.
- Notes/limitations: The deployed archive uses OAuth My Drive credentials:
  `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
  `GOOGLE_DRIVE_ARCHIVE_REFRESH_TOKEN`, and
  `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID` (plus the redirect-URI Secret).
  Drive is intentionally not a source of truth. The live OAuth archive was
  verified on 2026-08-27 with a controlled `20_USA` submission; archive failure
  remains non-blocking for model runs. The legacy service-account variables are
  retained only as a local/Shared Drive fallback.

Deployment details and the My Drive OAuth boundary are recorded in
`docs/researcher_submission_drive_archive.md`.

## Base-year candidate resolver contract

- Date: 2026-08-28
- Author: Codex
- Change summary: Added a pure candidate resolver for a future dynamic
  base-year build phase. It has no filesystem, browser, Drive, or generated
  package dependency.
- Source inputs: Explicit original candidate records only. A record includes a
  stable candidate ID, canonical row key, source identity, source-data year,
  source classification, and configured quality/source-priority identifiers.
- Update method: Select the variable policy through
  `back-end/core/base_year_variable_policy.py`. The registry matches exact
  canonical `Variable` names and validates its coverage against
  `config/road_module1_static_contract.csv`. Do not feed a previously
  shifted/generated candidate back into the resolver.
- Variable policy mapping:
  - `exact_year_required`: no current canonical Module 1 variables. This family
    remains available for external anchors such as ESTO energy-balance data,
    which must match the requested year and use the resolver's
    `energy_balance_exact_year` policy.
  - `seed_eligible`: `Stock`, `Mileage`, `Fuel Economy`, `Sales Share`,
    `Survival Rate`, `Vintage Profile Share`, `PHEV Electric Driving Share`,
    the passenger/freight projection assumptions, turnover bounds, and vehicle
    equivalent weights/bounds, plus the seven reconciliation weights/bounds.
    These 23 researcher/source or model-judgement inputs may use exact year,
    latest eligible earlier year, or only when neither exists the earliest
    eligible future year.
  - `derived`: `Stock Share` only. It is recalculated from resolved `Stock` and
    must not be resolved or shifted independently.
- Recategorizations or mappings: Native observations are selected exact-year,
  then latest eligible earlier, then earliest eligible future. Earlier values
  are `carried_forward`; future values are `carried_backward`; an exact-year
  non-native value retains its classification and is `transformed`. Missing
  classification remains `legacy_unknown`, which is not eligible under the
  supplied policies.
- Output files changed at this historical checkpoint: None. The resolver
  returned an in-memory selected candidate and structured rejections. The later
  opt-in generation boundary below can write review artifacts to a caller-owned
  directory; it remains disconnected from normal/static builds.
- Audit reasons: A call accepts one canonical row key only. Rejections are
  stable by candidate ID and explain the first selection dimension that lost:
  exact year, newer earlier year, earlier-over-future, earlier future year,
  configured quality tier, configured source priority, or candidate-ID tie
  break.
- Validation checks run: Synthetic resolver tests cover deterministic ranking,
  policy ineligibility, provenance, reversibility, and invalid inputs. Registry
  tests cover exact/seed/derived lookups, strict canonical spelling, malformed
  definitions, duplicates/conflicts, deterministic inventory, and full current
  contract coverage.
- Notes/limitations: This checkpoint originally classified variables only. The
  later opt-in integration does not regenerate checked-in packages, add source
  quality tiers or age thresholds, change resolver ranking, or broaden eligible
  source classifications. Some assumption sources are currently classified as
  `structural_assumption` or `model_assumption`; whether those classifications
  become resolver-eligible remains a separate explicit integration decision.
  ESTO energy-balance observations sit outside the canonical Module 1 variable
  registry and remain exact-year reconciliation anchors.

## Opt-in resolved base-year package generation

- Date: 2026-08-28
- Author: Codex
- Change summary: Added
  `back-end/core/base_year_package_generation.py`, a backend-only opt-in writer
  around the existing pure resolver. It is not wired into
  `write_economy_package()`, API startup, the researcher UI, or static-package
  discovery. Current checked-in defaults remain the authoritative fallback.
- Source inputs: A caller supplies a complete canonical-long fallback for one
  economy/requested year plus explicit original candidates. Each candidate
  carries a package-wide unique ID, source identity, source-data year,
  classification, configured resolver priority identifiers and a complete
  canonical payload at the original source year. The generator does not scan
  source folders or generated packages.
- Update method: Call `generate_resolved_base_year_package()` with an explicit
  caller-owned output directory, source-package identity and future package
  version. The existing variable registry chooses the resolver policy. The only
  implemented ranking strategy remains `prefer_earlier`: exact native, latest
  earlier native, then earliest future native. Sparse per-variable policy
  overrides may make a seed-eligible variable exact-year-only; they cannot
  broaden an exact-year policy or eligibility.
- Fallback and derivation: If a canonical key has no eligible candidate, its
  fallback row is copied unchanged. `legacy_unknown` is still ineligible.
  `Stock Share` is never resolved independently; candidates for it fail and its
  rows are derived from the resolved `Stock` totals for sibling vehicle-type
  branches.
- Validation boundary: Candidate payload keys must match the fallback key,
  payload year must equal source-data year, classifications must agree, values
  must be finite, and generated/shifted candidate origins are rejected. Output
  canonical keys must exactly match the fallback key set. The writer refuses
  the checked-in data tree, backend production-default output root and frontend
  static root.
- Outputs: The caller directory receives `<economy>_<year>.csv`, a deterministic
  resolution-audit CSV, and a JSON manifest. The audit records selected
  candidate/source identity, strategy and override use, source year,
  classification, treatment, selection reason and deterministic rejections.
  The manifest records source package/version, output and audit filenames and
  SHA-256 checksums, summary/rejection counts, and an isolated generation time.
- Validation checks: Synthetic tests cover opt-in/fallback behavior,
  exact/earlier/future selection, strict sparse overrides, derived stock share,
  deterministic output and idempotence, manifest checksums and counts,
  malformed metadata, package-wide candidate identity, generated-candidate
  rejection and protected output paths. Development validation uses temporary
  directories only.
- Remaining limitations: `closest_available` is documented but not implemented
  because adding it would change resolver ranking policy. Production candidate
  extraction, immutable-version promotion/index updates, UI integration and
  additional eligible classifications remain out of scope and require separate
  review.

## Archived 9th Outlook provenance discovery

- Date: 2026-08-28
- Author: Codex
- Change summary: Recorded the recovery location and interpretation of the full
  9th-edition transport data system after locating the 2025 combined provenance
  snapshot and the model code that discarded its metadata downstream.
- Source inputs: Read-only inspection of `transport_data_system.zip`,
  `transport_model_9th_edition.7z`, `combined_data_DATE20250122.csv`, and the
  older `combined_data_DATE20230902.csv` comparison copy.
- Update method: Documentation only. No archived data was added to the active
  source pool, and no defaults, static files, Drive files or numeric values were
  changed.
- Recategorizations or mappings: Clarified that `legacy_unknown` means archived
  provenance has not yet been linked for proven 9th Outlook lineage; it must not
  be presented as evidence that the historical source never existed.
- Output files changed: Documentation only.
- Validation checks run: Full interface test suite and documentation diff
  review.
- Notes/limitations: No bulk crosswalk or retrospective sourcing project is
  planned. Legacy rows remain available for targeted archive investigation and
  should be replaced gradually through normal reviewed source updates.
