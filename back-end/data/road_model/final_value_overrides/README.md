# Final Value Overrides

Put optional per-economy final override spreadsheets here.

Accepted filenames:

- `module1_final_value_overrides_<ECONOMY>.csv`
- `module1_final_value_overrides_<ECONOMY>.xlsx`

Example:

- `module1_final_value_overrides_20USA.csv`

Required columns:

- `Branch Path`
- `Variable`
- `Scenario`
- `Year`
- `Value`
- `Units`
- `share_decreased_from`

Optional column:

- `Region`

These files are applied after all normal sources have run, including:

- `processed_source/road_module1_source_<ECONOMY>.csv`
- supplemental source CSV/XLSX files
- survival and vintage profile overlays
- derived vehicle-type `Stock Share` rows

Override rows must match an existing generated row by `Branch Path`, `Variable`,
`Scenario`, and `Year`.

For `Sales Share` and `Stock Share`, sibling rows are checked so the group sums
to 100. The sibling group is the same parent `Branch Path`, same `Variable`,
same `Scenario`, and same `Year`.

If the new share breaks the 100 total, set `share_decreased_from` to the sibling
branch that should absorb the difference. This can be a full branch path or just
the sibling name.

Example:

```csv
Branch Path,Variable,Scenario,Year,Value,Units,share_decreased_from
Demand\Passenger road\LPVs\HEV large,Sales Share,Target,2022,12.5,Share,Demand\Passenger road\LPVs\ICE large
```

Leave `share_decreased_from` blank to normalize all siblings in that group.

When defaults are generated, any active override file writes two visibility
outputs in the economy output folder:

- `road_module1_final_value_override_report.csv`
- `road_module1_final_value_override_report.html`

Open the HTML file in a browser to see simple before/after bar charts for each
direct override and any share-balancing adjustment.
