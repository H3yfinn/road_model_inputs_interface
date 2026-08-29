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

## ESTO Vintage Packages

The researcher interface exposes a data-vintage choice, not a free-form base
year. The strict mapping is maintained in
`config/esto_vintage_registry.csv`:

| ESTO vintage | Model base year | Status |
|---|---:|---|
| 2024 | 2022 | Final — configured default |
| 2025 | 2023 | Final |
| 2026 | 2024 | Preliminary |

Each vintage maps to one distinct generated package version. The static index
only advertises a vintage after that package exists, so an incomplete staging
run cannot create a broken choice in the interface. Do not edit `index.json`
or static CSVs to add a vintage manually.

Exactly one registry row must have `is_default=True`. The configured default is
ESTO 2024 / base year 2022. If any vintage packages are present during static
index generation but that default package is absent, the build fails rather
than silently choosing a different vintage.

Changing vintage in the browser loads the matching package and base year. Any
current edits are saved as a separate browser draft and are not copied between
vintages; the user is warned before switching and can return to restore the
draft. A run request must provide the exact registered vintage, base year, and
package version combination or the backend rejects it before writing model
inputs.

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
- named lifecycle curves and lifecycle/control defaults are explicitly
  structural or model assumptions. Their calendar source year remains blank
  because it is not applicable; their derivation method and replacement
  guidance are recorded instead;
- `manually_entered_missing_rows.csv` values retain their explicit 2022 row
  year as `Source Data Year=2022`, remain `legacy_unknown`, and continue to ask
  for a better original dataset citation;
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

For base-year candidate resolution, a `legacy_unknown` classification remains
ineligible by itself. The extraction layer may add the separate
`verified_9th_outlook` candidate marker only when the source name and immutable
source-package version match an explicit rule in `road_module1_provenance.py`.
Package generation validates that mapping again before resolution. This allows
known 9th Outlook bridge values to seed a later or earlier base year without
making all unknown legacy data eligible or relabelling it as native.
Generated `Mileage Correction Factor` and `Fuel Economy Correction Factor`
rows are classified as derived controls outside the maintained source contract;
they remain authoritative fallback rows and never become independent resolver
candidates.

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

Do not plan or run a bulk row-by-row provenance recovery. Known records carrying
the archive guidance are complete enough for normal operation and should not be
put into a reviewer action queue. Leave them unchanged and replace them
gradually through normal reviewed source updates. If a specific value becomes
material, extract only the required archive files into a temporary or reviewed
local workspace and look it up using the full archived key `(economy, date,
medium, measure, vehicle_type, transport_type, drive, fuel)`. Preserve the
current numeric value and canonical key unless that investigation leads to a
separately reviewed source update.

Do not commit the multi-gigabyte archive or wholesale combined-data snapshot to
this repository. `combined_data_DATE20230902.csv` is an older comparison copy
and must not override the 2025 snapshot merely because it is locally available.

## Stock Share Derivation

The five vehicle-type `Stock Share` rows are derived from base-year `Stock`
rows after the source merge. More detailed technology/size Stock Share rows do
not have matching canonical Stock detail and remain authoritative source or
fallback rows; they must not be silently zeroed or relabelled as derived.

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

For routine tracking, call
`build_supplemental_provenance_inventory()` from
`back-end/core/supplemental_provenance_inventory.py`. It inventories only the
seven active supplemental paths named in `road_module1_default_parameters.json`
and uses the canonical provenance fields plus evidence grade, estimation status
and a separate tracking status. It does not feed the candidate resolver or
modify the existing supplemental loaders.

`tracked_complete` and `tracked_metadata_limited` require no reviewer action.
The latter is expected for the lifecycle-factor rows and the survival/vintage
workbooks. They are ChatGPT-assisted APERC model/derived assumptions whose
original external evidence and source year are unknown, rather than external
observations. Only
`attention_required` should be surfaced: missing or unconfigured active files,
malformed schema/year/profile data, missing record identities, and
duplicate/conflicting source identities.
The report is in memory unless a caller supplies a safe output path; protected
data/default/static paths are refused.

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
  - `derived`: `Stock Share` only. It must not be resolved or shifted
    independently. The generator recalculates rows carrying the explicit
    `stock_share_from_stock` marker and preserves other detailed shares from
    the authoritative fallback.
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
  `Stock Share` is never resolved independently; candidates for it fail. Rows
  explicitly marked `stock_share_from_stock` are derived from resolved `Stock`
  totals for sibling vehicle-type branches. Other detailed Stock Share rows
  are copied from the authoritative fallback because canonical Stock inputs do
  not exist at that hierarchy.
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

## Checked-in source candidate extraction

- Date: 2026-08-28
- Author: Codex
- Change summary: Added
  `back-end/core/base_year_candidate_extraction.py`, a read-only adapter from
  the current priority-ranked source pool into the opt-in review-package
  generator. It is not connected to normal defaults/static builds, API startup,
  package discovery, the researcher UI or production promotion.
- Source inputs: An explicit checked-in static CSV for one economy, containing
  one complete Current Accounts template year and the separate Reference/Target
  projection series, plus the rows returned before
  `load_processed_source_inputs()` generates fallback rows. The adapter does
  not inspect Drive, archives, researcher submissions, generated packages,
  supplemental-source folders or inactive specialist folders.
- Update method: Call `generate_checked_in_source_review_package()` with an
  explicit economy, requested base year, source-package version, review package
  version and caller-owned output directory. Source rows are mapped only to
  canonical Current Accounts template keys. The source-row year must equal
  structured `Source Data Year`; shifted/projected rows, missing-year rows and
  derived variables are audit-only exclusions. Existing source priority resolves
  duplicate key/year evidence after eligible native rows are considered;
  same-priority value conflicts fail.
- Provenance policy: Explicit metadata still wins. The version-scoped 9th
  Outlook bridge mapping may supply 2022, archive guidance and the separate
  `verified_9th_outlook` candidate marker. This makes only proven bridge rows
  seed-eligible without upgrading them to `native_observation`. Extraction
  never treats a derived/generated row as external evidence.
- Fallback normalisation: The current 20USA/2022 static CSV has five identical
  duplicate Stock Share pairs consisting of a legacy copy and one explicit
  `stock_share_from_stock` copy. The adapter retains only the explicit derived
  row. Any differing value/control metadata, non-Stock-Share duplicate or
  ambiguous derivation fails validation.
- Package assembly and validation: The complete Current Accounts template is
  rebased to the requested year and resolved independently of projections.
  Only Reference/Target rows after that year are retained. Both projection
  scenarios must have identical continuous coverage beginning at base year + 1;
  malformed values and conflicting duplicate keys fail. No shifted output is
  ever added to the candidate pool.
- Outputs: In addition to the resolved Current Accounts CSV, resolution audit
  and manifest, the caller-owned directory receives a separate projection CSV,
  their sorted complete-package CSV, original-candidate JSON and a candidate-
  extraction audit CSV. The manifest records component filenames, row counts,
  SHA-256 checksums, Current Accounts template source year and first projection
  year. Protected production/source/static paths remain refused.
- Validation checks: Synthetic tests cover explicit native and known 9th
  Outlook rows, missing/shifted/derived exclusions, deterministic source
  priority, conflicts, malformed fallback duplicates, no input mutation,
  manifest checksums and temporary end-to-end generation. A read-only
  20USA/2022 run inspected 81,127 ranked rows: 330 matched canonical keys, 290
  became non-native candidates with the version-scoped
  `verified_9th_outlook` lineage marker, 34 Stock Share source rows and 6
  missing-year rows were excluded. Resolution selected all 290 candidates,
  retained 212 authoritative-template rows (including 29 detailed Stock Share
  rows) and derived the 5 explicitly marked vehicle-type Stock Share rows,
  producing 507 unique keys.
- Notes/limitations: This is review-package generation, not promotion. Current
  checked-in sources provide no eligible native candidate in the 20USA run, and
  eligibility was intentionally not broadened. Russia is complete enough for
  normal operation: keep an explicit 2022 source year and carry it backward if
  used for the 2021 model base year; no separate dating investigation is
  required. Supplemental inputs are tracked by the separate inventory described
  above and remain outside candidate resolution. Immutable promotion/index
  changes and UI integration remain out of scope.

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
  planned. Rows carrying the archive guidance are operationally complete and
  require no routine review. The archive remains available only if a specific
  material value later needs investigation.

## Low-touch supplemental provenance inventory

- Date: 2026-08-28
- Author: Codex
- Change summary: Added a separate deterministic inventory for active
  supplemental sources and revised quality-audit semantics so known archived
  9th Outlook rows are complete enough for operations without being relabelled
  as native observations.
- Source inputs: The seven active supplemental paths declared in
  `road_module1_default_parameters.json`. Five are CSV sources; two are the
  checked-in survival/vintage lifecycle workbooks.
- Update method: Call `build_supplemental_provenance_inventory()` for an
  in-memory report or provide a safe caller-owned CSV path. Existing source
  files and loaders remain authoritative and unchanged. The inventory never
  creates resolver candidates.
- Recategorizations or mappings: Supplemental records use the canonical Source,
  Comment, Source Data Year, Source Classification, Base Year Treatment and
  Derivation Method fields. Synthetic/default inputs remain model or structural
  assumptions. Evidence grade and estimation status are tracked separately and
  do not confer native status. Known incomplete workbook/profile metadata is
  `tracked_metadata_limited`, not an action item. The lifecycle factors and
  survival/vintage profiles explicitly record that they are ChatGPT-assisted
  assumptions with unknown original external evidence and source year.
- Audit behavior: Only missing/unconfigured active files, malformed schemas or
  years/profiles, missing record identities, and duplicate/conflicting source
  identities are `attention_required`. `audit_module1_source_quality()` now
  separately reports `archived_reference_available` and
  `operationally_complete`; archived-linked
  rows no longer inflate `legacy_detail_needed`.
- Validation checks: The checked-in inventory produced 73 records across 7
  active sources: 69 `tracked_complete`, 4 `tracked_metadata_limited`, and 0
  requiring review. Automated tests cover deterministic output, no source-file
  mutation, malformed years/workbooks, missing/unconfigured files, duplicate
  identities and protected output paths.
- Notes/limitations: Russia requires no separate dating investigation. Preserve
  any explicit 2022 source year and use `carried_backward` if the value supports
  a 2021 base-year package. This change does not modify numeric inputs,
  production/static outputs, Drive, UI behavior, classification eligibility or
  promotion.

## Staged Module 1 review-package operator command

- Date: 2026-08-28
- Author: Codex
- Change summary: Added
  `back-end/scripts/generate_module1_review_package.py` as a small command-line
  entry point for the existing checked-in candidate extraction, opt-in resolver
  package generation and separate supplemental provenance inventory.
- Update method: Run the script with explicit `--economy`, `--base-year`,
  `--package-version` and `--output-dir` arguments. The source-package version
  defaults to the current checked-in version; an explicit fallback CSV remains
  optional.
- Outputs: The new or empty caller-owned staging directory receives the
  resolved Current Accounts review CSV, separate Reference/Target projection
  CSV, validated complete-package CSV, resolution audit and manifest, extracted
  candidate JSON and audit, and supplemental provenance inventory CSV. A
  structured JSON summary is printed for the operator.
- Safety: The command refuses a non-empty directory and inherits the protected
  production/source/static path checks. It has no promotion, static-index,
  Drive, UI or deployment operation.
- Validation checks: Automated tests cover staged summary/artifact reporting,
  refusal to overwrite an existing directory, clean command-line output and a
  nonzero safe-failure exit. Production-source validation is run only into a
  temporary directory.

## Explicit all-economies and researcher-submission review orchestration

- Date: 2026-08-28
- Author: Codex
- Change summary: Extended
  `back-end/scripts/generate_module1_review_package.py` with `--all-economies`
  and an explicit `--include-researcher-submissions` option so an operator can
  stage all checked-in economy packages, the supplemental provenance inventory
  and the archived-submission review in one run.
- Update method: Pass one shared `--base-year`, a review-only package version
  and a new or empty caller-owned output directory. The researcher-submission
  step is disabled by default. When deliberately enabled, it uses
  `ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID` or an explicit
  `--researcher-submissions-folder-id`
  and the existing archive credentials.
- Outputs: Economy packages are written below `packages/<ECONOMY>/`, the
  supplemental inventory remains separate, researcher-submission downloads and
  review artifacts go below `researcher_submission_review/`, and
  `review_run_summary.json` records the combined counts and artifact paths.
- Year meaning: `--base-year 2022` requests 2022 model/output packages; it does
  not label every Drive submission or source observation as 2022. Archived
  submissions preserve their recorded version, exact baseline checksum and
  source-year provenance.
- Safety: The researcher-submission branch is download/validation only. It
  never edits Drive, applies a candidate override, merges a submission into an
  economy package, promotes outputs, updates the static index, changes
  source/default values, or touches deployment. A fresh staging directory
  intentionally reviews every currently visible archive pair.
- Failure handling: Every checked-in economy is attempted. Strict validation
  failures are recorded in the run summary, later economies continue, and the
  command returns nonzero whenever any economy failed so a partial batch is
  never presented as complete.
- Conflict review artifacts: A duplicate-source failure produces two
  formula-safe CSVs below `quarantine/<ECONOMY>/`. The compact review CSV has one
  row per canonical conflict and ten purpose-specific columns, including
  candidate options, reviewer choice, reviewer source and reviewer reason. The
  evidence CSV preserves every underlying conflicting row. Artifact paths and
  SHA-256 checksums plus group/row counts are recorded on that economy's failure
  entry. These files collect a decision only; they never update
  source/default/static data or promote a package.
- Validation checks: Mocked archive tests cover the explicit opt-in boundary and
  all-economy aggregation. End-to-end package generation is validated only in a
  temporary directory; no live Drive download is required for automated tests.

## Static scenario/workbook conflict prevention

- Date: 2026-08-28
- Author: Codex
- Change summary: Corrected build-time causes behind the five short-code
  Reference Sales Share quarantines and prevented mixed source scenarios from
  being silently relabelled as Current Accounts. Added compact conflict-review
  and full evidence artifacts for any future duplicate-source quarantine.
- Workbook selection: Compact and canonical economy codes now both map to the
  expected LEAP token (`02BD` and `02_BD` -> `02_BD`). Matched workbook rows are
  filtered to the requested economy's accepted LEAP region names even when an
  ALL_ECONS workbook is the fallback. If it contains no matching region, the
  existing processed-source fallback is used.
- Current Accounts construction: Genuine Current Accounts rows are preferred
  for each `(Branch Path, Variable)` key. A non-Current-Accounts row is used only
  where that key has no Current Accounts row. Identical repeats collapse;
  disagreeing fallback scenarios fail before static output is written.
- Legacy compatibility: A blank Source Data Year no longer causes 12-column
  legacy canonical rows to disappear during long-to-wide pivoting.
- Quarantine outputs: Failed all-economy staging writes a ten-column,
  one-row-per-group review CSV and a separate formula-safe evidence CSV. The run
  summary records both paths and group/row counts. Neither applies a decision.
- Validation: All five affected economy-specific Reference workbooks loaded
  1,558 rows for 2023–2060 with zero duplicate canonical keys. A complete
  21-economy static build in a temporary root passed contract checks and wrote
  20,031 rows per economy with zero duplicate canonical keys.
- Safety: No checked-in backend output or frontend static
  file was regenerated. The temporary build differs materially from the current
  22,212-row bundle. It adds no keys and removes 2,156 unique keys per economy:
  28 out-of-contract Current Accounts Mileage/Fuel Economy keys and their 2,128
  correction-factor descendants. Shared Current Accounts values are unchanged;
  shared projection Sales Share changes range from 0 to 735 rows per economy.
  Those projection changes must be reviewed before an authorised regeneration.

## Explicit 2022 projection seed for a 2021 review package

- Date: 2026-08-28
- Author: Codex
- Approved behavior: When the requested base year is 2021, prepend the explicit
  2022 `Sales Share` rows from the matched Reference and Target LEAP workbooks.
  Do not carry Current Accounts into the projection layer, interpolate, or
  synthesize the missing first projection year.
- Validation: Both scenarios must exist and contain only economy-matched 2022
  Sales Share rows whose `Source` is the selected workbook, with identical
  nonempty row-key coverage in Reference and Target. Processed-source
  fallback, partial scenario coverage, wrong economy/scenario/year/variable,
  non-finite values and conflicting canonical keys fail the economy package.
  LEAP workbook region aliases are explicit for China, the Philippines and the
  United States; canonical interface display names remain unchanged.
- Scope: The general projected Sales Share loader now accepts an explicit year
  set while retaining 2023-2060 as its normal build default. The 2022 injection
  occurs only for a requested 2021 staged review package.
- Verification: All 21 economies passed strict 2022 workbook-seed validation.
  A staging-only all-economy 2021 run generated 15 packages and quarantined the
  6 economies with pre-existing checked-in-static conflicts (`02BD`, `12NZ`,
  `14PE`, `16RUS`, `18CT`, `21VN`) without blocking valid economies.
- Safety: No checked-in source/default/static output, active model input/output,
  Drive file, secret, index or deployment setting was changed or promoted.

## Sparse model-manager candidate selection override

- Date: 2026-08-29
- Author: Codex
- Purpose: Allow a reviewer to select a different eligible original observation
  for one canonical Module 1 key, including an older or future observation in
  place of the automatic exact-year choice when the reviewer records why.
- Input: The optional `--manual-candidate-overrides-csv` uses exactly nine
  columns: `Economy`, `Scenario`, `Branch Path`, `Variable`,
  `Requested Base Year`, `Source Package`, `Candidate ID`, `Reviewer Reason`
  and `Reviewer`.
- Validation: The key, requested year and source package must match the staged
  package; the candidate ID must identify exactly one extracted candidate for
  the key and remain eligible under its resolver policy. A manual selection
  cannot create a value/key, target a derived variable or broaden an exact-year
  policy.
- Audit: Resolution records the selected and automatic candidate IDs, reviewer
  reason/name, source data year and base-year treatment. The manifest stores the
  normalised sparse selections.
- Safety: This remains staging-only and developer-only. It does not change ESTO
  energy-balance anchors, source/default/static data, Drive or active model data.

## Cross-validated missing operating-value proposals

- Date: 2026-08-29
- Author: Codex
- Purpose: Produce auditable last-resort proposals for required non-positive
  Current Accounts `Mileage` and `Fuel Economy` rows without presenting the
  estimates as observations.
- Method: Mask each known positive target row in turn and compare simple
  candidate methods. Use exact-branch cross-economy medians for Fuel Economy.
  For Mileage, prefer other fuel branches for the same economy and exact drive,
  then the same economy/vehicle/size, then cross-economy peers. Select by median
  absolute percentage error and then 90th-percentile error.
- Command: Run `back-end/scripts/estimate_missing_module1_values.py` with an
  explicit static-version directory, integer base year and new review-output
  directory. See
  `docs/road_module1_missing_value_estimation_case_study_2026_08_29.md`.
- Outputs: A compact 17-column proposal sheet with explicit reviewer decision
  and note fields, a full proposal audit, complete
  estimate/context evidence, raw cross-validation predictions, summary metrics
  and a checksum manifest.
- Provenance: Proposals are `model_assumption` with source data year 2022 and
  explicit derivation/replacement guidance. A later base-year test must retain
  2022 and use `carried_forward`, not relabel the estimate as native.
- Safety: The command is review-only, refuses an existing output directory and
  never applies or promotes values. Application is a separate exact-key step
  that may replace only a non-positive value. No checked-in source/default/static
  package, active model input/output, Drive file, secret or deployment setting
  was changed for the case study.
