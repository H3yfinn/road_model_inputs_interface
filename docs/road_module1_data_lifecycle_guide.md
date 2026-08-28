# Road Module 1 data lifecycle and provenance guide

## Purpose

This is the central human/AI guide to how Road Module 1 data moves from
evidence to the researcher interface and model. It separates ordinary
researcher entry, model-manager setup, developer-only review, and promotion.
Specialist operating instructions remain in the linked guides.

## The short version

```text
original source evidence
  -> prepared source rows
  -> priority-ranked source merge
  -> base-year resolution from original candidates
  -> derived rows recalculated
  -> immutable generated package + manifest + audit
  -> researcher edits an in-browser working copy
  -> complete submitted package is archived
  -> model manager/developer reviews submissions offline
  -> approved changes update the correct source layer
  -> a new immutable defaults version is built
```

The browser is an editor and model hand-off. Google Drive is an immutable
submission archive. Neither is the source of truth for approved defaults.

## Roles and visible workflows

| Role | Normal surface | What it should show | What it must not do |
|---|---|---|---|
| Researcher | Road Module 1 browser interface | Editable values, units, compact source/data-year status, source details on demand, and **Source / reason for change** | Review other submissions, promote defaults, choose source priority, or edit Drive/source files |
| Model manager/operator | Notebook or separate advanced setup surface | Economy/base year, fallback strategy, sparse per-variable overrides, resolution summary and audit | Change approved sources silently or expose batch-review controls to researchers |
| Developer/reviewer | Local scripts and reviewer CSVs | Exact-baseline comparison, conflicts, duplicates, quarantine, candidates and promotion plan | Treat an archive as approved or automatically modify Drive/source/default/static files |
| Model | Validated canonical package | Values plus source year, classification, treatment and derivation | Guess missing rows or reinterpret browser values |

The developer-only workflow in
[`researcher_change_review_and_promotion_guide.md`](researcher_change_review_and_promotion_guide.md)
does not belong in the ordinary researcher interface.

## Authoritative layers

| Layer | Location | Authority |
|---|---|---|
| Source evidence | `back-end/data/road_model/` | Approved numeric defaults and provenance |
| Generated defaults | `back-end/outputs/road_module1_defaults/` | Rebuildable output; never hand-edit as source |
| Browser static package | `front-end/road-module1-static/` | Immutable generated browser/model hand-off version |
| Browser working copy | Browser memory and version/economy-scoped draft | Temporary researcher overlay |
| Model runtime copy | `leap_road_model/input_data/module1_defaults/` | Last submitted run input, not a default source |
| Drive archive | `Road model researcher submissions/<economy>/` | Immutable audit record, not an approval database |
| Local review outputs | Secure review-output folder | Developer decision support, never automatically active |

## Source and provenance contract

Every value must have an honest provenance state. A nonblank filename alone is
not necessarily adequate evidence.

### Known source

Retain the most specific detail available: dataset/workbook/document or reviewed
submission, actual source-data year, link/reference, classification, evidence
grade or estimation status, and transformation notes.

### Legacy value with incomplete evidence

Do not invent a citation. Where no recoverable lineage has been established,
use:

```text
Legacy input — original source detail not yet recorded; please update when better evidence is available.
```

Use `9th Outlook input — ...` only where repository evidence establishes that
lineage. For the known 9th Outlook transport lineage, the historical provenance
is preserved in an archived transport data system even when it has not yet been
joined into the current canonical row. Use:

```text
9th Outlook legacy input — row-level provenance is preserved in the archived 9th-edition transport data system and can be investigated on demand: https://drive.google.com/file/d/103sIJ1L1mbQpGfL2shlB8nrIOTkbyFz3/view?usp=drive_link. The displayed value may also reflect subsequent aggregation, disaggregation, or model reconciliation.
```

Until a separate classification migration is reviewed, keep incomplete legacy
classification as `legacy_unknown` internally. In this context that status
means **archived provenance not yet linked**, not that the original provenance
never existed. Do not present it to researchers simply as “source unknown.”

### Derived or generated value

Record the derivation, not a fictitious external source. For example, `Stock
Share` is derived from resolved `Stock`; preserve the upstream source and
derivation method.

### Researcher change

The note should include the dataset/document, source year, link/reference where
available, and why the value changed. Missing detail remains a non-blocking run
warning and is visible to the developer reviewer.

### Provenance enrichment used by future builds

`back-end/core/road_module1_provenance.py` normalises canonical-long provenance
without changing `Value` or the canonical key `(Economy, Scenario, Branch Path,
Variable, Year)`. The rule order is:

1. Preserve and validate explicit structured metadata. An explicit `Source Data
   Year` always wins.
2. Apply an explicit source-lineage rule only when both the source-name pattern
   and package version match.
3. For a proven, version-scoped 9th Outlook lineage with no source year, use
   2022. Canonical display provenance remains honest about the legacy lineage;
   candidate extraction separately applies the non-native
   `verified_9th_outlook` eligibility marker.
4. Mark identified derived/generated rows with their actual derivation rather
   than representing them as external observations.
5. Leave an uncertain source year blank, retain `legacy_unknown`, and add the
   honest missing-detail guidance.

The checked-in mapping is intentionally narrow. For
`v2026_06_05_road_module1_sources`, it covers the current
`road_module1_source_<economy>.csv` package and the specifically dated Target
20260526 / Reference 20260615 transport-export packages. Repository evidence in
`leap_transport/docs/PROCESS_FLOW.md` establishes that those packages bridge
9th-edition transport inputs into LEAP. A differently dated workbook, another
LEAP export, another generated package, or a vaguely similar filename does not
inherit that mapping. Add or change a rule only after reviewing the exact source
generation path and documenting the evidence.

For Current Accounts rows, a source year earlier than the economy base year is
`carried_forward`; a later source year is `carried_backward` with
`future_year_seed`. Thus a literal Russia 2022 source remains 2022 when used for
the 2021 base year. A same-year 9th Outlook legacy input is `transformed`, not
`native`, unless explicit structured metadata establishes a native observation.

The five vehicle-type `Stock Share` rows explicitly marked
`stock_share_from_stock` are derived from resolved `Stock`. More detailed
technology/size Stock Share rows have no matching canonical Stock detail and
retain their authoritative fallback provenance and values. Projected
stock-share seeds, generated mileage/fuel-economy correction factors,
specialist replacement sales shares, and scenario clones retain distinct
derivation methods. Supplemental inputs propagate an explicit four-digit
`data_year` through `Source Data Year`; their evidence grade or estimation
status is not silently upgraded to a native classification.

`audit_module1_source_quality()` reports total, complete external provenance,
operationally complete, archived-reference-available, legacy-detail-needed,
derived/generated, missing-date, and missing-classification counts in memory.
Known 9th Outlook rows with the archive link count as operationally complete
and are excluded from `legacy_detail_needed`; their internal classification
remains `legacy_unknown`. The audit writes a CSV only when the caller supplies
an output path; production artifacts are never an implicit side effect.

### Archived 9th Outlook provenance recovery

The full 9th-edition transport data system and related APERC-era code archives
are preserved in this read-only recovery folder:

- [APERC code archive folder](https://drive.google.com/drive/folders/1K--aSZYmolHb0Kl3m9ANjw11jWFdpj9u)
- [Full 9th-edition transport data system ZIP](https://drive.google.com/file/d/103sIJ1L1mbQpGfL2shlB8nrIOTkbyFz3/view?usp=drive_link)

The folder also contains `transport_model_9th_edition.7z`, the archived model
used to inspect the exact source-generation path. Inside that model archive,
the strongest current combined provenance snapshot is:

```text
transport_model_9th_edition/input_data/transport_data_system/combined_data_DATE20250122.csv
```

It contains 130,773 unique rows keyed by economy, date, medium, measure, vehicle
type, transport type, drive and fuel. Its `dataset` and `comment` fields recover
useful lineage including 9th Outlook ESTO, EGEDA/8th transport splits, IEA EV
Explorer, ATO and named national statistics. Generic labels such as
`manually_inputted_data`, `estimated` and `9th_model_first_iteration` still need
human interpretation. A named technical-assumption source also does not make a
row a native economy observation; for example, US Alternative Fuels Data Center
efficiency assumptions were applied across multiple economies.

The archived 9th-model import code explicitly dropped `Dataset`, `Source` and
`Comment` before the transport inputs were reshaped. Later aggregation dropped
`Dataset` again. Non-road splitting, unit conversion, ESTO reconciliation and
other model calculations could then change the numeric value. Consequently,
future recovery must distinguish:

- an exact external observation;
- a technical assumption seeded from an identified dataset;
- an archived source row subsequently reconciled or transformed; and
- a derived/generated value with multiple upstream inputs.

Do not ingest the Drive ZIP or scan the archive at browser/model runtime. The
Drive folder is recovery evidence, not an active source/default layer. Recovery
work should use a reviewed local or temporary extract, join on the full archived
source key, preserve transformation notes, and generate a new immutable package
only after tests and human review. Do not commit the entire combined CSV or
replace current numeric values merely because an archived row shares a key.

An older local copy, `combined_data_DATE20230902.csv`, is useful for historical
comparison but is not the primary reference: it has fewer rows and source
labels, and many shared keys changed value or dataset label before the 2025
snapshot.

No bulk provenance-recovery or row-by-row crosswalk is planned. Known rows that
carry the archive guidance are **complete enough for normal operation** and do
not belong in a reviewer action queue. Their `legacy_unknown` classification is
an honest technical description, not a request for more work. The records
should remain as they are and be replaced gradually when better sources arrive
through normal reviewed updates. If a particular value ever becomes material,
the archive and its full source key remain available for an on-demand lookup.

## Current source-quality audit

Snapshot reviewed on 2026-08-28 for checked-in version
`v2026_06_05_road_module1_sources` (21 economy CSVs, 505,458 long rows):

| Check | Result | Assessment |
|---|---:|---|
| Nonblank `Source` | 505,458 / 505,458 | Technically complete |
| Nonblank `Comment` | 505,458 / 505,458 | Technically complete |
| Nonblank structured `Source Data Year` | 0 / 505,458 | Material gap |
| Nonblank/non-legacy `Source Classification` | 0 / 505,458 | Material gap |

The row count is dominated by generated annual rows, not independent
observations:

- 408,576 mileage/fuel-economy correction-factor rows have an explicit
  generated-default label. That is valid control/derivation provenance, not
  external evidence.
- Roughly 84,000 projected `Sales Share` rows name LEAP export workbooks, but
  underlying evidence and source-data year are not separately structured.
- 6,598 rows point to an internal
  `processed_source/road_module1_source_<economy>.csv` and say only `Loaded from
  preprocessed Road Module 1 source.` This records pipeline lineage but not the
  original evidence.
- Named survival/vintage workbooks and supplemental APEC files are more useful.
  Several contain data year, evidence grade, range or estimation status, but
  those details are not consistently propagated into canonical fields.
- Manually filled rows, model-assumption defaults and final overrides generally
  have generic internal-file descriptions and need the most enrichment.

Overall: **the package is traceable to internal files, but evidence provenance
is not consistently high quality**. A future generated version should preserve
known detail, use honest legacy placeholders, and populate structured
provenance. Do not hand-edit an existing immutable static version.

### Temporary enriched-build validation

On 2026-08-28 the complete 21-economy backend and static build was run into an
isolated temporary directory using the checked-in sources and the enrichment
rules above. The resulting 404,974 static canonical rows produced this in-memory
audit (categories may overlap):

| Metric | Rows |
|---|---:|
| Complete external provenance | 0 |
| Legacy detail needed | 58,924 |
| Derived/generated | 346,050 |
| Missing source date | 345,344 |
| Missing/non-specific classification | 59,630 |

The zero complete count is deliberate rather than a failed upgrade: the
current 9th Outlook bridge rows still lack original source detail and remain
`legacy_unknown`, while supplemental synthetic/model inputs are not promoted to
native observations. All 181 Russia Current Accounts rows carrying an explicit
2022 source year were retained as 2022 and marked `carried_backward` for the
2021 base year. The temporary validation also confirmed that enrichment did not
change any canonical key or numeric value. No production output or static file
was regenerated.

This audit predates discovery of the archived transport data system and the
later operational-status split. A current audit separates proven rows carrying
the archive link into `archived_reference_available` and counts them as
`operationally_complete`, without making them native observations. Only other
unresolved legacy rows remain in `legacy_detail_needed`. The discovery does not
alter recorded source years or transformed classifications.

## Base-year resolution

The all-economy 2021/2022/2024/2026 dry run and its quarantined conflicts are
recorded in
[`road_module1_base_year_dry_run_2026_08_28.md`](road_module1_base_year_dry_run_2026_08_28.md).
It confirms that a requested-year projection slice is not a complete base-year
template; do not activate those staged outputs as interface/model packages.

Resolution starts from original candidates, never a previously shifted output.
Current Module 1 policies are simple:

- 23 original source/researcher/model-judgement variables are `seed_eligible`;
- `Stock Share` is never a resolver candidate; only rows explicitly marked
  `stock_share_from_stock` are recalculated from resolved `Stock`;
- generated `Mileage Correction Factor` and `Fuel Economy Correction Factor`
  rows are derived controls outside the maintained 24-variable source contract
  and are never resolver candidates;
- ESTO energy balances are external exact-year reconciliation anchors.

An exact-year eligible observation wins. Otherwise the selected fallback keeps
its real source-data year and is marked `carried_forward` (earlier source) or
`carried_backward` (future source).

Rows that remain honestly classified as `legacy_unknown` are resolver-eligible
only when the candidate extractor can reproduce an explicit, version-scoped
9th Outlook lineage mapping. The candidate carries the separate
`verified_9th_outlook` marker; package generation recomputes that marker from
the canonical `Source` and source-package version, so an arbitrary legacy row
cannot opt itself in. This exception applies only to seed-eligible Module 1
variables and never broadens an exact-year energy-balance policy.

Initial strategies should remain limited to:

- `prefer_earlier`: latest earlier, then earliest future. This is the only
  strategy currently implemented by the pure resolver and opt-in generator;
- `closest_available`: a documented future option, not currently implemented.

The current opt-in generator accepts sparse per-variable resolver-policy
overrides. They can make a `seed_eligible` variable stricter by requiring an
exact-year native observation, but cannot broaden an exact-year policy or make
another classification eligible. Store these choices in the generated
manifest/audit, not in approved source/default data.

### Opt-in backend generation boundary

`back-end/core/base_year_package_generation.py` is the first package-writing
boundary for the pure resolver. It is deliberately separate from
`write_economy_package()` and is not called by the browser, API startup, normal
defaults build, or static-bundle build. The checked-in static package remains
the authoritative fallback.

An operator supplies all of the following explicitly:

- one economy and requested base year;
- the complete canonical-long fallback rows for that economy/year;
- original candidate records whose payload year is their actual source-data
  year and whose canonical key exists in the fallback;
- a source-package identity, future package version, optional sparse policy
  overrides, and a caller-owned output directory.

For each non-derived fallback key, the generator calls the existing resolver.
A selected candidate replaces that value and preserves its real source year,
classification, treatment and source identity. If no candidate is eligible,
the fallback row is copied unchanged. `legacy_unknown` remains ineligible.
`Stock Share` candidates are rejected. Rows explicitly marked
`stock_share_from_stock` are recalculated from resolved `Stock`; detailed
shares without that derivation marker are copied from the authoritative
fallback because matching Stock detail does not exist. Candidate IDs must be
package-wide unique, and a candidate labelled shifted/generated—or a payload
whose year differs from its source year—fails validation so generated output
cannot be recycled as input.

The caller-owned directory receives a canonical CSV, deterministic resolution
audit CSV, and JSON manifest. The manifest records the economy, requested base
year, source package, strategy/overrides, summary and rejection counts,
filenames, and SHA-256 checksums. Selected candidate provenance is recorded in
the audit. Generation time is isolated at the manifest top level; the nested
`resolution` object and both CSV files are deterministic for equivalent inputs.

This is not production promotion. The function refuses to write beneath the
checked-in data directory, current backend defaults output root, or frontend
static root. Development and review must use a temporary or otherwise
caller-owned staging directory. Promotion, index updates, UI selection, source
discovery beyond the narrow adapter below, `closest_available`, additional
eligibility, and supplemental-source extraction remain separately reviewed
work.

### Checked-in source candidate extraction

`back-end/core/base_year_candidate_extraction.py` provides the narrow,
read-only adapter from the current priority-ranked source pool into the opt-in
generator. It separates the static package into a complete reviewed Current
Accounts template and a Reference/Target projection series. The template's
canonical key set is rebased to the requested year, then original candidates
are resolved against those keys. Projection rows remain separate and retain
only years after the requested base year. The adapter does not scan Drive,
archives, generated defaults, researcher submissions, or inactive specialist
folders.

The adapter keeps only original rows whose row year equals their structured
`Source Data Year`. Missing-year rows, shifted/projected rows and derived
variables are recorded in the extraction audit but cannot become candidates.
Known 9th Outlook bridge rows receive the documented 2022 source year and
archive guidance. Extraction can mark only the exact version-scoped lineage as
`verified_9th_outlook`, which makes it seed-eligible without misrepresenting it
as a native observation. If more than one ranked source supplies the same key
and source year, eligible native evidence is considered before verified legacy
evidence, then the existing source priority is applied. Conflicting values at
the same winning priority fail review-package generation.

Use `generate_checked_in_source_review_package()` with an explicit economy,
base year, source-package version, review package version and caller-owned
output directory. It writes three data components: the resolved Current
Accounts CSV, a separate projection-series CSV, and their sorted complete
package. It also writes the resolution audit/manifest, extracted candidate JSON
and candidate-extraction audit CSV. The manifest records every component's
filename, row count and SHA-256 checksum, including the Current Accounts
template source year and first retained projection year. The same protected-path
checks apply, and nothing is promoted or added to the static index.

Projection validation requires exactly Reference and Target with identical,
continuous coverage beginning in the year after the requested base year. It
rejects non-finite values and conflicting canonical duplicates. Identical
duplicate Stock Share rows collapse only when exactly one is the explicit
Stock-derived copy. An empty projection is allowed when the requested base year
is at the end of the available series. A requested 2021 package currently fails
clearly because the checked-in projections begin in 2023 and therefore cannot
supply 2022; the adapter does not invent the missing year.

The current static 20USA 2022 fallback contains five duplicate Stock Share
keys: each is an identical legacy copy paired with the explicit
`stock_share_from_stock` copy. The loader collapses only this exact case and
keeps the explicit derived row; conflicting values, non-Stock-Share duplicates,
or ambiguous derivation metadata fail. This normalisation changes neither the
unique canonical key set nor a retained numeric value.

A temporary 20USA/2022 run on 2026-08-28 inspected 81,127 ranked source rows.
Of 330 rows matching canonical fallback keys, 290 became candidates, 34 Stock
Share source rows were excluded and 6 rows lacked a source-data year. All 290
candidates retained legacy (non-native) classification but carried the verified,
version-scoped 9th Outlook lineage marker, so all 290 were selected. Another
212 rows used the authoritative Current Accounts template, including 29
detailed Stock Share rows, and the 5 explicitly marked vehicle-type Stock Share
rows were derived from Stock. The output had 507 unique canonical keys. This is
useful audit evidence for the narrow lineage rule, not an argument to broaden
eligibility to arbitrary legacy rows.

The checked-in 16RUS Current Accounts template is dated 2022. Russia provenance
is treated as complete enough for this workflow: preserve the recorded 2022
source year, do not attempt a separate 2021-versus-2022 research exercise, and use
`carried_backward` if that value is packaged for a 2021 base year. A complete
2021 review package still cannot be produced until the projection-series 2022
gap is resolved; this is a projection coverage limitation rather than an
outstanding provenance decision.

### Supplemental provenance inventory

Supplemental inputs remain in their existing files and loaders; they are not
resolver candidates and do not require routine reviewer approval.
`back-end/core/supplemental_provenance_inventory.py` reads only the seven active
supplemental paths declared in `road_module1_default_parameters.json` and
describes them using the same Source, Comment, Source Data Year, Source
Classification, Base Year Treatment and Derivation Method fields used by the
canonical package. Evidence grade and estimation status remain separate audit
fields and never imply a native observation.

`build_supplemental_provenance_inventory()` returns the deterministic inventory
and summary in memory. It writes a CSV only when given a caller-owned path
outside the protected data/default/static trees. The inventory stays separate
from candidate extraction and leaves every source value untouched.

Normal records are `tracked_complete`. Known source formats that intentionally
lack a year or evidence grade—currently the lifecycle-factor rows and the two
survival/vintage profile workbooks—are `tracked_metadata_limited` and do not
require review. These lifecycle inputs are recorded as ChatGPT-assisted APERC
model/derived assumptions whose original external evidence and source year are
unknown; they must not be presented as external observations. Only a missing
active file, unconfigured active source,
malformed schema/year/profile, missing record identity, or
duplicate/conflicting source identity becomes `attention_required`. A
2026-08-28 read-only inventory produced 73 records: 69
tracked complete, 4 tracked with limited metadata, and 0 requiring review.

### Staged review-package command

Operators can run the complete safe review workflow from the repository root:

```powershell
python back-end/scripts/generate_module1_review_package.py `
  --economy 20USA `
  --base-year 2022 `
  --package-version review_only_20USA_2022 `
  --output-dir C:\path\to\new_or_empty_staging_directory
```

The command extracts checked-in candidates, resolves a complete Current
Accounts template for the requested year, preserves the future Reference/Target
series separately, writes their validated combined package and audits, and
writes the separate supplemental provenance inventory. It then prints a JSON
summary. The output directory must be new or empty. Existing files are never
overwritten, protected data/default/static paths are refused, and the command
has no promotion or index-update operation.

To deliberately run the same staged workflow for every economy and include the
researcher-submission archive review in one operator action, use:

```powershell
python back-end/scripts/generate_module1_review_package.py `
  --all-economies `
  --base-year 2022 `
  --package-version review_only_all_2022 `
  --output-dir C:\path\to\new_or_empty_staging_directory `
  --include-researcher-submissions
```

The researcher-submission step is opt-in: omitting
`--include-researcher-submissions` makes no archive request. When included, it
uses the existing Google Drive archive credentials and
`ROAD_MODEL_SUBMISSIONS_DRIVE_FOLDER_ID`; an operator may instead pass
`--researcher-submissions-folder-id`. It downloads and validates archived
submission pairs into the staging directory, quarantines malformed pairs, and
produces review decisions and candidate overrides. It does not apply a
submission, modify Drive, promote a package, update the static index, or merge
researcher changes into the newly generated economy packages. Because the
staging directory is new, this combined run reviews all currently visible
archive pairs rather than continuing an older checkpoint.

Here `--base-year 2022` means “build the checked-in economy review packages for
model/output year 2022.” It does not assert that every researcher submission or
source observation was collected in 2022. Each Drive submission retains its
recorded version, economy, baseline checksum and source-year provenance and is
compared only with its exact immutable baseline. The combined
`review_run_summary.json` keeps the package results, supplemental inventory and
researcher-submission review result separate so a reviewer can decide what
deserves later promotion. Every economy is attempted independently. A malformed
economy does not prevent later economies from being staged, but it is recorded
under `economy_failures` and the command returns a nonzero exit code so partial
output cannot be mistaken for a complete build.

When strict generation finds conflicting duplicate source rows, the failed
economy's entry links two formula-safe quarantine artifacts. The primary
`*_source_conflict_review.csv` has one row per decision and only ten columns:
the canonical key, readable candidate options, reviewer choice, reviewer source
and reviewer reason. The separate `*_source_conflict_evidence.csv` retains every
underlying source/comment row for audit. Neither file applies a choice. A
reviewer should enter an authoritative value or correction, cite the supporting
source, and explain the reason; a later, separately approved source update is
still required. The failure entry records both SHA-256 checksums and the
group/evidence-row counts.

The 2026-08-28 conflict investigation found two deterministic static-build
defects. Compact codes such as `02BD` did not map to workbook token `02_BD`, so
five economies used an unfiltered ALL_ECONS Reference workbook. Static
Current Accounts construction also relabelled every source scenario before
checking disagreements. The loader now normalises both compact and underscored
tokens, filters workbook rows to the requested economy region, prefers genuine
Current Accounts rows for the Current Accounts template, and rejects ambiguous
fallback-scenario rows. Legacy canonical files with blank Source Data Year also
remain present through long-to-wide conversion rather than disappearing from a
pivot. These are build-code fixes only; the checked-in static bundle has not
been regenerated or activated.

## What the researcher interface should see

Researchers receive an already selected, validated package. Their editing
surface should show:

- value and units;
- a compact status: `Native 2024`, `From 2022`, `From 2026`, `Derived`,
  `Archived reference`, or `Source detail needed`;
- full provenance in expandable row details;
- a filter for shifted, missing or weak-source-detail values; and
- **Source / reason for change** when they edit.

Researchers should not see archive checkpoints, quarantine fingerprints,
baseline checksums, promotion candidates or source-priority controls. Until a
role-aware advanced surface exists, fallback strategies and per-variable
overrides belong in the model-manager/operator workflow.

## Startup and package discovery

The browser currently loads automatically:

```text
road-module1-static/index.json
  -> default version and economy list
  -> <version>/<economy>.csv
  -> browser working copy
```

It uses `cache: no-store`, sanitises version/economy path segments and reloads
on selection changes. It can offer a browser-local draft. However, the current
checked-in index lacks the newer per-economy base-year metadata and startup is
not connected to either the resolver or the opt-in backend generator.

The target is one deterministic lookup, not Drive discovery:

```text
index
  -> exact version + economy + requested base year
  -> validated resolution manifest
  -> checksum-identified resolved CSV
  -> browser working copy
```

The manifest should record economy, requested base year, source package,
strategy/overrides, CSV filename/checksum, generation time, and summary counts.
A saved draft should be offered only when its package checksum matches. The
browser must never scan Drive, choose the newest submission, merge sources or
run source-priority logic.

## Archive review and promotion

Changed researcher runs archive a complete canonical-long CSV plus matching
metadata JSON. Developer review remains offline. Archive pairs are untrusted
until schema, IDs, filenames, checksums, row counts and exact baseline are
validated. Invalid pairs are quarantined without blocking later valid ones.
Review tools never automatically modify Drive, sources, defaults, static files
or active overrides.

Approved changes update the owning source or a deliberate reviewed override,
then produce a new immutable dated version. Existing versions and submissions
remain unchanged.

See:

- [`researcher_change_review_and_promotion_guide.md`](researcher_change_review_and_promotion_guide.md)
- [`researcher_submission_drive_archive.md`](researcher_submission_drive_archive.md)
- [`researcher_submission_my_drive_oauth_draft.md`](researcher_submission_my_drive_oauth_draft.md)

## Simplicity guardrails

- One canonical-long boundary format.
- One global fallback strategy plus sparse variable overrides.
- No per-datapoint strategy controls initially.
- One manifest-selected package at startup.
- Rich provenance internally; compact status and details-on-demand for users.
- Researcher entry, model-manager setup and developer review stay separate.
- No Drive discovery or promotion in the browser.
- No generated output becomes an input candidate.
- Unknown variables, duplicate keys and malformed metadata fail before build.
- Weak source detail remains visible; it is never silently upgraded to a
  confident classification.

## Guidance for AI assistants

Before changing this pipeline:

1. Identify the role and authoritative layer being changed.
2. Read this guide and the specialist guide for that layer.
3. Preserve original source year/classification through every conversion.
4. Do not edit generated static packages as source data.
5. Do not expose developer review controls in the researcher interface.
6. Use synthetic/temp data and fake Drive responses in tests.
7. Stop for a human decision before changing fallback defaults, classification
   eligibility, archive failure policy, retention, sharing, or promotion.

## Related guides

- [`../back-end/data/road_model/UPDATE_METHOD.md`](../back-end/data/road_model/UPDATE_METHOD.md)
- [`../back-end/data/road_model/README.md`](../back-end/data/road_model/README.md)
- [`new model/multinode_road_module1_repo_guide.md`](new%20model/multinode_road_module1_repo_guide.md)
- [`researcher_change_review_and_promotion_guide.md`](researcher_change_review_and_promotion_guide.md)
- [`researcher_submission_drive_archive.md`](researcher_submission_drive_archive.md)
