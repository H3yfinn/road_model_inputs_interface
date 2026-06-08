# Manually Filled Rows

This folder contributes rows to the **source merge** step of the build alongside
`processed_source/` and `supplemental_source_files/`. All three folders are
priority-ranked together; the row with the lowest numeric priority wins when the
same key appears in more than one source.

## Files

| File | Purpose |
|---|---|
| `model_assumption_defaults.csv` | APEC-wide defaults for model-assumption rows (`Passenger Stock Growth Rate Adjustment`, `Freight GDP Elasticity Adjustment`). Priority 50 — lower than processed source (10), so an economy-specific row in processed source will override it. |
| `manually_entered_missing_rows.csv` | Auto-generated rows from LEAP coverage diagnostics. `Value` is left blank until filled manually. Priority 100 — lowest priority fallback. |

## Schema

All files in this folder use the same schema:

- `Economy`
- `Branch Path`
- `Variable`
- `Scenario`
- `Year`
- `Value`
- `Units`
- `notes`
- `DO_NOT_USE`
- `share_decreased_from` *(optional)* — for `Sales Share` / `Stock Share` rows, name the sibling branch that should absorb the introduced value. Can be a short leaf name (e.g. `ICE`) or a full branch path. If blank, sibling shares are **not** adjusted automatically.

Rows with a blank `Value` are ignored by the loader. Rows with `DO_NOT_USE` set
to `1`, `true`, `yes`, `y`, `x`, or `do not use` are also skipped.

## Priority

Priority is controlled by `../road_module1_source_priorities.csv`. Lower numeric
priority wins. The current priorities are:

| File | Priority | Notes |
|---|---|---|
| `processed_source/*` | 10 | Wins by default |
| `model_assumption_defaults.csv` | 50 | APEC-wide fallback; override by adding the row to processed source |
| `manually_entered_missing_rows.csv` | 100 | Last resort; only used when no other source has the row |

`final_value_overrides/` applies after all source merge steps regardless of priority.
