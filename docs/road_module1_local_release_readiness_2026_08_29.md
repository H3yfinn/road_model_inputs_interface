# Road Module 1 local release readiness — 2026-08-29

## Scope and safety boundary

This checkpoint validates the researcher archive/review workflow and three
ESTO-vintage Module 1 packages locally. It did not deploy, promote a package,
edit production source/default/static data, write to Google Drive, change a
secret, or change deployment configuration. Drive behavior was exercised only
with fake services and temporary directories.

## Completed local checks

- The interface full suite passed before the release scan: 258 tests.
- The model full suite passed after the dashboard-context correction: 262 tests.
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

## Release blocker found by validation

Each staged vintage contains 188 invalid Current Accounts rows: 94 zero
`Mileage` and 94 zero `Fuel Economy` values, all in the native base-year slice.
They occur in `07INA`, `08JPN`, `10MAS`, `11MEX`, `12NZ`, `13PNG`, `14PE` and
`18CT`. Module 2 correctly refuses these values.

The checked-in source pool also contains positive cross-economy median proxy
rows for the same keys. Candidate extraction now rejects and audits the invalid
higher-priority zeros, but the resolver correctly does not reinterpret those
derived proxies as native observations. Automatically making them eligible is
a data-policy decision, not a validation fix. Static publication now fails on
these invalid values so the problem cannot be hidden in a new bundle.

## Human decision required

Choose one policy before activation:

1. **Explicit last-resort proxy policy (recommended).** Classify the existing
   positive median fills as model-derived proxy assumptions, make that class
   eligible only when no native or verified historical candidate exists, and
   preserve source year 2022, derivation method and replacement guidance. This
   keeps all required branches runnable without presenting proxies as observed
   data.
2. **Require economy-native replacements.** Keep the eight economies blocked
   until researchers provide positive native Mileage/Fuel Economy evidence.
   This has the strongest evidence standard but prevents a complete release.
3. **Remove/exempt affected branches.** This would weaken the current global
   Module 1 branch contract and is not recommended without a separate modeling
   review showing those drive/fuel branches are genuinely inapplicable.

## Production-ready checklist after that decision

1. Implement and document the approved policy with focused tests.
2. Regenerate all three packages into a new staging directory; do not reuse a
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
