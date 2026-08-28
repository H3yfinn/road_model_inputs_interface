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

Do not invent a citation. Use:

```text
Legacy input — original source detail not yet recorded; please update when better evidence is available.
```

Use `9th Outlook input — ...` only where repository evidence establishes that
lineage. Keep incomplete legacy classification as `legacy_unknown`.

### Derived or generated value

Record the derivation, not a fictitious external source. For example, `Stock
Share` is derived from resolved `Stock`; preserve the upstream source and
derivation method.

### Researcher change

The note should include the dataset/document, source year, link/reference where
available, and why the value changed. Missing detail remains a non-blocking run
warning and is visible to the developer reviewer.

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

- `prefer_earlier`: latest earlier, then earliest future;
- `closest_available`: smallest year distance, with earlier winning a tie.

Use one global strategy plus sparse per-variable overrides. Store them in the
generated manifest/audit, not in approved source/default data.

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
not yet connected to the resolver.

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
