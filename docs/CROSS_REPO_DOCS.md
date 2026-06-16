# Cross-repository docs references

This repository is designed to be worked on alongside `../leap_road_model`.

## Contents

1. [Key docs in `leap_road_model`](#key-docs-in-leap_road_model)
2. [Working convention](#working-convention)

## Key docs in `leap_road_model`

- `..\..\leap_road_model\docs\new model\road_transport_model_modeller_guide.md`
- `..\..\leap_road_model\docs\new model\road_transport_model_methodology.md`
- `..\..\leap_road_model\docs\pending_changes.md` — running list of what is still to do
- `..\..\leap_road_model\docs\new model\transition_audit_report.md` — historical migration context only

## Working convention

- Keep both repos open in one multi-root VS Code workspace.
- Treat docs in both repos as one shared design corpus.
- Prefer source-data contracts in `road_model_inputs_interface/back-end/data/road_model` and avoid manual assumptions files.
