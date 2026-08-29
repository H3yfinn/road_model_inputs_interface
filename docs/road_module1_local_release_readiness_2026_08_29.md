# Road Module 1 local release readiness — 2026-08-29

## Scope and safety boundary

This checkpoint validates the researcher archive/review workflow and three
ESTO-vintage Module 1 packages locally. It did not deploy, promote a package,
edit production source/default/static data, write to Google Drive, change a
secret, or change deployment configuration. Drive behavior was exercised only
with fake services and temporary directories.

## Completed local checks

- The interface full suite passed after the missing-value work: 270 tests.
- The model full suite passed after the dashboard-context correction: 263 tests.
- The focused missing-value estimator suite passed: 8 tests, including strict
  integer-year validation, exact-key-only application, insufficient-evidence
  failure, non-overwriting atomic publication, checksums, compact reviewer
  columns and formula-safe generated cells.
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

The proposals were applied only to disposable model-package copies. All 24
previously failing economy/vintage runs then passed. A fresh complete 21 × 3
matrix subsequently passed 63 of 63 runs across ESTO 2024/base year 2022, ESTO
2025/base year 2023 and ESTO 2026/base year 2024. No proposal has been promoted
into a checked-in source/default/static package.

## Human review required before activation

A reviewer must inspect and accept the 188-row proposal/evidence package before
the values are added to the source layer and a new immutable package is built.
That is a promotion decision, not something the estimator performs. If accepted,
2022 remains the source data year; use in the 2023 and 2024 base-year packages
must be `carried_forward`. Native evidence introduced later must take priority
over the model assumption.

## Production-ready checklist after that decision

1. Review and accept or revise the 188 proposal rows and their evidence.
2. Add accepted values to the correct documented source layer, then regenerate
   all three packages into a new staging directory; do not reuse a
   shifted/generated package as candidate evidence.
3. Require 21 successful economy packages per vintage and zero quarantined
   source conflicts.
4. Run the static publication gate and require zero invalid values and zero
   duplicate canonical keys.
5. Rerun the 21 × 3 model matrix and require 63 successful runs.
6. Repeat the local browser smoke test for selector switching, draft isolation,
   comment/source guidance, acknowledgement and one full model run.
7. Rerun focused archive/batch tests and both repositories' full suites.
8. Review the final diffs and generated-package manifests/checksums.
9. Only then perform a separately authorised promotion/deployment; verify the
   deployed index and one economy from each vintage without changing Drive
   archive contents.

## Deliberately deferred

- Production Drive/OAuth connectivity and real archive permissions were not
  tested because this checkpoint prohibits real Drive access.
- No production package/static activation or deployment was attempted.
- The known Starlette `httpx` TestClient deprecation warning remains; it does
  not affect current behavior and is unrelated to this workflow.
