# Road Module 1 local release readiness — 2026-08-29

## Scope and safety boundary

This checkpoint validates the researcher archive/review workflow and three
ESTO-vintage Module 1 packages locally. It did not deploy, promote a package,
edit production source/default/static data, write to Google Drive, change a
secret, or change deployment configuration. Drive behavior was exercised only
with fake services and temporary directories.

## Completed local checks

- The interface full suite passed after the missing-value work: 271 tests.
- The model full suite passed after the dashboard-context correction: 263 tests.
- The focused missing-value estimator suite passed: 9 tests, including strict
  integer-year validation, exact-key-only application, insufficient-evidence
  failure, non-overwriting atomic publication, checksums, compact reviewer
  columns, formula-safe generated cells and safe comparison-chart generation.
- The focused archive, batch-review and run-router suite passed: 63 tests. This
  covers staged pair publication, pair filenames/checksums/IDs/row counts,
  exact recorded baselines, malformed-pair quarantine, continuation after an
  orphan, large-page Drive listing, formula-injection protection, zero-new-item
  output, and atomic locked checkpoints.
- A local browser smoke test confirmed the default ESTO 2024 selector, the
  preliminary 2026 label, edit-loss warning, vintage-specific draft restore,
  source/comment guidance, changed-row styling, run acknowledgement and a
  completed 20_USA model run. Drive was deliberately unavailable; the warning
  was visible and the model run continued.
- The staged bundle contains exactly 21 economy CSVs for each of ESTO 2024,
  2025 and 2026. Across 1,229,571 rows, the scan found zero duplicate canonical
  keys, invalid years, non-numeric values, or wrong-economy rows.
- The initial all-economy × all-vintage model matrix completed 63 attempted
  runs: 39 passed and 24 failed. The same eight economies failed in every
  vintage, which isolates the issue from ESTO-vintage selection.

## Missing-value blocker found and resolved in staging

Each staged vintage contains 188 invalid Current Accounts rows: 94 zero
`Mileage` and 94 zero `Fuel Economy` values, all in the base-year slice.
They occur in `07INA`, `08JPN`, `10MAS`, `11MEX`, `12NZ`, `13PNG`, `14PE` and
`18CT`. Module 2 correctly refuses these values.

The approved staging policy is an explicit last-resort model-derived estimate,
not an inferred native observation. The review-only workflow compared candidate
methods by masking each known positive value and estimating it from the evidence
that would remain available. It selected exact-branch peer medians for Fuel
Economy and a same-economy drive/vehicle-size hierarchy for Mileage.

The resulting package contains 188 positive proposals, 3,612 estimate/context
evidence rows and 9,200 cross-validation predictions. Every proposal records
source year 2022, `model_assumption`, its concrete derivation, cross-validation
error and replacement guidance. The method and results are documented in
[`road_module1_missing_value_estimation_case_study_2026_08_29.md`](road_module1_missing_value_estimation_case_study_2026_08_29.md).

The proposals were initially applied only to disposable model-package copies.
All 24 previously failing economy/vintage runs then passed, followed by a clean
63-of-63 matrix across ESTO 2024/base year 2022, ESTO 2025/base year 2023 and
ESTO 2026/base year 2024.

## Reviewed source activation

After visual review, the 188 rows were accepted into the separate checked-in
source dataset
`manually_filled_rows/cross_validated_missing_value_estimates_2022.csv`. This
does not activate or deploy a generated frontend bundle. The dataset records
source year 2022, `model_assumption`, the concrete estimation method, proposal
ID, validation result and replacement guidance.

The seed-eligible resolver treats `model_assumption` as a configured last
resort. Any valid native observation or verified historical candidate wins,
even when it is farther from the requested base year. With no such evidence,
the 2022 proxy resolves as `transformed` for base year 2022 and
`carried_forward` for base years 2023 and 2024; its concrete estimation method
is preserved separately from that base-year treatment.

Fresh source-driven staging generated 21 of 21 economy packages for each of
base years 2022, 2023 and 2024, with zero failures, invalid Mileage/Fuel Economy
values or duplicate canonical keys. Each package set selected exactly the 188
reviewed rows. A subsequent model matrix using those source-resolved packages
passed 63 of 63 runs.

## Remaining local release checklist

1. Run the staging-only vintage release command below and inspect its
   manifests/checksums. It regenerates a corrected source fallback, resolves
   every registered vintage from original checked-in candidates, and writes
   the three immutable backend/static package versions only to explicit new
   directories. It never copies a shifted generated package into the source
   layer.
2. Repeat the local browser smoke test against the staged static root for
   selector switching, draft isolation, comment/source guidance,
   acknowledgement and one full model run.
3. Review the final generated-package diffs and provenance display.
4. Only then perform a separately authorised deployment; verify the
   deployed index and one economy from each vintage without changing Drive
   archive contents.

Run from the interface repository root with two new, caller-owned directories:

```powershell
python back-end/scripts/stage_road_module1_vintage_release.py `
  --output-root C:\path\to\new_backend_staging `
  --static-root C:\path\to\new_static_staging
```

The command refuses existing destinations, nested roots, checked-in data,
normal backend outputs, the generated frontend bundle, active model inputs and
model results. It builds behind temporary sibling directories, validates every
complete canonical package, writes per-version and release manifests with
SHA-256 checksums, and exposes the requested staging roots only after all
registered economies and vintages pass. It does not access Drive, deploy, or
update any production/static default.

The first real command run exposed a late legacy LEAP-workbook overlay that
replaced four reviewed positive `12NZ` Mileage/Fuel Economy estimates with
invalid zeros after source-priority selection. The overlay now applies the same
per-variable value contract as publication: an invalid base-year overlay is
reported and skipped, preserving the valid ranked-source fallback and its
provenance; valid workbook values continue to overlay normally.

A clean rerun staged all 21 economies for all three vintages, passed the static
row contract, wrote checksum-matched backend/static packages, and preserved
ESTO 2024 as the configured default. The local artifacts are at:

```text
C:\Users\Work\AppData\Local\Temp\road_vintage_release_20260829_final\backend_packages
C:\Users\Work\AppData\Local\Temp\road_vintage_release_20260829_final\frontend_static
```

## Deliberately deferred

- Production Drive/OAuth connectivity and real archive permissions were not
  tested because this checkpoint prohibits real Drive access.
- No production package/static activation or deployment was attempted.
- The known Starlette `httpx` TestClient deprecation warning remains; it does
  not affect current behavior and is unrelated to this workflow.
