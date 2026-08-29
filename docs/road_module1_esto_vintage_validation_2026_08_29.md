# Road Module 1 ESTO-vintage staging validation — 2026-08-29

## Scope and safety

This validation built and checked the three registered ESTO-vintage packages:

| ESTO vintage | Base year | Package version |
|---:|---:|---|
| 2024 (configured default) | 2022 | `v2026_08_29_esto_2024` |
| 2025 | 2023 | `v2026_08_29_esto_2025` |
| 2026 (preliminary) | 2024 | `v2026_08_29_esto_2026` |

All generated artifacts were written below a caller-owned Windows temporary
directory. No Drive request was made. No checked-in source/default data,
frontend static bundle, production model input/output, secret, deployment file,
or static index was changed or promoted.

The validation first regenerated a corrected temporary source/static baseline.
It produced all 21 economy files and passed the maintained static row contract.
Each vintage run then used those same corrected temporary CSVs as its immutable
fallback template, rather than the known-conflicted legacy checked-in bundle.

## Package-generation results

| Base year | Economies generated | Quarantined | Complete rows per economy | Aggregate complete rows |
|---:|---:|---:|---:|---:|
| 2022 | 21 | 0 | 20,031 | 420,651 |
| 2023 | 21 | 0 | 19,517 | 409,857 |
| 2024 | 21 | 0 | 19,003 | 399,063 |

For every one of the 63 economy-vintage packages, the independent audit:

- recalculated and matched the Current Accounts, projection, and complete CSV
  checksums recorded in the manifest (189 component checksums total);
- verified the exact canonical-long columns;
- found no duplicate `(Economy, Scenario, Branch Path, Variable, Year)` keys;
- verified the package version, economy, requested base year, and row counts;
- verified that Current Accounts contained only the requested base year;
- verified Reference and Target projection coverage began at base year + 1;
- rejected any fractional recorded source year; and
- confirmed that no manual candidate override was applied.

The staged packages were then copied only within the temporary directory into
the directory/filename shape consumed by `leap_road_model`. All 21 economies
for each of the three vintages loaded through the model adapter, including
survival and vintage profiles. This test initially exposed a hard-coded 2022
adapter assumption. It was corrected in `leap_road_model` so the adapter now
uses the validated selected base year and rejects fractional years, while
preserving Russia's explicit legacy 2022-to-2021 bridge.

## Source-year selection observed

Future candidates were exercised rather than merely allowed in theory:

| Base year | Native dated rows | Earlier dated rows | Later dated rows |
|---:|---:|---:|---:|
| 2022 | 5,920 | 220 | 525 |
| 2023 | 0 | 6,140 | 525 |
| 2024 | 66 | 6,140 | 459 |

These counts cover dated Current Accounts rows across all economies. Each
selected row retains its original source year and whether it was carried
forward or backward; a shifted package is never reused as an original source.

## Provenance policy resolved after validation

The 2022 packages contain 3,394 Current Accounts rows classified
`legacy_unknown` / `legacy_unrecorded`. They occur in every economy:

| Variable group | Rows |
|---|---:|
| Survival Rate | 1,596 |
| Vintage Profile Share | 1,596 |
| Turnover bounds | 84 |
| Fuel Economy / Mileage manual fills | 76 |
| Passenger/freight projection adjustments | 42 |

The filenames and comments are retained, so these rows are not anonymous. They
come from lifecycle workbooks, lifecycle defaults, manually filled missing
rows, and model-assumption defaults. However, they are not all documented as
9th Outlook observations, so assigning 2022 to every row would create false
precision and would contradict the conservative provenance rule.

The reviewed policy is to classify lifecycle curves, turnover controls, and growth
adjustments explicitly as structural/model assumptions for which a data year
may be not applicable; separately record 2022 for the manual Fuel Economy and
Mileage rows whose checked-in row and comment explicitly identify a 2022
value, while retaining the request for better source detail. Do not label all
3,394 rows as 9th Outlook data. This policy is implemented in explicit,
version-scoped source-provenance rules and will apply when the packages are
regenerated.

An in-memory post-policy recheck across the same 21 staged 2022 economy
packages preserved every canonical key and numeric value. It produced zero
`legacy_unrecorded` treatments, identified 3,192 structural-assumption rows and
126 model-assumption rows with no fabricated source year, and recorded 2022 on
the 76 manual Fuel Economy/Mileage fallback rows.

The subsequent all-economy model matrix found that the candidate extractor
could still prefer a higher-priority checked-in zero over one of those positive
manual fallbacks. Zero is not a valid `Mileage` or `Fuel Economy` value under
the existing Module 1 contract. Candidate extraction now applies that contract
before source-priority resolution, records the excluded source row as
`invalid_value_for_variable`, and allows the already-reviewed positive fallback
to compete normally. This changes neither source files nor the fallback policy;
it prevents an invalid source value from masking an existing valid candidate.

## Activation status

The code contract, interface selector, package generator, and model adapter are
validated. The three vintage packages remain staging artifacts and are not
discoverable in the production interface. Activation still requires an
authorised regeneration/promotion of the generated backend outputs and static
bundle, followed by an interface smoke test. ESTO 2024 / base year 2022 is the
configured initial default; the build will refuse to publish vintage choices
if that default package is missing.
