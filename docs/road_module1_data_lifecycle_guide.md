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
3. For a proven 9th Outlook lineage with no source year, use 2022 and retain
   `legacy_unknown` unless a source supplied a more specific classification.
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

`Stock Share` is marked as derived from resolved `Stock`. Projected stock-share
seeds, generated mileage/fuel-economy correction factors, specialist replacement
sales shares, and scenario clones retain distinct derivation methods. Supplemental
inputs propagate an explicit four-digit `data_year` through `Source Data Year`;
their evidence grade or estimation status is not silently upgraded to a native
classification.

`audit_module1_source_quality()` reports total, complete, legacy-detail-needed,
derived/generated, missing-date, and missing-classification counts in memory. It
writes a CSV only when the caller supplies an output path; production artifacts
are never an implicit side effect.

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

No bulk provenance-recovery or row-by-row crosswalk is planned. The current
legacy records should remain as they are and be replaced gradually when better
sources are supplied through normal reviewed updates. If a particular legacy
value ever needs investigation, use the archived transport data system and its
full source key on demand. That targeted lookup is expected to require much less
work than pre-emptively sourcing every historic row.

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

This audit predates discovery of the archived transport data system described
above. Its `legacy_unknown` and `legacy detail needed` counts remain accurate for
the structured fields in that generated package, but should now be interpreted
as **archived detail not yet recovered into the package** for proven 9th Outlook
rows. The discovery does not retroactively make transformed rows external
observations or alter the recorded source year.

## Base-year resolution

Resolution starts from original candidates, never a previously shifted output.
Current Module 1 policies are simple:

- 23 original source/researcher/model-judgement variables are `seed_eligible`;
- `Stock Share` is derived from resolved `Stock`;
- ESTO energy balances are external exact-year reconciliation anchors.

An exact-year eligible observation wins. Otherwise the selected fallback keeps
its real source-data year and is marked `carried_forward` (earlier source) or
`carried_backward` (future source).

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
`Stock Share` candidates are rejected and the output shares are recalculated
from resolved `Stock` rows. Candidate IDs must be package-wide unique, and a
candidate labelled shifted/generated—or a payload whose year differs from its
source year—fails validation so generated output cannot be recycled as input.

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
discovery, `closest_available`, additional eligibility, and conversion of the
existing processed sources into candidate records remain separately reviewed
work.

## What the researcher interface should see

Researchers receive an already selected, validated package. Their editing
surface should show:

- value and units;
- a compact status: `Native 2024`, `From 2022`, `From 2026`, `Derived`, or
  `Source detail needed`;
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
