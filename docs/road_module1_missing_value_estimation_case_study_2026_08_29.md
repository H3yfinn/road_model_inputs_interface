# Case study: estimating missing Module 1 operating values

## Outcome

The staged ESTO 2024 package contained 188 invalid Current Accounts inputs:
94 zero `Mileage` values and the matching 94 zero `Fuel Economy` values. A
review-only estimator produced one positive, auditable proposal for every row.
It did not alter checked-in sources, generated defaults, the browser static
bundle, active model inputs, Google Drive, secrets or deployment settings.

The affected economies were `07INA`, `08JPN`, `10MAS`, `11MEX`, `12NZ`,
`13PNG`, `14PE` and `18CT`. The first six had 30 proposals each. New Zealand
and Chinese Taipei each had four proposals for the two FCEV truck branches.

These are model assumptions, not observations. A zero is not a defensible
operating value for a branch that the canonical package includes: it causes
zero vehicle activity or an invalid efficiency calculation even when the
branch has little or no stock in the base year.

## Estimation question

For each missing branch, the useful evidence differs by variable:

- Mileage is strongly economy-specific. A related drive or vehicle-size value
  in the same economy can describe local vehicle use better than the exact
  branch median across all economies.
- Fuel economy is strongly technology- and branch-specific. The exact branch
  across peer economies can be more reliable than an economy-wide adjustment.

The workflow therefore tested simple alternatives instead of selecting a
single universal proxy by intuition.

## Methods compared

For every known positive row, the workflow temporarily treated that row as
missing and estimated it using only evidence that would remain available in a
real missing-row case. The target row itself was always excluded.

For both variables it tested the median of the exact branch in other economies.
For Mileage it also tested this hierarchy:

1. median of other fuel branches for the same economy, vehicle and exact drive;
2. if unavailable, median of other branches for the same economy, vehicle and
   size;
3. if unavailable, exact-branch median from other economies.

For Fuel Economy it also tested an economy-adjusted peer median. The adjustment
used the economy's ratios to peer medians in other comparable branches. This
more elaborate method was retained in the audit but rejected by the results.

The median prevents one unusual economy from controlling a proposal. At least
five peer economies are required for an exact-branch peer estimate. Strategy
selection is deterministic: lowest median absolute percentage error, then
lowest 90th-percentile error, then the simpler method if still tied.

This is masked-known-value cross-validation, not a claim that the source data
are independent observations. For the Mileage hierarchy, other values from the
same economy are deliberately available because those are the values that
would be available when filling the actual missing branch.

## Cross-validation result

Each method produced 2,300 test predictions for its variable.

| Variable | Method | Median absolute percentage error | 90th percentile |
|---|---|---:|---:|
| Fuel Economy | Exact-branch peer median | 4.6% | 36.8% |
| Fuel Economy | Economy-adjusted peer median | 12.4% | 44.4% |
| Mileage | Exact-branch peer median | 15.4% | 53.7% |
| Mileage | Same-economy hierarchy | 0.1% | 7.3% |

The selected methods were therefore exact-branch peer median for Fuel Economy
and the same-economy hierarchy for Mileage. Mean percentage error was not used
for selection because a small number of known values are very close to zero,
making their percentage errors disproportionately large. The raw predictions
are retained so reviewers can inspect those tails rather than hiding them.

## The 188 proposals

The final proposal mix was:

| Variable and method | Rows |
|---|---:|
| Fuel Economy — exact-branch peer median | 94 |
| Mileage — same-economy exact-drive median | 42 |
| Mileage — same-economy vehicle-size median | 52 |

Proposed Fuel Economy values range from 61.12 to 1,441.96 MJ/100 km, with a
median of 206.45. Proposed Mileage values range from 4.97 to 40.62 thousand km,
with a median of 11.24.

The workflow records the selected strategy, concrete estimation method,
proposal ID, peer median, peer-economy count, cross-validation errors, source
data year, classification, base-year treatment and replacement guidance. The
separate evidence file contains every value used in an estimate. Where Mileage
uses same-economy evidence, it also includes the exact-branch peer values shown
for comparison.

The estimates are labelled:

```text
Source = Cross-validated Module 1 missing-value estimate
Source Classification = model_assumption
Source Data Year = 2022
Review Status = proposed_model_derived_proxy
```

For the 2022 base-year package, `Base Year Treatment=transformed`. When the same
estimate is tested in a 2023 or 2024 base-year package, the value remains a 2022
estimate and is labelled `carried_forward`; it must not be presented as native
2023 or 2024 data.

## Reproducing a review package

Run the estimator against an explicit, immutable static-version directory and
a new output directory:

```powershell
python back-end/scripts/estimate_missing_module1_values.py `
  --static-dir <static-version-directory> `
  --base-year 2022 `
  --output-dir <new-review-output-directory>
```

The output directory must not already exist. It contains:

- `proposed_missing_values.csv` — the compact 17-column reviewer view; record
  `accept`, `reject` or `revise` in `Reviewer Decision` and explain the evidence
  or reason in `Reviewer Note`;
- `proposal_audit.csv` — all machine-readable strategy and provenance fields;
- `proposal_evidence.csv` — the inputs behind each decision;
- `cross_validation_predictions.csv` — every masked-row prediction;
- `cross_validation_summary.csv` — method comparison; and
- `proposal_comparison.html` — an interactive dashboard-style scatterplot for
  comparing each proposal with exact-branch peers and related same-economy
  estimate inputs; and
- `estimation_manifest.json` — source and artifact SHA-256 checksums, counts and
  selected strategies.

The generator publishes the set through a sibling staging directory, refuses
to overwrite an existing review package and never applies proposals. Applying
a reviewed proposal is a separate operation that accepts only an exact
canonical key whose existing value is non-positive. It refuses absent keys,
duplicate proposals, positive-value replacement, non-finite estimates and
fractional years.

### Visual review

Open `proposal_comparison.html` and choose the economy, variable and datapoint.
It reuses the dashboard's spread-dot visual language:

- a red diamond and dotted horizontal line show the proposed value;
- blue circles show the exact same branch in other economies; and
- green triangles show related same-economy values used by the selected
  Mileage method.

Hover text retains the economy, complete branch, value and evidence role. The
summary below the chart repeats the proposal, method, input count and
cross-validation median error. Stored Mileage values are expanded from their
`Thousands` scale to km/vehicle/year. Fuel Economy is labelled in MJ/100 km and
the page explicitly explains that lower means more efficient. The chart uses the
same pinned Plotly CDN approach as the generated model dashboard; the CSV and
manifest evidence remain usable if the chart library is temporarily offline.

## What this case study does and does not establish

This case demonstrates a repeatable last-resort method for keeping every
required model branch usable while being honest about uncertainty. It does not
make the estimates native evidence, prove that every branch is equally likely,
or authorise automatic promotion.

Native or better documented economy-specific evidence should replace a proxy
through the normal researcher submission and developer review process. The
original proposal ID and derivation audit should remain available so the reason
for the replacement is clear. A future missing-value case may need different
candidate methods; it should repeat the same pattern of explicit assumptions,
masked-value validation, complete evidence, staging-only review and model-run
validation rather than copying these values blindly.
