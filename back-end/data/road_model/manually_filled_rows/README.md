# Manually Filled Rows

`manually_entered_missing_rows.csv` is automatically updated from LEAP row
coverage diagnostics produced by `leap_road_model`.

Rows are all-economy and use this schema:

- `Economy`
- `Branch Path`
- `Variable`
- `Scenario`
- `Year`
- `Value`
- `Units`
- `notes`
- `DO_NOT_USE`

Automatically added rows leave `Value` blank. Blank values are ignored by the
Road Module 1 loader, so these rows are not used until a value is entered.
Rows with `DO_NOT_USE` set to `1`, `true`, `yes`, `y`, `x`, or `do not use`
are skipped even if `Value` is filled.

Priority is controlled by `../road_module1_source_priorities.csv`. The
`manual_missing_rows` source is set to `-1`, which the loader treats as a
fallback priority below positive priorities. More negative values are even lower
priority, so `-2` loses to `-1`, `-3` loses to `-2`, and so on.
`final_value_overrides` still apply after this priority resolution step.
