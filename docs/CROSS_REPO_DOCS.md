# Cross-repository docs references

This repository is designed to be worked on alongside `../leap_road_model`.

## Key docs in `leap_road_model`

- `..\..\leap_road_model\docs\new model\road_transport_model_detailed.md`
- `..\..\leap_road_model\docs\new model\road_transport_model_simplified.md`
- `..\..\leap_road_model\docs\pending_changes.md` — running list of what is still to do
- `..\..\leap_road_model\docs\new model\transition_audit_report.md` — historical migration context only

## Working convention

- Keep both repos open in one multi-root VS Code workspace.
- Treat docs in both repos as one shared design corpus.
- Prefer source-data contracts in `road_model_inputs_interface/back-end/data/road_model` and avoid manual assumptions files.
