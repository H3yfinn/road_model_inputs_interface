# Road Model data contract v1 (simple split)

## Intent

Keep model **structure** in JSON-like contract files, and keep all **numeric operational values** in CSV/XLSX source files under:

`back-end/data/road_model/`

This keeps runtime code clean and makes data updates traceable.

## Two-layer contract

### 1) Control plane (structure, enums, schema) — JSON

Allowed in JSON:

- economy identifiers and display names
- variable names and canonical aliases
- required dataset/table names
- required column names and key columns
- allowed units and categorical values
- branch/path taxonomy mappings and labels
- scenario names and scope flags

Not allowed in this JSON layer:

- operational numeric defaults used by the model runtime
- numeric assumptions for reconciliation, mileage, efficiency, saturation, etc.

### 2) Data plane (operational numeric values) — CSV/XLSX

Required source-of-truth location:

- `back-end/data/road_model/*.csv`
- `back-end/data/road_model/*.xlsx` / `*.xls`

Examples of numeric content that must live here:

- reconciliation bounds/weights
- PHEV utilisation values
- vehicle equivalent weights
- passenger saturation values
- mileage/efficiency/base-year values

## Update method requirement

Every numeric source update should include a recorded method with:

- data source(s)
- transformation steps
- script/notebook path used to generate outputs
- date, author, and version tag
- validation checks performed

Recommended location for this record:

- `back-end/data/road_model/UPDATE_METHOD.md` > todo note that this whoole update method hasnt been built yet. We will slowly build it up and may have to move it to a new system. But i do think this si the best wya to handle transprot input data updates for mow... usingf a script by scirpt approach, with no expectations of reusability across scripts, but with a consistent record-keeping format for each update. This is the best way to ensure that we have a clear audit trail for all numeric data updates, while not requriing too much system design, which is crucial for transparency, reproducibility and appraochability in the tranprot model. > to start i think maybe i could build some script to process the outptu from leap_transport, whichy is almost all ready bnut needs a few recategorisations anmd mappings to fit the road model structure. I can record the method for that script in the UPDATE_METHOD.md file, and then we have a clear record of how the leap_transport outputs which was built to map the 9th edition transport outputs to the leap strucutrre, are transformed into the new road model inputs. This also allows us to iterate on the script and the mappings as needed, while keeping a clear history of changes and their rationale. it also makes it so we dont need to use the leap_tranprot repo and instead can treat it as reocrd. In the future someojne may want to then build a method to rpelace certain data points in that leap_transport output with more up-to-date or accurate data from other sources, and they can also record that method in the UPDATE_METHOD.md file... but in genral i do expect that leap_transport outptu to remain a key source for the road model numeric inputs, at least for the initial version, so having a clear method record for how that output is processed into road model inputs is crucial. Overall, this approach allows us to maintain a clear and detailed record of all numeric data updates, which is essential for transparency, reproducibility and accountability in the road model development process. It also allows us to track the provenance of all numeric data used in the model, which is important for understanding the assumptions and limitations of the model outputs.

## Near-term generation path

When ready, generate `back-end/data/road_model/leap_import_workbooks/*` from methods in `../leap_transport/`.

That generation path becomes the preferred producer for numeric workbooks, while this repo remains the consumer/validator. > todo as epxlained in docs\new model\multinode_road_module1_repo_guide.md, not sure whgat wer will do about any generation of internmmediate data between the input data and the data shown in the UI. I think the strong reason for intermediatie data creatioin is verification and validation of the data, so maybe we can have a process where we generate intermediate data files in the same `back-end/data/road_model/` folder, or it can go somehwere that is more typicak for the data served to the UI, with clear naming conventions to indicate that they are intermediate files, perhaps even by putting them in a subfolder. then those are the files that re used by the final UI. This can include verification and validation steps. 

## CI/audit behavior (target)

- pass if structure JSON files are schema-only and numeric source files exist
- fail if runtime code embeds operational numeric tables
- fail if numeric assumptions are introduced into structure JSON files
- fail if update-method record is missing for changed numeric source files
