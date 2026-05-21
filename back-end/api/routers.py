from fastapi import APIRouter
from typing import Dict, Any

from config.settings import settings
from core.data_ingestion import APECDataIngestor
from core.tree_components import Tree
from core.optimization_engine import OptimizationEngine
from core.leap_exporter import LEAPExporter
from core.logger import get_logger

from api.schemas import (
    InitializationRequest, InitializationResponse,
    TreeLayerUpdatePayload, LayerUpdateResponse,
    ExportRequest, ExportResponse
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/energy-model", tags=["Interactive Modeling"])

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
    
    exporter = LEAPExporter(tree, payload.economy, payload.year, payload.sector_flow, payload.macro_drivers)
    filepath = exporter.generate() 

    return ExportResponse(
        status="success",
        leap_export_path=filepath,
        message="LEAP export generated successfully."
    )