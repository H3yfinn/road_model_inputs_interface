# Road Module 1 Static Bundle

This folder is the packaged local-data source for static/client-side deployments.

## Required files

- `index.json`
  - contains available `versions`, `economies`, and `default_version`.

- defaults JSON files by version/economy, for example:
  - `v2026_05_25_best_guess/20USA.json`

The scenario is fixed to `Current Accounts` in the loaded rows.

## Defaults file schema

Each defaults file should look like:

```json
{
  "key_columns": ["Branch Path", "Variable", "Scenario", "Region"],
  "rows": [
    {
      "Branch Path": "Demand\\Passenger road\\LPVs\\ICE medium",
      "Variable": "Sales Share",
      "Scenario": "Current Accounts",
      "Region": "United States",
      "Scale": "%",
      "Units": "Share",
      "Per...": "",
      "2022": 18
    }
  ]
}
```

## Optional backend mode

Static mode is the default. Optional backend fallback helpers are only used when enabled explicitly, for example:

- `?roadBackend=1`

You can disable again with:

- `?roadBackend=0`
