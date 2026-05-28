from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

# ---------------------------------------------------------
# Core Domain Models
# ---------------------------------------------------------
class MacroDrivers(BaseModel):
    households: float = Field(..., description="Total number of households", gt=0)
    floor_area_sqm: float = Field(..., description="Total floor area in square meters", gt=0)
    occupancy_rate: float = Field(..., description="Average persons per household", gt=0)

class FuelAssignment(BaseModel):
    """Represents a specific fuel assigned to a leaf node."""
    name: str = Field(..., description="Must match the APEC DB product string")
    weight: float = Field(..., description="Relative weight of this fuel", ge=0.0)
    efficiency: float = Field(default=1.0, description="Transformation efficiency (eta)", gt=0.0)

class CalculatedFuel(FuelAssignment):
    """Extends assignment with calculated physical values."""
    normalized_weight: float = Field(..., description="Proportional share among sibling fuels")
    allocated_energy: float = Field(..., description="Top-down physical energy (Mass balance)")
    effective_energy: float = Field(..., description="Energy delivered after applying efficiency (eta)")

class WeightNode(BaseModel):
    weight: float = Field(..., description="Raw bottom-up weight", ge=0.0)
    min_weight: Optional[float] = Field(default=None, description="Optional lower bound weight constraint for optimization", ge=0.0, le=1.0)
    max_weight: Optional[float] = Field(default=None, description="Optional upper bound weight constraint for optimization", ge=0.0, le=1.0)
    macro_driver: Optional[str] = None
    tags: Optional[List[str]] = Field(default=None, description="Metadata tags for special node handling")
    children: Optional[Dict[str, 'WeightNode']] = None
    fuels: Optional[List[FuelAssignment]] = Field(default=None, description="Fuels assigned at the leaf node")

class CalculatedNode(BaseModel):
    weight: float
    normalized_weight: float
    min_weight: Optional[float] = Field(default=None, description="Optional lower bound weight constraint")
    max_weight: Optional[float] = Field(default=None, description="Optional upper bound weight constraint")
    macro_driver: Optional[str] = None
    tags: Optional[List[str]] = None
    allocated_energy: float = Field(..., description="Top-down physical energy allocated to this node")
    children: Optional[Dict[str, 'CalculatedNode']] = None
    fuels: Optional[List[CalculatedFuel]] = None


# ---------------------------------------------------------
# API Request/Response Payloads
# ---------------------------------------------------------
class InitializationRequest(BaseModel):
    """Payload to initialize the tree and fetch the macro total."""
    economy: str = Field(..., description="Economy code or identifier (e.g., '01_AUS')")
    year: int = Field(..., description="Year of the simulation")
    sector_flow: str = Field(..., description="Target sector mapped to the 'flows' column in the DB")

class InitializationResponse(BaseModel):
    """Response returning the top-down total energy for the selected flow."""
    economy: str
    year: int
    sector_flow: str
    total_energy: float = Field(..., description="Total top-down energy for the requested sector")
    message: str

class TreeLayerUpdatePayload(BaseModel):
    """Payload for submitting a tree for balancing, validation, or optimization."""
    economy: str
    year: int
    sector_flow: str
    total_energy: float = Field(..., description="The macro total retrieved in Stage 1")
    target_layer: str = Field(..., description="Identifier for the current stage (e.g., 'full_tree')")
    tree_state: Dict[str, WeightNode] = Field(..., description="The hierarchical tree state")

class LayerUpdateResponse(BaseModel):
    """Standardized response after calculating, validating, or optimizing a tree."""
    status: str = Field(..., description="Execution status, e.g., 'success', 'validation_error'")
    message: str
    balanced_tree: Dict[str, CalculatedNode] = Field(..., description="The newly balanced tree populated with calculated energy values")
    validation_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed breakdown of macro imbalances")

class UserVariable(BaseModel):
    """A researcher-defined variable to be included in the export workbook."""
    name: str = Field(..., description="Snake_case key identifier (e.g. 'scrappage_rate_2030')")
    display_name: str = Field(..., description="Human-readable label shown in the output sheet")
    value: float = Field(..., description="Numeric value")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g. '%', 'vehicles/yr')")
    description: Optional[str] = Field(default=None, description="What this variable represents")
    category: Optional[str] = Field(default=None, description="Grouping category (e.g. 'Scrappage', 'Fleet Turnover')")


class ExportRequest(BaseModel):
    """Payload to trigger the final Excel generation."""
    economy: str
    year: int
    sector_flow: str
    macro_drivers: MacroDrivers = Field(..., description="The macroeconomic values for intensity calculations")
    balanced_tree: Dict[str, CalculatedNode] = Field(..., description="The fully built, validated, and balanced energy tree")
    user_variables: Optional[List[UserVariable]] = Field(default_factory=list, description="Researcher-defined variables appended as a dedicated sheet")

class ExportResponse(BaseModel):
    """Response details for a successful LEAP export."""
    status: str
    leap_export_path: str = Field(..., description="File path to the generated LEAP Excel workbook")
    message: str


class RoadModule1Override(BaseModel):
    """Single researcher override keyed by the LEAP-like Road model key columns."""
    key: Dict[str, Any]
    year: int | str
    value: Optional[float] = None
    comment: Optional[str] = ""


class RoadModule1ResearcherOutputRequest(BaseModel):
    version: str
    economy: str
    overrides: List[RoadModule1Override] = Field(default_factory=list)


class RoadModule1ResearcherOutputResponse(BaseModel):
    status: str
    completed_inputs_path: str
    rows_written: int
    overrides_applied: int
    override_issue_count: int
    structure_validation_passed: bool
    message: str
