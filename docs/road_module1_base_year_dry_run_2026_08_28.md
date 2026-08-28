# Module 1 multi-base-year dry-run report — 2026-08-28

## Scope and safety

This review exercised the opt-in staged package generator for all 21 checked-in
economies at requested base years 2021, 2022, 2024 and 2026. All outputs were
written below caller-owned Windows temporary directories. Researcher-submission
review was omitted, so the runs made no Google Drive request. No source/default
CSV, generated static bundle, production model input/output, secret, index or
deployment file was changed.

The run also repeated the 20USA 2024 package and compared the resolved CSV and
resolution audit byte-for-byte. Both were deterministic. Representative 20USA
packages for 2022, 2024 and 2026 passed canonical submission normalisation.

## Results

| Requested base year | Economies generated | Economies quarantined | Resolution totals for generated economies | Assessment |
|---:|---:|---:|---|---|
| 2021 | 0 | 21 | None | The checked-in static package begins at 2022, so strict fallback validation correctly refused to invent a 2021 slice. |
| 2022 | 20 | 1 | 5,800 resolved; 4,240 authoritative fallback; 100 derived; 10,140 rows | Complete Current Accounts slices were produced for 20 economies. Russia was quarantined for conflicting canonical keys. |
| 2024 | 16 | 5 | 928 resolved; 0 fallback; 8,192 derived; 9,120 rows | Technically valid but not a complete base-year package: only projected Sales Share and generated correction-factor rows exist at this year. |
| 2026 | 16 | 5 | 928 resolved; 0 fallback; 8,192 derived; 9,120 rows | Same structure and exceptions as 2024; also not a complete base-year package. |

For each successful 2024 or 2026 economy, the 570-row result contains:

- 58 `Sales Share` rows, selected from verified 2022 9th Outlook lineage and
  marked `carried_forward`;
- 256 generated `Mileage Correction Factor` rows; and
- 256 generated `Fuel Economy Correction Factor` rows.

It contains no Current Accounts Stock, Mileage, Fuel Economy, survival, vintage,
reconciliation or saturation rows. Therefore these outputs must remain review
artifacts and must not be activated as model/interface base-year packages.

## Quarantined source conflicts

The source CSVs were treated as untrusted. Same-key duplicates were grouped and
their values compared rather than silently selecting the first row.

| Year(s) | Economies | Conflict |
|---|---|---|
| 2022 | `16RUS` | 66 conflicting Current Accounts keys: 47 Fuel Economy and 19 Sales Share. Five additional Stock Share duplicate keys have identical values and are safely handled by the existing explicit-derived-row rule. |
| 2024 and 2026 | `02BD`, `12NZ`, `14PE`, `18CT`, `21VN` | Each economy has 22 conflicting Reference Sales Share keys at each tested year. |

All other economies have five identical 2022 Stock Share duplicates representing
the source copy and the explicit Stock-derived copy. The loader retains the one
explicitly derived row only when their comparable values agree.

Later source-path inspection showed these conflicts are packaging defects, not
independent source-owner choices. The five short economy codes missed their
economy-specific Reference workbooks and fell back to an unfiltered
`ALL_ECONS` workbook. Russia combined original Current Accounts and Reference
rows after relabelling both as Current Accounts. Row order remains an invalid
way to resolve either defect.

## Implementation defect corrected during validation

`Mileage Correction Factor` and `Fuel Economy Correction Factor` are generated
static controls outside the maintained 24-variable source contract. They were
missing from the variable-policy registry, then were incorrectly sent to a
resolver despite having no resolver policy. They are now explicit generated-only
derived variables. Package generation preserves them as authoritative derived
rows with audit reason `generated_derived_control_preserved`; they never become
source candidates.

## Follow-up implementation

At the time of the initial dry run, the generator took its authoritative key set
from the requested-year static slice. That was suitable for auditing an
existing slice, but could not construct a new base year:

- 2021 has no slice at all; and
- future slices contain projection rows rather than the complete Current
  Accounts/base-year contract.

The recommended design below is now implemented in the opt-in review-package
path:

1. Keep a reviewed Current Accounts **base-year template** separate from
   Reference/Target projection series. Initially this would use the complete
   2022 Current Accounts key set, with source scenarios separated before any
   Current Accounts relabelling.
2. For a requested base year, keep that template's canonical row keys and resolve
   each seed-eligible value from original candidates. Preserve the selected
   source year and mark `native`, `carried_forward` or `carried_backward`.
3. Recalculate Stock Share from resolved Stock. Keep generated correction
   factors in the projection layer, not in the base-year candidate set.
4. Join the reviewed resolved Current Accounts slice to the separately maintained
   Reference/Target projection series when producing a complete immutable
   interface/model package.
5. Validate and review that complete package before activation. Never use a
   previously shifted package as a new source-candidate pool.

The generator now writes the resolved Current Accounts slice, the retained
Reference/Target projection series, and a validated complete package as three
separate CSVs with manifest checksums and row counts. Projection coverage must
be continuous and identical in both scenarios from base year + 1, malformed or
conflicting rows fail, and a shifted output never becomes a candidate source.

A representative 20USA/2024 review package contains 507 Current Accounts rows,
20,540 projection rows and 21,047 complete-package rows spanning 2024–2060.
An all-economy 2024 run generated all three package components for 15 economies
and quarantined six without stopping later economies: the five projection
conflict economies plus Russia's Current Accounts conflicts.
The follow-up conflict inventory gives reviewers a compact one-row-per-group
sheet plus full evidence. Russia has 66 groups / 132 evidence rows across Fuel
Economy and Sales Share. Each of the other five economies has 809 projected
Sales Share groups / 8,143 evidence rows across the retained 2025–2060 series;
this confirms why the compact decision sheet must remain separate from raw
evidence.
The requested 2021 case now reaches the complete template but is deliberately
quarantined because the checked-in projection series begins in 2023 and cannot
supply 2022. The Russia and five projected Sales Share conflict groups described
above are now prevented in code: short and canonical economy codes resolve the
same workbook token, ALL_ECONS fallback rows are filtered to the requested
region, and Current Accounts construction prefers true Current Accounts rows,
uses other scenarios only for missing keys, and rejects any remaining
disagreement. A temporary all-economy static build wrote 21 files with 20,031
rows each and zero duplicate canonical keys. It was not promoted: its key/value
diff from the existing 22,212-row checked-in bundle still requires review before
any authorised regeneration. The diff has no added keys and removes 2,156
unique keys per economy: 28 Current Accounts Mileage/Fuel Economy keys now
outside the maintained static contract and their 2,128 projected correction-
factor descendants. Shared Current Accounts values do not change. Shared-value
changes are confined to projected Sales Share (0–735 rows per economy),
including the intended short-code Reference workbook corrections plus other
projection differences that still need review.

The remaining 2021 projection choice is genuinely policy-relevant. The safest
technical option is to retain explicit 2022 Reference/Target Sales Share rows
already present in the source workbooks, because carrying 2021 Current Accounts
or interpolating 2022 would invent assumptions. This option still requires
model-manager confirmation before implementation. Activation and interface
discovery remain separate actions.
