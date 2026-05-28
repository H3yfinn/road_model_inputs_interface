import os
from pydantic import BaseModel

class AppSettings(BaseModel):
    """
    Centralized configuration for the application.
    Reads from environment variables or falls back to default values.
    """
    # Application settings
    api_title: str = "Multinode Energy Modeler API"
    api_version: str = "1.0.0"
    
    # File paths (Updated to match what routers.py expects)
    db_path: str = os.getenv("DB_PATH", "data/multinodeenergy_backend/00APEC_2024_low_with_subtotals.csv")
    mapping_path: str = os.getenv("MAPPING_PATH", "data/multinodeenergy_backend/sector_fuel_codes_to_names 1.xlsx - code_to_name.csv")
    output_dir: str = os.getenv("OUTPUT_DIR", "output")
    
    # Optimization parameters (Retained for backward compatibility if needed)
    optimizer_maxiter: int = int(os.getenv("OPTIMIZER_MAXITER", 2000))
    optimizer_ftol: float = float(os.getenv("OPTIMIZER_FTOL", 1e-6))

# Instantiate the settings to be imported across the app
settings = AppSettings()