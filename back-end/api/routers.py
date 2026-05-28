from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from typing import Dict, Any
from io import BytesIO
import math
import pandas as pd

from config.settings import settings
from core.data_ingestion import APECDataIngestor
from core.tree_components import Tree
from core.optimization_engine import OptimizationEngine
from core.leap_exporter import LEAPExporter
from core.logger import get_logger
from core.road_module1_defaults import (
    DEFAULT_VERSION,
    MODULE1_KEY_COLUMNS,
    ROAD_MODULE1_RESEARCHER_OUTPUT_ROOT,
    apply_provided_values_file,
    get_default_input_workbook_path,
    get_default_filled_inputs_path,
    load_builtin_transport_leap_provided_values,
    list_default_versions,
    list_default_economies,
    load_default_filled_inputs,
    write_researcher_completed_package,
)

from api.schemas import (
    InitializationRequest, InitializationResponse,
    TreeLayerUpdatePayload, LayerUpdateResponse,
    ExportRequest, ExportResponse,
    UserVariable,
    RoadModule1ResearcherOutputRequest, RoadModule1ResearcherOutputResponse
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/energy-model", tags=["Interactive Modeling"])
# Road Module 1 routes are optional local backend tooling.
# Static/client-side-first deployments can run Road Module 1 upload/validation/export in-browser.
road_router = APIRouter(prefix="/api/v1/road-module1", tags=["Road model"])

# Instantiate the DB Ingestor
data_ingestor = APECDataIngestor(filepath=settings.db_path, code_to_name_path=settings.mapping_path)


# ==========================================
# 1. Initialization & Metadata
# ==========================================
@router.post("/initialize", response_model=InitializationResponse)
def initialize_tree(payload: InitializationRequest):
    """Fetches the top-down macroeconomic total to seed the root of the tree."""
    e_total = data_ingestor.get_total_energy(payload.economy, payload.year, payload.sector_flow)
    return InitializationResponse(
        economy=payload.economy,
        year=payload.year,
        sector_flow=payload.sector_flow,
        total_energy=e_total,
        message="Successfully initialized macro energy target."
    )

@router.get("/metadata/active_fuels")
def get_active_fuels(economy: str, year: int, sector_flow: str):
    """Retrieves the valid non-zero fuels up to prefix 17 for a specific flow."""
    active_fuels = data_ingestor.get_active_fuels(economy, year, sector_flow)
    return {
        "economy": economy,
        "year": year,
        "sector_flow": sector_flow,
        "active_fuels": active_fuels
    }


# ==========================================
# 2. Validation Engine
# ==========================================
@router.post("/validate_tree", response_model=LayerUpdateResponse)
def validate_tree(payload: TreeLayerUpdatePayload):
    """
    Performs a forward pass on the user's manual weights.
    Strictly checks the bottom-up fuel aggregates against the top-down ESTO targets.
    """
    # 1. Build the Tree
    tree = Tree()
    tree.build_from_state(payload.tree_state)
    
    # 2. Fetch Macro Limits and Validate
    macro_targets = data_ingestor.get_active_fuels(payload.economy, payload.year, payload.sector_flow)
    engine = OptimizationEngine(top_down_total=payload.total_energy)
    
    validation_report = engine.calculate_imbalances(tree, macro_targets)

    status = "success" if validation_report["is_valid"] else "validation_error"
    msg = "Tree is perfectly balanced." if validation_report["is_valid"] else "Energy imbalances detected."

    return LayerUpdateResponse(
        status=status,
        message=msg,
        balanced_tree=tree.to_calculated_schema(),
        validation_details=validation_report
    )


# ==========================================
# 3. Mathematical Optimization Engine
# ==========================================
@router.post("/optimize_tree", response_model=LayerUpdateResponse)
def optimize_tree(payload: TreeLayerUpdatePayload):
    """
    Runs the SLSQP algorithm to mathematically adjust all relative weights in the tree,
    forcing the physical fuel sums to perfectly match the ESTO targets.
    """
    # 1. Build the Tree
    tree = Tree()
    tree.build_from_state(payload.tree_state)
    
    # 2. Fetch Macro Targets & Run Optimizer
    macro_targets = data_ingestor.get_active_fuels(payload.economy, payload.year, payload.sector_flow)
    engine = OptimizationEngine(top_down_total=payload.total_energy)
    
    optimized_tree, success, msg = engine.optimize_weights(tree, macro_targets)

    # Changed from ValueError to RuntimeError to correctly trigger the 422 global exception handler
    if not success:
        raise RuntimeError(f"Optimizer failed to converge: {msg}")

    # 3. Generate the final validation report post-optimization to confirm 0.0000 imbalances
    validation_report = engine.calculate_imbalances(optimized_tree, macro_targets)

    return LayerUpdateResponse(
        status="success",
        message="Tree successfully optimized. Imbalances eliminated.",
        balanced_tree=optimized_tree.to_calculated_schema(),
        validation_details=validation_report
    )


# ==========================================
# 4. LEAP Export
# ==========================================
@router.post("/export", response_model=ExportResponse)
def export_to_leap(payload: ExportRequest):
    """Triggers the final Excel generation using the fully built and validated tree."""
    tree = Tree()
    tree.build_from_state(payload.balanced_tree)
    
    exporter = LEAPExporter(
        tree,
        payload.economy,
        payload.year,
        payload.sector_flow,
        payload.macro_drivers,
        user_variables=payload.user_variables or [],
    )
    filepath = exporter.generate()

    return ExportResponse(
        status="success",
        leap_export_path=filepath,
        message="LEAP export generated successfully."
    )


def _clean_json_value(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


@road_router.get("/versions")
def get_road_module1_versions():
    versions = list_default_versions()
    if not versions:
        versions = [DEFAULT_VERSION]
    return {"versions": versions, "default_version": versions[-1]}


@road_router.get("/economies")
def get_road_module1_economies(version: str = DEFAULT_VERSION):
    return {
        "version": version,
        "economies": list_default_economies(version=version),
    }


@road_router.get("/defaults")
def get_road_module1_defaults(
    economy: str,
    version: str = DEFAULT_VERSION,
    scenario: str | None = None,
):
    defaults_df = load_default_filled_inputs(economy=economy, version=version)
    if scenario:
        defaults_df = defaults_df[defaults_df["Scenario"] == scenario].copy()

    rows = []
    for record in defaults_df.to_dict(orient="records"):
        rows.append({key: _clean_json_value(value) for key, value in record.items()})

    return {
        "version": version,
        "economy": economy,
        "key_columns": MODULE1_KEY_COLUMNS,
        "rows": rows,
    }


@road_router.get("/provided_values_template")
def download_road_module1_provided_values_template(
    economy: str,
    version: str = DEFAULT_VERSION,
):
    filepath = get_default_input_workbook_path(economy=economy, version=version)
    if not filepath.exists():
        filepath = get_default_filled_inputs_path(economy=economy, version=version)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Provided-values template not found: {filepath}")

    is_workbook = filepath.suffix.lower() in {".xlsx", ".xls"}

    return FileResponse(
        path=filepath,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if is_workbook
            else "text/csv"
        ),
        filename=f"{economy}_{version}_road_module1_provided_values_template{filepath.suffix}",
    )


@road_router.get("/builtin_provided_values")
def get_road_module1_builtin_provided_values(
    economy: str,
    version: str = DEFAULT_VERSION,
    scenario: str | None = None,
):
    overlaid_df, overlay_report, workbook_path = load_builtin_transport_leap_provided_values(
        economy=economy,
        version=version,
    )
    if scenario:
        overlaid_df = overlaid_df[overlaid_df["Scenario"] == scenario].copy()

    rows = []
    for record in overlaid_df.to_dict(orient="records"):
        rows.append({key: _clean_json_value(value) for key, value in record.items()})

    return {
        "version": version,
        "economy": economy,
        "key_columns": MODULE1_KEY_COLUMNS,
        "rows": rows,
        "provided_file_name": workbook_path.name if workbook_path else "",
        "provided_values_applied": int(overlay_report["status"].eq("applied").sum()) if not overlay_report.empty else 0,
        "provided_value_issues": int(overlay_report["status"].eq("fail").sum()) if not overlay_report.empty else 0,
    }


@road_router.post("/provided_values")
async def upload_road_module1_provided_values(
    file: UploadFile = File(...),
    economy: str = Form(...),
    version: str = Form(DEFAULT_VERSION),
    scenario: str | None = Form(None),
):
    default_filled_df = load_default_filled_inputs(economy=economy, version=version)
    file_bytes = await file.read()
    filename = file.filename or "uploaded_provided_values_file"
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    try:
        if suffix == "csv":
            provided_df = pd.read_csv(BytesIO(file_bytes))
        elif suffix in {"xlsx", "xls"}:
            with pd.ExcelFile(BytesIO(file_bytes)) as workbook:
                preferred_sheet = "Details" if "Details" in workbook.sheet_names else (
                    "Data" if "Data" in workbook.sheet_names else workbook.sheet_names[0]
                )
                provided_df = pd.read_excel(workbook, sheet_name=preferred_sheet)
        else:
            raise ValueError("Use a CSV or Excel file with the same columns as the Road model provided-values file.")

        overlaid_df, overlay_report = apply_provided_values_file(
            default_filled_df=default_filled_df,
            provided_df=provided_df,
            source_name=filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read provided values file: {exc}") from exc

    if scenario:
        overlaid_df = overlaid_df[overlaid_df["Scenario"] == scenario].copy()

    rows = []
    for record in overlaid_df.to_dict(orient="records"):
        rows.append({key: _clean_json_value(value) for key, value in record.items()})

    return {
        "version": version,
        "economy": economy,
        "key_columns": MODULE1_KEY_COLUMNS,
        "rows": rows,
        "provided_file_name": filename,
        "provided_values_applied": int(overlay_report["status"].eq("applied").sum()) if not overlay_report.empty else 0,
        "provided_value_issues": int(overlay_report["status"].eq("fail").sum()) if not overlay_report.empty else 0,
    }


@road_router.post("/researcher_output", response_model=RoadModule1ResearcherOutputResponse)
def save_road_module1_researcher_output(payload: RoadModule1ResearcherOutputRequest):
    result = write_researcher_completed_package(
        economy=payload.economy,
        version=payload.version,
        overrides=[override.dict() for override in payload.overrides],
    )
    return RoadModule1ResearcherOutputResponse(
        **result,
        message=(
            "Researcher output saved and structure validation passed."
            if result["status"] == "success"
            else "Researcher output saved, but validation issues were found."
        ),
    )


@road_router.get("/researcher_output_file")
def download_road_module1_researcher_output_file(version: str = DEFAULT_VERSION, economy: str = ""):
    output_root = ROAD_MODULE1_RESEARCHER_OUTPUT_ROOT.resolve()
    output_dir = (output_root / version / economy).resolve()
    if not economy:
        raise HTTPException(status_code=400, detail="Economy is required.")
    if not output_dir.exists() or not output_dir.is_dir():
        raise HTTPException(status_code=404, detail="Researcher output has not been exported for this selection yet.")
    if not output_dir.is_relative_to(output_root):
        raise HTTPException(status_code=400, detail="Invalid researcher output path.")

    workbook_path = output_dir / f"road_module1_inputs_{economy}.xlsx"
    if not workbook_path.exists():
        raise HTTPException(status_code=404, detail="Researcher output workbook was not found for this selection.")

    return FileResponse(
        path=workbook_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=workbook_path.name,
    )
