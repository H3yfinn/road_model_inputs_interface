from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_VERSION = "v2026_05_25_best_guess"
SOURCE_DATE = "2026-05-25"
BASE_YEAR = 2022
DEFAULT_SCENARIOS = ["current_accounts"]
DEFAULT_YEARS = [2022]
YEAR_COLUMNS = [str(year) for year in DEFAULT_YEARS]
TRANSPORT_LEAP_EXPORT_ALL_ECONS_PATTERN = "transport_leap_export_combined_ALL_ECONS*.xlsx"
TRANSPORT_LEAP_EXPORT_FALLBACK_FILENAME = "transport_leap_export_combined_00_APEC_domestic_international_Target_20260514.xlsx"
TRANSPORT_LEAP_EXPORT_SHEET = "FOR_VIEWING"
TRANSPORT_LEAP_EXPORT_HEADER_ROW = 2
TRANSPORT_LEAP_EXPORT_SCENARIO_PRIORITY = ["Reference", "Target"]
TRANSPORT_LEAP_EXPORT_APEC_FALLBACK_VARIABLES = {
    "Sales Share",
    "Stock Share",
    "Device Share",
    "Mileage",
    "Average Mileage",
    "Final On-Road Fuel Economy",
    "Final On-Road Mileage",
    "Fuel Economy",
}
BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DATA_ROOT = BACKEND_ROOT / "data"
MULTINODE_BACKEND_DATA_DIR = DATA_ROOT / "multinodeenergy_backend"
ROAD_MODEL_DATA_DIR = DATA_ROOT / "road_model"
TRANSPORT_LEAP_EXPORT_DIR = ROAD_MODEL_DATA_DIR / "leap_import_workbooks"
ROAD_MODULE1_DEFAULTS_OUTPUT_ROOT = BACKEND_ROOT / "outputs" / "road_module1_defaults"
ROAD_MODULE1_RESEARCHER_OUTPUT_ROOT = BACKEND_ROOT / "outputs" / "road_module1_researcher_outputs"
ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH = ROAD_MODEL_DATA_DIR / "road_model_default_input_workbook.xlsx"
ROAD_MODEL_DEFAULT_INPUT_SHEET = "road_model_default_inputs"
ROAD_MODEL_PHEV_UTILISATION_SHEET = "phev_utilisation_source"
PHEV_UTILISATION_SOURCE_CSV = ROAD_MODEL_DATA_DIR / "apec_phev_utilisation_rates.csv"
PASSENGER_SATURATION_SOURCE_CSV = ROAD_MODEL_DATA_DIR / "apec_passenger_vehicle_saturation.csv"
RECONCILIATION_FACTORS_SOURCE_CSV = ROAD_MODEL_DATA_DIR / "apec_reconciliation_factors.csv"
VEHICLE_EQUIVALENT_WEIGHTS_SOURCE_CSV = ROAD_MODEL_DATA_DIR / "apec_vehicle_equivalent_weights.csv"
SURVIVAL_PROFILE_SOURCE_XLSX = ROAD_MODEL_DATA_DIR / "vehicle_survival_modified_00_APEC.xlsx"
VINTAGE_PROFILE_SOURCE_XLSX = ROAD_MODEL_DATA_DIR / "vintage_modelled_from_survival_00_APEC.xlsx"

ECONOMIES = [
    ("01AUS", "Australia", 26.0),
    ("02BD", "Brunei Darussalam", 0.45),
    ("03CDA", "Canada", 39.0),
    ("04CHL", "Chile", 20.0),
    ("05PRC", "China", 1410.0),
    ("06HKC", "Hong Kong, China", 7.5),
    ("07INA", "Indonesia", 275.0),
    ("08JPN", "Japan", 125.0),
    ("09ROK", "Korea", 52.0),
    ("10MAS", "Malaysia", 34.0),
    ("11MEX", "Mexico", 128.0),
    ("12NZ", "New Zealand", 5.2),
    ("13PNG", "Papua New Guinea", 10.0),
    ("14PE", "Peru", 34.0),
    ("15PHL", "Philippines", 114.0),
    ("16RUS", "Russia", 144.0),
    ("17SGP", "Singapore", 5.6),
    ("18CT", "Chinese Taipei", 23.5),
    ("19THA", "Thailand", 71.0),
    ("20USA", "United States", 333.0),
    ("21VN", "Viet Nam", 99.0),
]

ECONOMY_CODE_TO_LEAP_REGION_NAMES = {
    "01AUS": ["Australia"],
    "02BD": ["Brunei Darussalam"],
    "03CDA": ["Canada"],
    "04CHL": ["Chile"],
    "05PRC": ["People's Republic of China", "China"],
    "06HKC": ["Hong Kong, China"],
    "07INA": ["Indonesia"],
    "08JPN": ["Japan"],
    "09ROK": ["Republic of Korea", "Korea"],
    "10MAS": ["Malaysia"],
    "11MEX": ["Mexico"],
    "12NZ": ["New Zealand"],
    "13PNG": ["Papua New Guinea"],
    "14PE": ["Peru"],
    "15PHL": ["Philippines"],
    "16RUS": ["Russia"],
    "17SGP": ["Singapore"],
    "18CT": ["Chinese Taipei"],
    "19THA": ["Thailand"],
    "20USA": ["United States of America", "United States"],
    "21VN": ["Viet Nam"],
}
LEAP_REGION_NAME_TO_ECONOMY_CODE = {
    region_name: economy_code
    for economy_code, region_names in ECONOMY_CODE_TO_LEAP_REGION_NAMES.items()
    for region_name in region_names
}

VEHICLE_TYPES = [
    ("passenger", "passenger_car", 1.00, 0.62),
    ("passenger", "suv_light_truck", 1.35, 0.20),
    ("passenger", "bus", 12.00, 0.02),
    ("passenger", "motorcycle", 0.25, 0.16),
    ("freight", "light_commercial_vehicle", 1.50, 0.55),
    ("freight", "medium_truck", 3.00, 0.25),
    ("freight", "heavy_truck", 5.00, 0.20),
]

DRIVE_FUEL_MAP = {
    "ice_gasoline": "gasoline",
    "ice_diesel": "diesel",
    "lpg": "lpg",
    "cng": "natural_gas",
    "hev_gasoline": "gasoline",
    "erev_gasoline": "gasoline_electricity",
    "phev_gasoline": "gasoline_electricity",
    "bev": "electricity",
    "fcev": "hydrogen",
}

DEFAULT_DRIVE_SHARES = {
    "passenger_car": {
        "ice_gasoline": 0.65,
        "ice_diesel": 0.08,
        "lpg": 0.02,
        "cng": 0.01,
        "hev_gasoline": 0.11,
        "erev_gasoline": 0.03,
        "phev_gasoline": 0.02,
        "bev": 0.07,
        "fcev": 0.00,
    },
    "suv_light_truck": {
        "ice_gasoline": 0.70,
        "ice_diesel": 0.15,
        "lpg": 0.01,
        "cng": 0.01,
        "hev_gasoline": 0.06,
        "erev_gasoline": 0.01,
        "phev_gasoline": 0.01,
        "bev": 0.04,
        "fcev": 0.00,
    },
    "bus": {
        "ice_gasoline": 0.02,
        "ice_diesel": 0.78,
        "lpg": 0.01,
        "cng": 0.08,
        "hev_gasoline": 0.00,
        "erev_gasoline": 0.00,
        "phev_gasoline": 0.00,
        "bev": 0.09,
        "fcev": 0.01,
    },
    "motorcycle": {
        "ice_gasoline": 0.93,
        "ice_diesel": 0.00,
        "lpg": 0.00,
        "cng": 0.00,
        "hev_gasoline": 0.00,
        "erev_gasoline": 0.00,
        "phev_gasoline": 0.00,
        "bev": 0.07,
        "fcev": 0.00,
    },
    "light_commercial_vehicle": {
        "ice_gasoline": 0.42,
        "ice_diesel": 0.48,
        "lpg": 0.02,
        "cng": 0.02,
        "hev_gasoline": 0.00,
        "erev_gasoline": 0.00,
        "phev_gasoline": 0.01,
        "bev": 0.03,
        "fcev": 0.00,
    },
    "medium_truck": {
        "ice_gasoline": 0.06,
        "ice_diesel": 0.86,
        "lpg": 0.01,
        "cng": 0.04,
        "hev_gasoline": 0.00,
        "erev_gasoline": 0.00,
        "phev_gasoline": 0.00,
        "bev": 0.02,
        "fcev": 0.01,
    },
    "heavy_truck": {
        "ice_gasoline": 0.02,
        "ice_diesel": 0.90,
        "lpg": 0.00,
        "cng": 0.04,
        "hev_gasoline": 0.00,
        "erev_gasoline": 0.00,
        "phev_gasoline": 0.00,
        "bev": 0.02,
        "fcev": 0.02,
    },
}

# Explicitly constrain which drive types are valid for each vehicle type in
# Module 1 default generation. This prevents placeholder rows for combinations
# that are out of scope in the current road data tree.
VALID_DRIVES_BY_VEHICLE_TYPE = {
    "passenger_car": {
        "ice_gasoline",
        "ice_diesel",
        "lpg",
        "cng",
        "hev_gasoline",
        "erev_gasoline",
        "phev_gasoline",
        "bev",
        "fcev",
    },
    "suv_light_truck": {
        "ice_gasoline",
        "ice_diesel",
        "lpg",
        "cng",
        "hev_gasoline",
        "erev_gasoline",
        "phev_gasoline",
        "bev",
        "fcev",
    },
    "bus": {
        "ice_gasoline",
        "ice_diesel",
        "lpg",
        "cng",
        "phev_gasoline",
        "bev",
        "fcev",
    },
    "motorcycle": {
        "ice_gasoline",
        "bev",
    },
    "light_commercial_vehicle": {
        "ice_gasoline",
        "ice_diesel",
        "lpg",
        "cng",
        "phev_gasoline",
        "bev",
        "fcev",
    },
    "medium_truck": {
        "ice_gasoline",
        "ice_diesel",
        "lpg",
        "cng",
        "bev",
        "fcev",
    },
    "heavy_truck": {
        "ice_gasoline",
        "ice_diesel",
        "lpg",
        "cng",
        "bev",
        "fcev",
    },
}

MILEAGE_KM_PER_YEAR = {
    "passenger_car": 12500,
    "suv_light_truck": 13500,
    "bus": 45000,
    "motorcycle": 7000,
    "light_commercial_vehicle": 21000,
    "medium_truck": 36000,
    "heavy_truck": 65000,
}

EFFICIENCY_MJ_PER_KM = {
    "ice_gasoline": 2.7,
    "ice_diesel": 2.4,
    "lpg": 2.8,
    "cng": 2.6,
    "hev_gasoline": 1.9,
    "erev_gasoline": 1.4,
    "phev_gasoline": 1.5,
    "bev": 0.65,
    "fcev": 1.1,
}

EXPECTED_UNITS = {
    "base_year_stock": "vehicles",
    "current_sales_share": "share",
    "efficiency": "MJ_per_100km",
    "mileage": "vehicle_km_per_vehicle",
    "passenger_saturation": "vehicles_per_1000_people",
    "phev_electric_driving_share": "share",
    "reconciliation_bound_lower": "share",
    "reconciliation_bound_upper": "share",
    "reconciliation_weight": "weight",
    "survival_rate": "share",
    "vehicle_equivalent_weight": "vehicle_equivalent",
    "vintage_profile_share": "share",
}

MODULE1_INPUT_COLUMNS = [
    "Branch Path",
    "Variable",
    "Scenario",
    "Region",
    "Scale",
    "Units",
    "Per...",
    *YEAR_COLUMNS,
    "input_source",
    "standardized_label_status",
    "notes",
    "source_type",
    "source_name",
    "source_scope",
    "source_date",
    "default_version",
    "researcher_review_recommended",
    "review_reason",
]

MODULE1_KEY_COLUMNS = [
    "Branch Path",
    "Variable",
    "Scenario",
    "Region",
]

MODULE1_WORKBOOK_DATA_COLUMNS = [
    "Branch Path",
    "Variable",
    "Scenario",
    "Region",
    "Scale",
    "Units",
    "Per...",
    *YEAR_COLUMNS,
]

MODULE1_CORE_OUTPUT_FILE_TYPES = {
    "default_filled_inputs",
}

MODULE1_WORKBOOK_RESEARCHER_DATA_COLUMNS = [
    "Branch Path",
    "Variable",
    "Scenario",
    "Region",
    "Scale",
    "Units",
    "Per...",
    str(BASE_YEAR),
]

MODULE1_WORKBOOK_FACTOR_COLUMNS = [
    "Parameter",
    "Transport Type",
    "Vehicle Type",
    "Scenario",
    "Value",
    "Unit",
    "Notes",
]

MODULE1_WORKBOOK_REQUIRED_SHEETS = [
    "Data",
    "Lifecycle",
    "Vintage",
    "Factors",
    "Details",
]

MODULE1_REQUIRED_COLUMNS = [
    "Branch Path",
    "Variable",
    "Scenario",
    "Region",
    "Units",
    "input_source",
    "default_version",
]

MODULE1_ALLOWED_INPUT_SOURCES = ["default", "provided", "researcher", "researcher_override"]
MODULE1_ALLOWED_LABEL_STATUSES = ["standardized", "needs_mapping", "unknown"]

VEHICLE_TYPE_TO_LEAP_BRANCH = {
    "all": "",
    "passenger_car": "LPVs",
    "suv_light_truck": "LPVs",
    "bus": "Buses",
    "motorcycle": "Motorcycles",
    "light_commercial_vehicle": "LCVs",
    "medium_truck": "Trucks",
    "heavy_truck": "Trucks",
}

VEHICLE_TYPE_DETAIL_BRANCH = {
    "passenger_car": "Passenger cars",
    "suv_light_truck": "SUV and light trucks",
    "bus": "Buses",
    "motorcycle": "Motorcycles",
    "light_commercial_vehicle": "LCVs",
    "medium_truck": "Medium trucks",
    "heavy_truck": "Heavy trucks",
}

DRIVE_TO_LEAP_BRANCH = {
    "all": "",
    "ice_gasoline": "ICE",
    "ice_diesel": "ICE",
    "lpg": "ICE",
    "cng": "ICE",
    "hev_gasoline": "HEV",
    "erev_gasoline": "EREV",
    "phev_gasoline": "PHEV",
    "bev": "BEV",
    "fcev": "FCEV",
}

FUEL_TO_LEAP_BRANCH = {
    "all": "",
    "gasoline": "Motor gasoline",
    "diesel": "Gas and diesel oil",
    "lpg": "LPG",
    "natural_gas": "Natural gas",
    "gasoline_electricity": "",
    "electricity": "Electricity",
    "hydrogen": "Hydrogen",
}

PARAMETER_TO_LEAP_VARIABLE = {
    "base_year_stock": "Stock",
    "current_sales_share": "Sales Share",
    "efficiency": "Fuel Economy",
    "mileage": "Mileage",
    "passenger_saturation": "Passenger Vehicle Saturation",
    "phev_electric_driving_share": "PHEV Electric Driving Share",
    "reconciliation_bound_lower": "Reconciliation Bound Lower",
    "reconciliation_bound_upper": "Reconciliation Bound Upper",
    "reconciliation_weight": "Reconciliation Weight",
    "survival_rate": "Survival Rate",
    "vehicle_equivalent_weight": "Vehicle Equivalent Weight",
    "vintage_profile_share": "Vintage Profile Share",
}

PARAMETER_TO_LEAP_METADATA = {
    "base_year_stock": ("", "Device", ""),
    "current_sales_share": ("%", "Share", ""),
    "efficiency": ("", "MJ/100 km", ""),
    "mileage": ("", "Kilometer", ""),
    "passenger_saturation": ("", "Device", "1000 people"),
    "phev_electric_driving_share": ("%", "Share", ""),
    "reconciliation_bound_lower": ("%", "Share", ""),
    "reconciliation_bound_upper": ("%", "Share", ""),
    "reconciliation_weight": ("", "Weight", ""),
    "survival_rate": ("%", "Share", ""),
    "vehicle_equivalent_weight": ("", "Vehicle equivalent", ""),
    "vintage_profile_share": ("%", "Share", ""),
}

EXPECTED_UNITS_BY_VARIABLE = {
    PARAMETER_TO_LEAP_VARIABLE[parameter]: PARAMETER_TO_LEAP_METADATA[parameter][1]
    for parameter in PARAMETER_TO_LEAP_VARIABLE
}

MODULE1_VALUE_VALIDATION_RULES = {
    "Stock": {
        "min": 0,
        "description": "Stock cannot be negative.",
    },
    "Sales Share": {
        "min": 0,
        "max": 100,
        "description": "Sales Share must be between 0 and 100.",
    },
    "Fuel Economy": {
        "min": 0,
        "description": "Fuel economy cannot be negative.",
    },
    "Mileage": {
        "min": 0,
        "description": "Mileage cannot be negative.",
    },
    "Passenger Vehicle Saturation": {
        "min": 0,
        "description": "Passenger Vehicle Saturation cannot be negative.",
    },
    "PHEV Electric Driving Share": {
        "min": 0,
        "max": 100,
        "description": "PHEV Electric Driving Share must be between 0 and 100.",
    },
    "Reconciliation Bound Lower": {
        "min": 0,
        "description": "Reconciliation Bound Lower cannot be negative.",
    },
    "Reconciliation Bound Upper": {
        "min": 0,
        "description": "Reconciliation Bound Upper cannot be negative.",
    },
    "Reconciliation Weight": {
        "min": 0,
        "description": "Reconciliation Weight cannot be negative.",
    },
    "Survival Rate": {
        "min": 0,
        "max": 100,
        "description": "Survival Rate must be between 0 and 100.",
    },
    "Vehicle Equivalent Weight": {
        "min": 0,
        "description": "Vehicle Equivalent Weight cannot be negative.",
    },
    "Vintage Profile Share": {
        "min": 0,
        "max": 100,
        "description": "Vintage Profile Share must be between 0 and 100.",
    },
}


@dataclass(frozen=True)
class EconomyInfo:
    code: str
    name: str
    population_million: float


def get_economies() -> list[EconomyInfo]:
    return [EconomyInfo(code=code, name=name, population_million=pop) for code, name, pop in ECONOMIES]


def _base_stock_total(economy: EconomyInfo, transport_type: str) -> float:
    population = economy.population_million * 1_000_000
    if transport_type == "passenger":
        return population * 0.42
    return population * 0.055


def _year_multiplier(year: int, annual_change: float) -> float:
    return (1 + annual_change) ** max(year - BASE_YEAR, 0)


def _normalize_shares(shares: dict[str, float]) -> dict[str, float]:
    total = sum(shares.values())
    if total <= 0:
        return {key: 1 / len(shares) for key in shares}
    return {key: value / total for key, value in shares.items()}


def _source_fields(review_reason: str) -> dict[str, str | bool]:
    return {
        "source_type": "default_best_guess",
        "source_name": "APERC placeholder road defaults",
        "source_scope": "all_apec_economies_until_researcher_update",
        "source_date": SOURCE_DATE,
        "default_version": DEFAULT_VERSION,
        "researcher_review_recommended": False,
        "review_reason": "",
    }


def _normalize_apec_economy_code(raw_code: object) -> str:
    return str(raw_code or "").strip().replace("_", "")


def find_phev_utilisation_source_path(explicit_path: str | Path | None = None) -> Path | None:
    """Find the PHEV utilisation CSV used to populate default Road model inputs."""
    if explicit_path:
        candidate = Path(explicit_path)
        if candidate.exists():
            return candidate

    for candidate in [PHEV_UTILISATION_SOURCE_CSV]:
        if candidate.exists():
            return candidate
    return None


def load_phev_utilisation_rates(source_path: str | Path | None = None) -> tuple[pd.DataFrame, Path | None]:
    """Load economy-level PHEV electric utilisation rates from the source CSV."""
    resolved_path = find_phev_utilisation_source_path(source_path)
    if resolved_path is None:
        return pd.DataFrame(), None

    phev_df = pd.read_csv(resolved_path)
    required_columns = [
        "project_code",
        "economy",
        "data_year",
        "phev_utilisation_rate",
        "lower_rate",
        "upper_rate",
        "evidence_grade",
        "estimation_status",
    ]
    missing_columns = [column for column in required_columns if column not in phev_df.columns]
    if missing_columns:
        raise ValueError("PHEV utilisation CSV is missing required columns: " + ", ".join(missing_columns))

    phev_df = phev_df.copy()
    phev_df["economy_code"] = phev_df["project_code"].map(_normalize_apec_economy_code)
    for column in ["data_year", "phev_utilisation_rate", "lower_rate", "upper_rate"]:
        phev_df[column] = pd.to_numeric(phev_df[column], errors="coerce")
    return phev_df, resolved_path


def overlay_phev_utilisation_rates(
    default_filled_df: pd.DataFrame,
    economy: EconomyInfo,
    source_path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the PHEV utilisation CSV for base-year PHEV electric driving share rows."""
    phev_df, resolved_path = load_phev_utilisation_rates(source_path)
    if phev_df.empty or resolved_path is None:
        return default_filled_df, pd.DataFrame(
            [
                {
                    "status": "skipped",
                    "Branch Path": "",
                    "Variable": "PHEV Electric Driving Share",
                    "Scenario": "",
                    "Region": economy.name,
                    "source_year": "",
                    "details": "PHEV utilisation source CSV was not found.",
                }
            ]
        )

    source_rows = phev_df[phev_df["economy_code"].eq(economy.code)]
    if source_rows.empty:
        return default_filled_df, pd.DataFrame(
            [
                {
                    "status": "fail",
                    "Branch Path": "",
                    "Variable": "PHEV Electric Driving Share",
                    "Scenario": "",
                    "Region": economy.name,
                    "source_year": "",
                    "details": f"No PHEV utilisation row found for {economy.code}.",
                }
            ]
        )

    source_row = source_rows.iloc[0]
    rate = source_row["phev_utilisation_rate"]
    if pd.isna(rate):
        raise ValueError(f"PHEV utilisation rate is missing for {economy.code}.")

    overlaid_df = default_filled_df.copy()
    target_mask = overlaid_df["Variable"].eq("PHEV Electric Driving Share")
    report_rows = []
    note = (
        f"PHEV utilisation rate from {resolved_path.name}; source data_year "
        f"{int(source_row['data_year']) if not pd.isna(source_row['data_year']) else ''}; "
        f"evidence_grade {source_row['evidence_grade']}; "
        f"range {source_row['lower_rate']}-{source_row['upper_rate']}; "
        f"{source_row['estimation_status']}. Future-year changes are handled by LEAP adjustment variables."
    )

    for idx in overlaid_df[target_mask].index:
        overlaid_df.at[idx, str(BASE_YEAR)] = float(rate)
        for year_col in YEAR_COLUMNS:
            if int(year_col) > BASE_YEAR:
                overlaid_df.at[idx, year_col] = pd.NA
        overlaid_df.at[idx, "input_source"] = "provided"
        overlaid_df.at[idx, "source_type"] = "apec_phev_utilisation_rates"
        overlaid_df.at[idx, "source_name"] = resolved_path.name
        overlaid_df.at[idx, "source_scope"] = economy.code
        overlaid_df.at[idx, "source_date"] = str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else ""
        overlaid_df.at[idx, "researcher_review_recommended"] = False
        overlaid_df.at[idx, "review_reason"] = ""
        overlaid_df.at[idx, "notes"] = note
        report_rows.append(
            {
                "status": "applied",
                "Branch Path": overlaid_df.at[idx, "Branch Path"],
                "Variable": "PHEV Electric Driving Share",
                "Scenario": overlaid_df.at[idx, "Scenario"],
                "Region": economy.name,
                "source_year": overlaid_df.at[idx, "source_date"],
                "details": f"{BASE_YEAR}={float(rate)}",
            }
        )

    return overlaid_df[MODULE1_INPUT_COLUMNS], pd.DataFrame(report_rows)


def _find_first_existing_path(
    explicit_path: str | Path | None,
    candidates: list[Path],
) -> Path | None:
    if explicit_path:
        explicit_candidate = Path(explicit_path)
        if explicit_candidate.exists():
            return explicit_candidate
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_passenger_saturation_source_path(explicit_path: str | Path | None = None) -> Path | None:
    return _find_first_existing_path(
        explicit_path,
        [PASSENGER_SATURATION_SOURCE_CSV],
    )


def load_passenger_saturation_rates(
    source_path: str | Path | None = None,
) -> tuple[pd.DataFrame, Path | None]:
    resolved_path = find_passenger_saturation_source_path(source_path)
    if resolved_path is None:
        return pd.DataFrame(), None

    saturation_df = pd.read_csv(resolved_path)
    required_columns = [
        "project_code",
        "economy",
        "data_year",
        "saturation_vehicles_per_1000",
        "lower_bound",
        "upper_bound",
        "evidence_grade",
        "estimation_status",
    ]
    missing_columns = [column for column in required_columns if column not in saturation_df.columns]
    if missing_columns:
        raise ValueError(
            "Passenger saturation CSV is missing required columns: " + ", ".join(missing_columns)
        )

    saturation_df = saturation_df.copy()
    saturation_df["economy_code"] = saturation_df["project_code"].map(_normalize_apec_economy_code)
    for column in ["data_year", "saturation_vehicles_per_1000", "lower_bound", "upper_bound"]:
        saturation_df[column] = pd.to_numeric(saturation_df[column], errors="coerce")
    return saturation_df, resolved_path


def find_reconciliation_factors_source_path(explicit_path: str | Path | None = None) -> Path | None:
    return _find_first_existing_path(
        explicit_path,
        [RECONCILIATION_FACTORS_SOURCE_CSV],
    )


def load_reconciliation_factors(
    source_path: str | Path | None = None,
) -> tuple[pd.DataFrame, Path | None]:
    resolved_path = find_reconciliation_factors_source_path(source_path)
    if resolved_path is None:
        return pd.DataFrame(), None

    factors_df = pd.read_csv(resolved_path)
    required_columns = [
        "transport_type",
        "reconciliation_bound_lower",
        "reconciliation_bound_upper",
        "reconciliation_weight",
        "data_year",
    ]
    missing_columns = [column for column in required_columns if column not in factors_df.columns]
    if missing_columns:
        raise ValueError(
            "Reconciliation factors CSV is missing required columns: " + ", ".join(missing_columns)
        )

    factors_df = factors_df.copy()
    factors_df["transport_type"] = factors_df["transport_type"].fillna("").astype(str).str.strip().str.lower()
    for column in ["reconciliation_bound_lower", "reconciliation_bound_upper", "reconciliation_weight", "data_year"]:
        factors_df[column] = pd.to_numeric(factors_df[column], errors="coerce")
    return factors_df, resolved_path


def find_vehicle_equivalent_weights_source_path(explicit_path: str | Path | None = None) -> Path | None:
    return _find_first_existing_path(
        explicit_path,
        [VEHICLE_EQUIVALENT_WEIGHTS_SOURCE_CSV],
    )


def load_vehicle_equivalent_weights(
    source_path: str | Path | None = None,
) -> tuple[pd.DataFrame, Path | None]:
    resolved_path = find_vehicle_equivalent_weights_source_path(source_path)
    if resolved_path is None:
        return pd.DataFrame(), None

    weights_df = pd.read_csv(resolved_path)
    required_columns = ["vehicle_type", "vehicle_equivalent_weight", "data_year"]
    missing_columns = [column for column in required_columns if column not in weights_df.columns]
    if missing_columns:
        raise ValueError(
            "Vehicle equivalent weights CSV is missing required columns: " + ", ".join(missing_columns)
        )

    weights_df = weights_df.copy()
    weights_df["vehicle_type"] = weights_df["vehicle_type"].fillna("").astype(str).str.strip().str.lower()
    for column in ["vehicle_equivalent_weight", "data_year"]:
        weights_df[column] = pd.to_numeric(weights_df[column], errors="coerce")
    return weights_df, resolved_path


def _vehicle_type_from_weight_branch_path(branch_path: str) -> str:
    normalized_path = str(branch_path or "").strip().lower().replace("\\", "/")
    mapping = {
        "demand/passenger road/buses": "bus",
        "demand/passenger road/lpvs/passenger cars": "passenger_car",
        "demand/passenger road/lpvs/suv and light trucks": "suv_light_truck",
        "demand/passenger road/motorcycles": "motorcycle",
    }
    return mapping.get(normalized_path, "")


def overlay_model_factor_sources(
    default_filled_df: pd.DataFrame,
    economy: EconomyInfo,
    saturation_source_path: str | Path | None = None,
    reconciliation_source_path: str | Path | None = None,
    vehicle_weight_source_path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    overlaid_df = default_filled_df.copy()
    report_rows: list[dict[str, object]] = []

    saturation_df, saturation_path = load_passenger_saturation_rates(saturation_source_path)
    if saturation_df.empty or saturation_path is None:
        report_rows.append(
            {
                "status": "skipped",
                "Branch Path": "Demand\\Passenger road",
                "Variable": "Passenger Vehicle Saturation",
                "Scenario": "",
                "Region": economy.name,
                "source_file": "",
                "details": "Passenger saturation source CSV not found.",
            }
        )
    else:
        source_rows = saturation_df[saturation_df["economy_code"].eq(economy.code)]
        if source_rows.empty:
            report_rows.append(
                {
                    "status": "fail",
                    "Branch Path": "Demand\\Passenger road",
                    "Variable": "Passenger Vehicle Saturation",
                    "Scenario": "",
                    "Region": economy.name,
                    "source_file": saturation_path.name,
                    "details": f"No passenger saturation row found for {economy.code}.",
                }
            )
        else:
            source_row = source_rows.iloc[0]
            saturation_value = source_row["saturation_vehicles_per_1000"]
            if pd.isna(saturation_value):
                raise ValueError(f"Passenger saturation is missing for {economy.code}.")

            target_mask = (
                overlaid_df["Variable"].eq("Passenger Vehicle Saturation")
                & overlaid_df["Branch Path"].eq("Demand\\Passenger road")
            )
            for idx in overlaid_df[target_mask].index:
                overlaid_df.at[idx, str(BASE_YEAR)] = float(saturation_value)
                for year_col in YEAR_COLUMNS:
                    if int(year_col) > BASE_YEAR:
                        overlaid_df.at[idx, year_col] = pd.NA
                overlaid_df.at[idx, "input_source"] = "provided"
                overlaid_df.at[idx, "source_type"] = "apec_passenger_saturation"
                overlaid_df.at[idx, "source_name"] = saturation_path.name
                overlaid_df.at[idx, "source_scope"] = economy.code
                overlaid_df.at[idx, "source_date"] = (
                    str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else ""
                )
                overlaid_df.at[idx, "researcher_review_recommended"] = False
                overlaid_df.at[idx, "review_reason"] = ""
                overlaid_df.at[idx, "notes"] = (
                    f"Passenger saturation from {saturation_path.name}; "
                    f"lower={source_row['lower_bound']}, upper={source_row['upper_bound']}, "
                    f"grade={source_row['evidence_grade']}, "
                    f"status={source_row['estimation_status']}."
                )
                report_rows.append(
                    {
                        "status": "applied",
                        "Branch Path": overlaid_df.at[idx, "Branch Path"],
                        "Variable": "Passenger Vehicle Saturation",
                        "Scenario": overlaid_df.at[idx, "Scenario"],
                        "Region": economy.name,
                        "source_file": saturation_path.name,
                        "details": f"{BASE_YEAR}={float(saturation_value)}",
                    }
                )

    reconciliation_df, reconciliation_path = load_reconciliation_factors(reconciliation_source_path)
    if reconciliation_df.empty or reconciliation_path is None:
        report_rows.append(
            {
                "status": "skipped",
                "Branch Path": "Demand\\Passenger road;Demand\\Freight road",
                "Variable": "Reconciliation Bound Lower/Upper/Weight",
                "Scenario": "",
                "Region": economy.name,
                "source_file": "",
                "details": "Reconciliation factors source CSV not found.",
            }
        )
    else:
        reconciliation_by_transport = {
            row["transport_type"]: row
            for _, row in reconciliation_df.iterrows()
            if row["transport_type"] in {"passenger", "freight"}
        }
        for idx, target_row in overlaid_df.iterrows():
            variable = str(target_row.get("Variable", ""))
            if variable not in {
                "Reconciliation Bound Lower",
                "Reconciliation Bound Upper",
                "Reconciliation Weight",
            }:
                continue
            transport_type = _extract_transport_label_from_branch_path(str(target_row.get("Branch Path", "")))
            source_row = reconciliation_by_transport.get(transport_type)
            if source_row is None:
                continue

            if variable == "Reconciliation Bound Lower":
                source_value = source_row["reconciliation_bound_lower"]
            elif variable == "Reconciliation Bound Upper":
                source_value = source_row["reconciliation_bound_upper"]
            else:
                source_value = source_row["reconciliation_weight"]

            if pd.isna(source_value):
                continue

            overlaid_df.at[idx, str(BASE_YEAR)] = float(source_value)
            for year_col in YEAR_COLUMNS:
                if int(year_col) > BASE_YEAR:
                    overlaid_df.at[idx, year_col] = pd.NA
            overlaid_df.at[idx, "input_source"] = "provided"
            overlaid_df.at[idx, "source_type"] = "apec_reconciliation_factors"
            overlaid_df.at[idx, "source_name"] = reconciliation_path.name
            overlaid_df.at[idx, "source_scope"] = transport_type
            overlaid_df.at[idx, "source_date"] = (
                str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else ""
            )
            overlaid_df.at[idx, "researcher_review_recommended"] = False
            overlaid_df.at[idx, "review_reason"] = ""
            overlaid_df.at[idx, "notes"] = (
                f"Reconciliation factor from {reconciliation_path.name} ({transport_type})."
            )
            report_rows.append(
                {
                    "status": "applied",
                    "Branch Path": target_row["Branch Path"],
                    "Variable": variable,
                    "Scenario": target_row["Scenario"],
                    "Region": economy.name,
                    "source_file": reconciliation_path.name,
                    "details": f"{BASE_YEAR}={float(source_value)}",
                }
            )

    vehicle_weights_df, vehicle_weights_path = load_vehicle_equivalent_weights(vehicle_weight_source_path)
    if vehicle_weights_df.empty or vehicle_weights_path is None:
        report_rows.append(
            {
                "status": "skipped",
                "Branch Path": "",
                "Variable": "Vehicle Equivalent Weight",
                "Scenario": "",
                "Region": economy.name,
                "source_file": "",
                "details": "Vehicle equivalent weights source CSV not found.",
            }
        )
    else:
        weights_by_vehicle = {
            row["vehicle_type"]: row
            for _, row in vehicle_weights_df.iterrows()
        }
        for idx, target_row in overlaid_df.iterrows():
            if str(target_row.get("Variable", "")) != "Vehicle Equivalent Weight":
                continue
            vehicle_key = _vehicle_type_from_weight_branch_path(str(target_row.get("Branch Path", "")))
            source_row = weights_by_vehicle.get(vehicle_key)
            if source_row is None:
                continue
            source_value = source_row["vehicle_equivalent_weight"]
            if pd.isna(source_value):
                continue

            overlaid_df.at[idx, str(BASE_YEAR)] = float(source_value)
            for year_col in YEAR_COLUMNS:
                if int(year_col) > BASE_YEAR:
                    overlaid_df.at[idx, year_col] = pd.NA
            overlaid_df.at[idx, "input_source"] = "provided"
            overlaid_df.at[idx, "source_type"] = "apec_vehicle_equivalent_weights"
            overlaid_df.at[idx, "source_name"] = vehicle_weights_path.name
            overlaid_df.at[idx, "source_scope"] = vehicle_key
            overlaid_df.at[idx, "source_date"] = (
                str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else ""
            )
            overlaid_df.at[idx, "researcher_review_recommended"] = False
            overlaid_df.at[idx, "review_reason"] = ""
            overlaid_df.at[idx, "notes"] = (
                f"Vehicle equivalent weight from {vehicle_weights_path.name} ({vehicle_key})."
            )
            report_rows.append(
                {
                    "status": "applied",
                    "Branch Path": target_row["Branch Path"],
                    "Variable": "Vehicle Equivalent Weight",
                    "Scenario": target_row["Scenario"],
                    "Region": economy.name,
                    "source_file": vehicle_weights_path.name,
                    "details": f"{BASE_YEAR}={float(source_value)}",
                }
            )

    report_df = pd.DataFrame(report_rows)
    if report_df.empty:
        report_df = pd.DataFrame(
            columns=["status", "Branch Path", "Variable", "Scenario", "Region", "source_file", "details"]
        )

    return overlaid_df[MODULE1_INPUT_COLUMNS], report_df


def find_survival_profile_source_path(explicit_path: str | Path | None = None) -> Path | None:
    return _find_first_existing_path(
        explicit_path,
        [SURVIVAL_PROFILE_SOURCE_XLSX],
    )


def find_vintage_profile_source_path(explicit_path: str | Path | None = None) -> Path | None:
    return _find_first_existing_path(
        explicit_path,
        [VINTAGE_PROFILE_SOURCE_XLSX],
    )


def _normalize_transport_type(value: object) -> str:
    text = str(value or "").strip().lower()
    if "pass" in text:
        return "passenger"
    if "freight" in text or "truck" in text:
        return "freight"
    return ""


def _economy_code_from_source_row(row: pd.Series) -> str:
    project_code = _normalize_apec_economy_code(row.get("project_code", ""))
    if project_code:
        return project_code

    economy_text = str(row.get("economy", "")).strip()
    if economy_text:
        if economy_text in LEAP_REGION_NAME_TO_ECONOMY_CODE:
            return LEAP_REGION_NAME_TO_ECONOMY_CODE[economy_text]
        normalized = _normalize_apec_economy_code(economy_text)
        if normalized:
            return normalized
    return ""


def _load_age_profile_records_from_workbook(
    workbook_path: Path,
    value_column_candidates: list[str],
) -> pd.DataFrame:
    all_sheets = pd.read_excel(workbook_path, sheet_name=None)
    parsed_frames: list[pd.DataFrame] = []

    for _, sheet_df in all_sheets.items():
        if sheet_df is None or sheet_df.empty:
            continue

        normalized_df = sheet_df.copy()
        normalized_df.columns = [str(column).strip().lower() for column in normalized_df.columns]

        value_col = next((column for column in value_column_candidates if column in normalized_df.columns), None)
        age_col = "age" if "age" in normalized_df.columns else ("year" if "year" in normalized_df.columns else None)

        if value_col is None or age_col is None:
            continue

        transport_col = "transport_type" if "transport_type" in normalized_df.columns else None
        if transport_col is None and "transport" in normalized_df.columns:
            transport_col = "transport"

        slim_df = pd.DataFrame(
            {
                "economy_code": normalized_df.apply(_economy_code_from_source_row, axis=1),
                "transport_type": (
                    normalized_df[transport_col].map(_normalize_transport_type)
                    if transport_col
                    else ""
                ),
                "age": pd.to_numeric(normalized_df[age_col], errors="coerce"),
                "value": pd.to_numeric(normalized_df[value_col], errors="coerce"),
            }
        )
        slim_df = slim_df.dropna(subset=["age", "value"]).copy()
        if slim_df.empty:
            continue
        parsed_frames.append(slim_df)

    if not parsed_frames:
        return pd.DataFrame(columns=["economy_code", "transport_type", "age", "value"])

    combined = pd.concat(parsed_frames, ignore_index=True)
    combined["age"] = combined["age"].astype(int)
    combined = combined[(combined["age"] >= 0) & (combined["age"] <= 100)]
    return combined


def load_survival_profile_records(source_path: str | Path | None = None) -> tuple[pd.DataFrame, Path | None]:
    resolved_path = find_survival_profile_source_path(source_path)
    if resolved_path is None:
        return pd.DataFrame(columns=["economy_code", "transport_type", "age", "value"]), None
    records = _load_age_profile_records_from_workbook(
        resolved_path,
        value_column_candidates=["survival_rate", "survival", "value", "rate"],
    )
    return records, resolved_path


def load_vintage_profile_records(source_path: str | Path | None = None) -> tuple[pd.DataFrame, Path | None]:
    resolved_path = find_vintage_profile_source_path(source_path)
    if resolved_path is None:
        return pd.DataFrame(columns=["economy_code", "transport_type", "age", "value"]), None
    records = _load_age_profile_records_from_workbook(
        resolved_path,
        value_column_candidates=["vintage_profile_share", "vintage_share", "vintage", "share", "value"],
    )
    return records, resolved_path


def _build_profile_lookup_map(
    records: pd.DataFrame,
    economy_code: str,
) -> dict[tuple[str, int], float]:
    lookup: dict[tuple[str, int], float] = {}
    if records.empty:
        return lookup

    economy_subset = records[records["economy_code"].eq(economy_code)].copy()
    if economy_subset.empty:
        economy_subset = records[records["economy_code"].eq("")].copy()

    for _, row in economy_subset.iterrows():
        transport_type = str(row.get("transport_type", "")).strip().lower()
        if transport_type not in {"passenger", "freight"}:
            continue
        age = int(row["age"])
        value = float(row["value"])
        lookup[(transport_type, age)] = value
    return lookup


def overlay_survival_and_vintage_profiles(
    default_filled_df: pd.DataFrame,
    economy: EconomyInfo,
    survival_source_path: str | Path | None = None,
    vintage_source_path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    overlaid_df = default_filled_df.copy()
    report_rows: list[dict[str, object]] = []

    survival_records, survival_path = load_survival_profile_records(survival_source_path)
    vintage_records, vintage_path = load_vintage_profile_records(vintage_source_path)

    profile_specs = [
        ("Survival Rate", survival_records, survival_path, "survival_profile_source"),
        ("Vintage Profile Share", vintage_records, vintage_path, "vintage_profile_source"),
    ]

    for variable_name, profile_records, profile_path, source_type in profile_specs:
        if profile_path is None or profile_records.empty:
            report_rows.append(
                {
                    "status": "skipped",
                    "Branch Path": "",
                    "Variable": variable_name,
                    "Scenario": "",
                    "Region": economy.name,
                    "source_file": profile_path.name if profile_path else "",
                    "details": "Profile source workbook missing or had no parseable age/value table.",
                }
            )
            continue

        profile_lookup = _build_profile_lookup_map(profile_records, economy.code)
        if not profile_lookup:
            report_rows.append(
                {
                    "status": "fail",
                    "Branch Path": "",
                    "Variable": variable_name,
                    "Scenario": "",
                    "Region": economy.name,
                    "source_file": profile_path.name,
                    "details": f"No profile rows matched economy {economy.code} (or blank/common profile rows).",
                }
            )
            continue

        for idx, row in overlaid_df.iterrows():
            if str(row.get("Variable", "")) != variable_name:
                continue

            transport_label = _extract_transport_label_from_branch_path(str(row.get("Branch Path", "")))
            age = _extract_age_from_branch_path(str(row.get("Branch Path", "")))
            if transport_label not in {"passenger", "freight"} or age is None:
                continue

            profile_value = profile_lookup.get((transport_label, age))
            if profile_value is None:
                continue

            overlaid_df.at[idx, str(BASE_YEAR)] = float(profile_value)
            for year_col in YEAR_COLUMNS:
                if int(year_col) > BASE_YEAR:
                    overlaid_df.at[idx, year_col] = pd.NA

            overlaid_df.at[idx, "input_source"] = "provided"
            overlaid_df.at[idx, "source_type"] = source_type
            overlaid_df.at[idx, "source_name"] = profile_path.name
            overlaid_df.at[idx, "source_scope"] = economy.code
            overlaid_df.at[idx, "source_date"] = SOURCE_DATE
            overlaid_df.at[idx, "researcher_review_recommended"] = False
            overlaid_df.at[idx, "review_reason"] = ""
            overlaid_df.at[idx, "notes"] = (
                f"{variable_name} imported from {profile_path.name}; "
                f"transport={transport_label}, age={age}."
            )
            report_rows.append(
                {
                    "status": "applied",
                    "Branch Path": row["Branch Path"],
                    "Variable": variable_name,
                    "Scenario": row["Scenario"],
                    "Region": economy.name,
                    "source_file": profile_path.name,
                    "details": f"{BASE_YEAR}={float(profile_value)}",
                }
            )

    report_df = pd.DataFrame(report_rows)
    if report_df.empty:
        report_df = pd.DataFrame(
            columns=["status", "Branch Path", "Variable", "Scenario", "Region", "source_file", "details"]
        )

    return overlaid_df[MODULE1_INPUT_COLUMNS], report_df


def _transport_export_sort_key(path: Path) -> tuple[str, float]:
    match = re.search(r"_(\d{8})(?:\D|$)", path.name)
    date_token = match.group(1) if match else ""
    return date_token, path.stat().st_mtime


def _latest_existing_file(paths: Iterable[Path]) -> Path | None:
    existing_paths = [path for path in paths if path.exists() and path.is_file()]
    if not existing_paths:
        return None
    return max(existing_paths, key=_transport_export_sort_key)


def _iter_transport_leap_all_econs_candidates() -> Iterable[Path]:
    search_dirs = [TRANSPORT_LEAP_EXPORT_DIR]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        yield from search_dir.glob(TRANSPORT_LEAP_EXPORT_ALL_ECONS_PATTERN)


def _economy_to_leap_import_token(economy: str | None) -> str:
    economy_text = str(economy or "").strip().upper()
    if len(economy_text) >= 5 and economy_text[:2].isdigit():
        return f"{economy_text[:2]}_{economy_text[2:]}"
    return economy_text


def _iter_transport_leap_economy_candidates(economy: str) -> Iterable[Path]:
    token = _economy_to_leap_import_token(economy)
    if not token:
        return
    pattern = f"transport_leap_export_combined_{token}_domestic_international_Target_*.xlsx"
    for search_dir in [TRANSPORT_LEAP_EXPORT_DIR]:
        if not search_dir.exists():
            continue
        yield from search_dir.glob(pattern)


def find_transport_leap_export_path(
    explicit_path: str | Path | None = None,
    economy: str | None = None,
) -> Path | None:
    """Find the latest transport LEAP export workbook used to improve defaults."""
    if explicit_path:
        explicit_candidate = Path(explicit_path)
        if explicit_candidate.exists():
            return explicit_candidate

    if economy:
        latest_economy_file = _latest_existing_file(_iter_transport_leap_economy_candidates(economy))
        if latest_economy_file is not None:
            return latest_economy_file

    latest_all_econs = _latest_existing_file(_iter_transport_leap_all_econs_candidates())
    if latest_all_econs is not None:
        return latest_all_econs

    fallback_paths = [
        TRANSPORT_LEAP_EXPORT_DIR / TRANSPORT_LEAP_EXPORT_FALLBACK_FILENAME,
    ]
    return _latest_existing_file(fallback_paths)


def _transport_leap_source_regions(economy: EconomyInfo) -> list[str]:
    regions = [economy.name]
    regions.extend(ECONOMY_CODE_TO_LEAP_REGION_NAMES.get(economy.code, []))
    seen = set()
    unique_regions = []
    for region in regions:
        region_text = str(region).strip()
        if not region_text or region_text in seen:
            continue
        unique_regions.append(region_text)
        seen.add(region_text)
    return unique_regions


def _matching_transport_leap_rows(
    workbook_df: pd.DataFrame,
    *,
    branch_path: str,
    variable: str,
    regions: Iterable[str],
) -> pd.DataFrame:
    region_values = list(regions)
    if not region_values:
        return pd.DataFrame(columns=workbook_df.columns)

    variable_aliases = {variable}
    if variable == "Fuel Economy":
        variable_aliases.add("Final On-Road Fuel Economy")
    elif variable == "Final On-Road Fuel Economy":
        variable_aliases.add("Fuel Economy")

    return workbook_df[
        workbook_df["Branch Path"].eq(branch_path)
        & workbook_df["Variable"].isin(variable_aliases)
        & workbook_df["Region"].isin(region_values)
    ]


def _transport_leap_source_scope(
    *,
    source_region: str,
    economy: EconomyInfo,
) -> str:
    if source_region == economy.name:
        return "exact_region_match"
    if source_region in ECONOMY_CODE_TO_LEAP_REGION_NAMES.get(economy.code, []):
        return "leap_region_alias_match"
    if source_region == "APEC":
        return "apec_fallback_non_absolute"
    return "region_match"


def _transport_leap_source_type(source_scope: str) -> str:
    if source_scope == "apec_fallback_non_absolute":
        return "transport_leap_export_apec_fallback"
    return "transport_leap_export_default"


def load_transport_leap_export_defaults(
    workbook_path: str | Path | None = None,
    economy: str | None = None,
) -> tuple[pd.DataFrame, Path | None]:
    """Load the FOR_VIEWING sheet in a lean form for defaults overlay."""
    resolved_path = find_transport_leap_export_path(workbook_path, economy=economy)
    if resolved_path is None:
        return pd.DataFrame(), None

    workbook_df = _load_transport_leap_export_defaults_from_path(str(resolved_path.resolve()))
    return workbook_df.copy(), resolved_path


@lru_cache(maxsize=4)
def _load_transport_leap_export_defaults_from_path(resolved_path_text: str) -> pd.DataFrame:
    resolved_path = Path(resolved_path_text)
    required_columns = ["Branch Path", "Variable", "Scenario", "Region", "Scale", "Units", "Per..."]
    required_column_set = set(required_columns)
    year_column_set = {str(year) for year in DEFAULT_YEARS} | set(DEFAULT_YEARS)

    workbook_df = pd.read_excel(
        resolved_path,
        sheet_name=TRANSPORT_LEAP_EXPORT_SHEET,
        header=TRANSPORT_LEAP_EXPORT_HEADER_ROW,
        usecols=lambda column: column in required_column_set or column in year_column_set,
    )

    missing_columns = [column for column in required_columns if column not in workbook_df.columns]
    if missing_columns:
        raise ValueError(
            "Transport LEAP export workbook is missing required columns: " + ", ".join(missing_columns)
        )

    rename_columns = {year: str(year) for year in DEFAULT_YEARS if year in workbook_df.columns}
    workbook_df = workbook_df.rename(columns=rename_columns)
    keep_columns = [*required_columns, *[year_col for year_col in YEAR_COLUMNS if year_col in workbook_df.columns]]
    workbook_df = workbook_df[keep_columns].copy()

    text_columns = ["Branch Path", "Variable", "Scenario", "Region", "Scale", "Units", "Per..."]
    for column in text_columns:
        workbook_df[column] = workbook_df[column].fillna("").astype(str).str.strip()

    workbook_df = workbook_df[workbook_df["Branch Path"].ne("") & workbook_df["Variable"].ne("")]
    for year_col in YEAR_COLUMNS:
        if year_col in workbook_df.columns:
            workbook_df[year_col] = pd.to_numeric(workbook_df[year_col], errors="coerce")

    return workbook_df


def _select_transport_leap_source_row(
    source_rows: pd.DataFrame,
    target_scenario: str,
) -> pd.Series | None:
    if source_rows.empty:
        return None

    for scenario in [target_scenario, *TRANSPORT_LEAP_EXPORT_SCENARIO_PRIORITY]:
        matching_scenario = source_rows[source_rows["Scenario"].eq(scenario)]
        if not matching_scenario.empty:
            return matching_scenario.iloc[0]
    return source_rows.iloc[0]


def overlay_transport_leap_export_values(
    default_filled_df: pd.DataFrame,
    economy: EconomyInfo,
    workbook_path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the LEAP export workbook as the best available default data source where it matches."""
    workbook_df, resolved_path = load_transport_leap_export_defaults(
        workbook_path=workbook_path,
        economy=economy.code,
    )
    overlay_report_rows = []
    if workbook_df.empty or resolved_path is None:
        return default_filled_df, pd.DataFrame(
            [
                {
                    "status": "skipped",
                    "Branch Path": "",
                    "Variable": "",
                    "Scenario": "",
                    "Region": economy.name,
                    "source_region": "",
                    "source_scenario": "",
                    "years_overlaid": "",
                    "details": "Transport LEAP export workbook was not found.",
                }
            ]
        )

    overlaid_df = default_filled_df.copy()
    source_filename = resolved_path.name
    source_regions = _transport_leap_source_regions(economy)

    for idx, target_row in overlaid_df.iterrows():
        if target_row.get("source_type") == "apec_phev_utilisation_rates":
            continue

        branch_path = target_row["Branch Path"]
        variable = target_row["Variable"]
        target_scenario = target_row["Scenario"]

        source_rows = _matching_transport_leap_rows(
            workbook_df,
            branch_path=branch_path,
            variable=variable,
            regions=source_regions,
        )

        if source_rows.empty and variable in TRANSPORT_LEAP_EXPORT_APEC_FALLBACK_VARIABLES:
            source_rows = _matching_transport_leap_rows(
                workbook_df,
                branch_path=branch_path,
                variable=variable,
                regions=["APEC"],
            )

        selected_source_row = _select_transport_leap_source_row(
            source_rows=source_rows,
            target_scenario=target_scenario,
        )
        if selected_source_row is None:
            continue

        years_overlaid = []
        for year_col in YEAR_COLUMNS:
            if year_col not in workbook_df.columns or pd.isna(selected_source_row[year_col]):
                continue
            overlaid_df.at[idx, year_col] = float(selected_source_row[year_col])
            years_overlaid.append(year_col)

        if not years_overlaid:
            continue

        overlaid_df.at[idx, "Scale"] = selected_source_row["Scale"]
        overlaid_df.at[idx, "Units"] = selected_source_row["Units"]
        overlaid_df.at[idx, "Per..."] = selected_source_row["Per..."]
        source_scope = _transport_leap_source_scope(
            source_region=selected_source_row["Region"],
            economy=economy,
        )
        source_type = _transport_leap_source_type(source_scope)
        overlaid_df.at[idx, "source_type"] = source_type
        overlaid_df.at[idx, "source_name"] = source_filename
        overlaid_df.at[idx, "source_scope"] = source_scope
        overlaid_df.at[idx, "source_date"] = SOURCE_DATE
        existing_notes = str(overlaid_df.at[idx, "notes"] or "").strip()
        overlay_note = (
            "Transport LEAP export value overlay applied from "
            f"{selected_source_row['Region']} / {selected_source_row['Scenario']}."
        )
        overlaid_df.at[idx, "notes"] = f"{existing_notes} {overlay_note}".strip()

        overlay_report_rows.append(
            {
                "status": "applied",
                "Branch Path": branch_path,
                "Variable": variable,
                "Scenario": target_scenario,
                "Region": economy.name,
                "source_region": selected_source_row["Region"],
                "source_scenario": selected_source_row["Scenario"],
                "years_overlaid": ";".join(years_overlaid),
                "details": source_scope,
            }
        )

    if not overlay_report_rows:
        overlay_report_rows.append(
            {
                "status": "no_matches",
                "Branch Path": "",
                "Variable": "",
                "Scenario": "",
                "Region": economy.name,
                "source_region": "",
                "source_scenario": "",
                "years_overlaid": "",
                "details": f"No matching defaults found in {source_filename}.",
            }
        )

    return overlaid_df[MODULE1_INPUT_COLUMNS], pd.DataFrame(overlay_report_rows)


def _format_leap_scenario(scenario: str) -> str:
    return scenario.replace("_", " ").title()


def _build_branch_path(
    transport_type: str,
    vehicle_type: str,
    drive: str,
    fuel: str,
    parameter: str,
    parameter_detail: str = "",
) -> str:
    road_branch = "Passenger road" if transport_type == "passenger" else "Freight road"
    parts = ["Demand", road_branch]

    vehicle_branch = VEHICLE_TYPE_TO_LEAP_BRANCH.get(vehicle_type, vehicle_type)
    if vehicle_branch:
        parts.append(vehicle_branch)

    drive_branch = DRIVE_TO_LEAP_BRANCH.get(drive, drive)
    if vehicle_type == "suv_light_truck" and drive_branch in {"ICE", "HEV", "EREV", "PHEV", "BEV", "FCEV"}:
        drive_branch = f"{drive_branch} medium"
    elif vehicle_type == "passenger_car" and drive_branch in {"ICE", "HEV", "EREV", "PHEV", "BEV", "FCEV"}:
        drive_branch = f"{drive_branch} small"
    elif vehicle_type == "medium_truck" and drive_branch in {"ICE", "HEV", "EREV", "PHEV", "BEV", "FCEV"}:
        drive_branch = f"{drive_branch} medium"
    elif vehicle_type == "heavy_truck" and drive_branch in {"ICE", "HEV", "EREV", "PHEV", "BEV", "FCEV"}:
        drive_branch = f"{drive_branch} heavy"

    if drive == "all" and vehicle_type in VEHICLE_TYPE_DETAIL_BRANCH:
        detail_branch = VEHICLE_TYPE_DETAIL_BRANCH[vehicle_type]
        if detail_branch != vehicle_branch:
            parts.append(detail_branch)

    if drive_branch:
        parts.append(drive_branch)

    fuel_branch = FUEL_TO_LEAP_BRANCH.get(fuel, fuel)
    if fuel_branch and parameter in {
        "efficiency",
        "mileage",
    }:
        parts.append(fuel_branch)

    if parameter_detail:
        parts.append(parameter_detail.replace("_", " ").title())

    return "\\".join(parts)


def _build_levels(branch_path: str) -> dict[str, str]:
    parts = branch_path.split("\\")
    return {f"Level {idx}": parts[idx - 1] if idx <= len(parts) else "" for idx in range(1, 9)}


def _leap_fields(
    scenario: str,
    year: int,
    transport_type: str,
    vehicle_type: str,
    drive: str,
    fuel: str,
    parameter: str,
    value: float,
    parameter_detail: str,
) -> dict[str, object]:
    branch_path = _build_branch_path(
        transport_type=transport_type,
        vehicle_type=vehicle_type,
        drive=drive,
        fuel=fuel,
        parameter=parameter,
        parameter_detail=parameter_detail,
    )
    scale, units, per_unit = PARAMETER_TO_LEAP_METADATA[parameter]
    return {
        "Branch Path": branch_path,
        "Variable": PARAMETER_TO_LEAP_VARIABLE[parameter],
        "Scenario": _format_leap_scenario(scenario),
        "Region": "",
        "Scale": scale,
        "Units": units,
        "Per...": per_unit,
        "Year": year,
        "Value": round(float(value), 8),
    }


def _row(
    economy: EconomyInfo,
    scenario: str,
    year: int,
    transport_type: str,
    vehicle_type: str,
    drive: str,
    fuel: str,
    parameter: str,
    value: float,
    parameter_detail: str = "",
    notes: str = "",
) -> dict[str, object]:
    return {
        **_leap_fields(
            scenario=scenario,
            year=year,
            transport_type=transport_type,
            vehicle_type=vehicle_type,
            drive=drive,
            fuel=fuel,
            parameter=parameter,
            value=value,
            parameter_detail=parameter_detail,
        ),
        "Region": economy.name,
        "input_source": "default",
        "standardized_label_status": "standardized",
        "notes": notes,
        **_source_fields("Placeholder default. Replace with economy-specific researcher data when available."),
    }


def _long_defaults_to_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    metadata_cols = [column for column in MODULE1_INPUT_COLUMNS if column not in YEAR_COLUMNS]
    pivot_cols = [column for column in metadata_cols if column in long_df.columns]

    duplicate_key_cols = [*pivot_cols, "Year"]
    duplicate_rows = long_df.duplicated(subset=duplicate_key_cols, keep=False)
    if duplicate_rows.any():
        long_df = long_df.groupby(duplicate_key_cols, dropna=False, as_index=False)["Value"].sum()

    wide_df = (
        long_df.pivot(
            index=pivot_cols,
            columns="Year",
            values="Value",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    for year_col in YEAR_COLUMNS:
        year_int = int(year_col)
        if year_int in wide_df.columns:
            wide_df[year_col] = wide_df[year_int]
            wide_df.drop(columns=[year_int], inplace=True)
        elif year_col not in wide_df.columns:
            wide_df[year_col] = pd.NA

    return wide_df[MODULE1_INPUT_COLUMNS]


def build_default_assumptions(economy: EconomyInfo, scenarios: Iterable[str], years: Iterable[int]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for scenario in scenarios:
        for transport_type in ["passenger", "freight"]:
            rows.append(
                _row(
                    economy=economy,
                    scenario=scenario,
                    year=BASE_YEAR,
                    transport_type=transport_type,
                    vehicle_type="all",
                    drive="all",
                    fuel="all",
                    parameter="reconciliation_bound_lower",
                    value=0.85,
                )
            )
            rows.append(
                _row(
                    economy=economy,
                    scenario=scenario,
                    year=BASE_YEAR,
                    transport_type=transport_type,
                    vehicle_type="all",
                    drive="all",
                    fuel="all",
                    parameter="reconciliation_bound_upper",
                    value=1.15,
                )
            )
            rows.append(
                _row(
                    economy=economy,
                    scenario=scenario,
                    year=BASE_YEAR,
                    transport_type=transport_type,
                    vehicle_type="all",
                    drive="all",
                    fuel="all",
                    parameter="reconciliation_weight",
                    value=1.0,
                )
            )
            if transport_type == "passenger":
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type="all",
                        drive="all",
                        fuel="all",
                        parameter="passenger_saturation",
                        value=420,
                    )
                )
            for year in years:
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=year,
                        transport_type=transport_type,
                        vehicle_type="all",
                        drive="phev_gasoline",
                        fuel="all",
                        parameter="phev_electric_driving_share",
                        value=min(0.75, 0.45 * _year_multiplier(year, 0.01)),
                    )
                )
            for age in range(0, 31):
                if transport_type == "freight":
                    survival = max(0.0, 1 - (age / 28) ** 2.4)
                    vintage_weight = 0.91**age
                else:
                    survival = max(0.0, 1 - (age / 22) ** 2.2)
                    vintage_weight = 0.88**age

                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type="all",
                        drive="all",
                        fuel="all",
                        parameter="survival_rate",
                        parameter_detail=f"age_{age}",
                        value=survival,
                    )
                )
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type="all",
                        drive="all",
                        fuel="all",
                        parameter="vintage_profile_share",
                        parameter_detail=f"age_{age}",
                        value=vintage_weight,
                        notes="Normalize across ages before use.",
                    )
                )

        for transport_type, vehicle_type, vehicle_equivalent_weight, stock_share in VEHICLE_TYPES:
            if transport_type == "passenger":
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type=vehicle_type,
                        drive="all",
                        fuel="all",
                        parameter="vehicle_equivalent_weight",
                        value=vehicle_equivalent_weight,
                    )
                )

            base_stock = _base_stock_total(economy, transport_type) * stock_share
            drive_shares = _normalize_shares(DEFAULT_DRIVE_SHARES[vehicle_type])
            allowed_drives = VALID_DRIVES_BY_VEHICLE_TYPE.get(vehicle_type, set())
            if allowed_drives:
                drive_shares = {
                    drive: share
                    for drive, share in drive_shares.items()
                    if drive in allowed_drives
                }
                drive_shares = _normalize_shares(drive_shares)

            for year in years:
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=year,
                        transport_type=transport_type,
                        vehicle_type=vehicle_type,
                        drive="all",
                        fuel="all",
                        parameter="mileage",
                        value=MILEAGE_KM_PER_YEAR[vehicle_type] * _year_multiplier(year, -0.002),
                    )
                )

            for drive, fuel_share in drive_shares.items():
                fuel = DRIVE_FUEL_MAP[drive]
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type=vehicle_type,
                        drive=drive,
                        fuel=fuel,
                        parameter="base_year_stock",
                        value=base_stock * fuel_share,
                    )
                )
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type=vehicle_type,
                        drive=drive,
                        fuel=fuel,
                        parameter="current_sales_share",
                        value=fuel_share,
                    )
                )

                for year in years:
                    rows.append(
                        _row(
                            economy=economy,
                            scenario=scenario,
                            year=year,
                            transport_type=transport_type,
                            vehicle_type=vehicle_type,
                            drive=drive,
                            fuel=fuel,
                            parameter="efficiency",
                            value=EFFICIENCY_MJ_PER_KM[drive] * 100 * _year_multiplier(year, -0.006),
                        )
                    )

    long_df = pd.DataFrame(rows)
    return _long_defaults_to_wide(long_df)


def build_default_input_workbook_tables(
    scenarios: Iterable[str] = DEFAULT_SCENARIOS,
    years: Iterable[int] = DEFAULT_YEARS,
    phev_utilisation_source_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Build workbook-ready tables for the Road model default input workbook."""
    input_rows = []
    phev_report_rows = []

    for economy in get_economies():
        economy_df = build_default_assumptions(economy=economy, scenarios=scenarios, years=years)
        economy_df, phev_report = overlay_phev_utilisation_rates(
            default_filled_df=economy_df,
            economy=economy,
            source_path=phev_utilisation_source_path,
        )
        economy_df, _ = overlay_model_factor_sources(
            default_filled_df=economy_df,
            economy=economy,
        )
        input_rows.append(economy_df)
        phev_report_rows.append(phev_report)

    default_inputs = pd.concat(input_rows, ignore_index=True)
    phev_report = pd.concat(phev_report_rows, ignore_index=True)
    phev_source, _ = load_phev_utilisation_rates(phev_utilisation_source_path)

    return {
        ROAD_MODEL_DEFAULT_INPUT_SHEET: default_inputs[MODULE1_INPUT_COLUMNS],
        ROAD_MODEL_PHEV_UTILISATION_SHEET: phev_source,
        "phev_overlay_report": phev_report,
    }


def _normalize_module1_input_columns(input_df: pd.DataFrame) -> pd.DataFrame:
    rename_columns = {}
    for column in input_df.columns:
        column_as_text = str(column).strip()
        if column_as_text.endswith(".0") and column_as_text[:-2].isdigit():
            column_as_text = column_as_text[:-2]
        rename_columns[column] = column_as_text
    normalized_df = input_df.rename(columns=rename_columns).copy()

    missing_columns = [column for column in MODULE1_INPUT_COLUMNS if column not in normalized_df.columns]
    if missing_columns:
        raise ValueError("Road model default input workbook is missing columns: " + ", ".join(missing_columns))

    normalized_df = normalized_df[MODULE1_INPUT_COLUMNS].copy()
    normalized_df["Variable"] = normalized_df["Variable"].replace(
        {"Final On-Road Fuel Economy": "Fuel Economy"}
    )
    legacy_default_mask = (
        normalized_df["source_type"].astype(str).str.strip().eq("default_best_guess")
        & normalized_df["input_source"].astype(str).str.strip().isin(["", "provided"])
    )
    normalized_df.loc[legacy_default_mask, "input_source"] = "default"
    text_columns = [column for column in MODULE1_INPUT_COLUMNS if column not in YEAR_COLUMNS]
    for column in text_columns:
        normalized_df[column] = normalized_df[column].fillna("").astype(str).str.strip()
    for year_col in YEAR_COLUMNS:
        normalized_df[year_col] = pd.to_numeric(normalized_df[year_col], errors="coerce")
    normalized_df["researcher_review_recommended"] = normalized_df["researcher_review_recommended"].map(
        lambda value: str(value).strip().lower() in {"true", "1", "yes"}
        if not isinstance(value, bool)
        else value
    )
    return normalized_df


def load_default_input_workbook(
    workbook_path: str | Path = ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH,
    sheet_name: str = ROAD_MODEL_DEFAULT_INPUT_SHEET,
    require_exists: bool = False,
) -> pd.DataFrame:
    """Load the workbook-format Road model defaults used to seed per-economy packages."""
    workbook_path = Path(workbook_path)
    if not workbook_path.exists():
        if require_exists:
            raise FileNotFoundError(
                "Road model default input workbook was not found. "
                f"Expected file: {workbook_path}"
            )
        return pd.DataFrame(columns=MODULE1_INPUT_COLUMNS)

    workbook_df = pd.read_excel(workbook_path, sheet_name=sheet_name)
    workbook_df = _normalize_module1_input_columns(workbook_df)
    structure_report = validate_module1_input_structure(workbook_df)
    failed_checks = structure_report[structure_report["status"].eq("fail")]
    if not failed_checks.empty:
        details = "; ".join(
            f"{row.check_name}: {row.details}" for row in failed_checks.itertuples(index=False)
        )
        raise ValueError(f"Road model default input workbook failed structure validation: {details}")
    return workbook_df[MODULE1_INPUT_COLUMNS]


def build_schema_contract() -> pd.DataFrame:
    rows = []
    text_columns = {
        "Branch Path",
        "Variable",
        "Scenario",
        "Region",
        "Scale",
        "Units",
        "Per...",
        "input_source",
        "standardized_label_status",
        "notes",
        "source_type",
        "source_name",
        "source_scope",
        "source_date",
        "default_version",
        "review_reason",
    }
    integer_columns = set()
    boolean_columns = {"researcher_review_recommended"}

    for position, column_name in enumerate(MODULE1_INPUT_COLUMNS, start=1):
        if column_name in text_columns:
            expected_type = "string"
        elif column_name in integer_columns:
            expected_type = "integer"
        elif column_name in boolean_columns:
            expected_type = "boolean"
        elif column_name in YEAR_COLUMNS:
            expected_type = "number"
        else:
            expected_type = "unknown"

        rows.append(
            {
                "position": position,
                "column_name": column_name,
                "required": column_name in MODULE1_REQUIRED_COLUMNS,
                "expected_type": expected_type,
                "notes": "Researcher output files must keep this column name and meaning.",
            }
        )
    return pd.DataFrame(rows)


def validate_module1_input_structure(input_df: pd.DataFrame) -> pd.DataFrame:
    """Return a row-level structure report for default or researcher Road model files."""
    issues = []

    actual_columns = list(input_df.columns)
    missing_columns = [column for column in MODULE1_INPUT_COLUMNS if column not in actual_columns]
    unexpected_columns = [column for column in actual_columns if column not in MODULE1_INPUT_COLUMNS]

    if missing_columns:
        issues.append(
            {
                "check_name": "required_columns_present",
                "status": "fail",
                "issue_count": len(missing_columns),
                "details": "; ".join(missing_columns),
            }
        )
    else:
        issues.append(
            {
                "check_name": "required_columns_present",
                "status": "pass",
                "issue_count": 0,
                "details": "",
            }
        )

    if unexpected_columns:
        issues.append(
            {
                "check_name": "no_unexpected_columns",
                "status": "fail",
                "issue_count": len(unexpected_columns),
                "details": "; ".join(unexpected_columns),
            }
        )
    else:
        issues.append(
            {
                "check_name": "no_unexpected_columns",
                "status": "pass",
                "issue_count": 0,
                "details": "",
            }
        )

    if actual_columns == MODULE1_INPUT_COLUMNS:
        issues.append(
            {
                "check_name": "column_order_matches_contract",
                "status": "pass",
                "issue_count": 0,
                "details": "",
            }
        )
    else:
        issues.append(
            {
                "check_name": "column_order_matches_contract",
                "status": "fail",
                "issue_count": 1,
                "details": "Column names or order differ from MODULE1_INPUT_COLUMNS.",
            }
        )

    if not missing_columns:
        required_null_counts = input_df[MODULE1_REQUIRED_COLUMNS].isna().sum()
        required_null_counts = required_null_counts[required_null_counts > 0]
        issues.append(
            {
                "check_name": "required_values_populated",
                "status": "pass" if required_null_counts.empty else "fail",
                "issue_count": int(required_null_counts.sum()) if not required_null_counts.empty else 0,
                "details": "; ".join(f"{key}:{value}" for key, value in required_null_counts.items()),
            }
        )

        bad_value_count = 0
        for year_col in YEAR_COLUMNS:
            numeric_values = pd.to_numeric(input_df[year_col].dropna(), errors="coerce")
            bad_value_count += int(numeric_values.isna().sum())
        issues.append(
            {
                "check_name": "year_values_are_numeric",
                "status": "pass" if bad_value_count == 0 else "fail",
                "issue_count": bad_value_count,
                "details": "",
            }
        )

        bad_bounds_count, bad_bounds_details = _validate_module1_value_bounds(input_df)
        issues.append(
            {
                "check_name": "year_values_match_measure_bounds",
                "status": "pass" if bad_bounds_count == 0 else "fail",
                "issue_count": bad_bounds_count,
                "details": bad_bounds_details,
            }
        )

        bad_reconciliation_pairs_count, bad_reconciliation_pairs_details = (
            _validate_module1_reconciliation_bound_pairs(input_df)
        )
        issues.append(
            {
                "check_name": "reconciliation_lower_bound_not_above_upper_bound",
                "status": "pass" if bad_reconciliation_pairs_count == 0 else "fail",
                "issue_count": bad_reconciliation_pairs_count,
                "details": bad_reconciliation_pairs_details,
            }
        )

        duplicate_keys = input_df.duplicated(subset=MODULE1_KEY_COLUMNS, keep=False)
        issues.append(
            {
                "check_name": "module1_key_columns_are_unique",
                "status": "pass" if not duplicate_keys.any() else "fail",
                "issue_count": int(duplicate_keys.sum()),
                "details": "Key columns: " + "; ".join(MODULE1_KEY_COLUMNS),
            }
        )

        unknown_variables = sorted(set(input_df["Variable"]) - set(EXPECTED_UNITS_BY_VARIABLE))
        issues.append(
            {
                "check_name": "variables_are_known",
                "status": "pass" if not unknown_variables else "fail",
                "issue_count": len(unknown_variables),
                "details": "; ".join(unknown_variables),
            }
        )

        unit_mismatch = input_df["Units"] != input_df["Variable"].map(EXPECTED_UNITS_BY_VARIABLE)
        issues.append(
            {
                "check_name": "units_match_variable_contract",
                "status": "pass" if not unit_mismatch.any() else "fail",
                "issue_count": int(unit_mismatch.sum()),
                "details": "",
            }
        )

        bad_sources = sorted(set(input_df["input_source"]) - set(MODULE1_ALLOWED_INPUT_SOURCES))
        issues.append(
            {
                "check_name": "input_sources_are_known",
                "status": "pass" if not bad_sources else "fail",
                "issue_count": len(bad_sources),
                "details": "; ".join(bad_sources),
            }
        )

        bad_statuses = sorted(
            set(input_df["standardized_label_status"].dropna()) - set(MODULE1_ALLOWED_LABEL_STATUSES)
        )
        issues.append(
            {
                "check_name": "label_statuses_are_known",
                "status": "pass" if not bad_statuses else "fail",
                "issue_count": len(bad_statuses),
                "details": "; ".join(bad_statuses),
            }
        )

    return pd.DataFrame(issues)


def _workbook_check(check_name: str, passed: bool, issue_count: int = 0, details: str = "") -> dict[str, object]:
    return {
        "check_name": check_name,
        "status": "pass" if passed else "fail",
        "issue_count": int(issue_count),
        "details": details,
    }


def _validate_profile_sheet_layout(profile_df: pd.DataFrame) -> tuple[int, str]:
    if profile_df.empty:
        return 1, "Sheet is empty."
    first_col = profile_df.iloc[:, 0].fillna("").astype(str).str.strip()
    second_col = profile_df.iloc[:, 1].fillna("").astype(str).str.strip() if profile_df.shape[1] > 1 else pd.Series()
    area_count = int(first_col.eq("Area:").sum())
    profile_count = int(first_col.eq("Profile:").sum())
    header_count = int(first_col.eq("Year").sum() & second_col.eq("Value").sum()) if profile_df.shape[1] > 1 else 0
    issue_parts = []
    if area_count == 0:
        issue_parts.append("missing Area blocks")
    if profile_count == 0:
        issue_parts.append("missing Profile blocks")
    if header_count == 0:
        issue_parts.append("missing Year/Value headers")
    return len(issue_parts), "; ".join(issue_parts)


def validate_module1_workbook_structure(workbook_path: str | Path) -> pd.DataFrame:
    """Validate the one-workbook-per-economy Road Module 1 handoff contract."""
    workbook_path = Path(workbook_path)
    if not workbook_path.exists():
        return pd.DataFrame([_workbook_check("workbook_exists", False, 1, str(workbook_path))])

    issues = [_workbook_check("workbook_exists", True)]
    try:
        workbook = pd.ExcelFile(workbook_path)
    except Exception as exc:
        return pd.DataFrame(
            [
                _workbook_check("workbook_exists", True),
                _workbook_check("workbook_can_be_opened", False, 1, str(exc)),
            ]
        )

    sheet_names = workbook.sheet_names
    missing_sheets = [sheet for sheet in MODULE1_WORKBOOK_REQUIRED_SHEETS if sheet not in sheet_names]
    issues.append(
        _workbook_check(
            "required_sheets_present",
            not missing_sheets,
            len(missing_sheets),
            "; ".join(missing_sheets),
        )
    )
    if missing_sheets:
        return pd.DataFrame(issues)

    data_df = pd.read_excel(workbook_path, sheet_name="Data")
    details_df = pd.read_excel(workbook_path, sheet_name="Details")
    factors_df = pd.read_excel(workbook_path, sheet_name="Factors")
    lifecycle_df = pd.read_excel(workbook_path, sheet_name="Lifecycle", header=None)
    vintage_df = pd.read_excel(workbook_path, sheet_name="Vintage", header=None)

    issues.append(
        _workbook_check(
            "data_columns_match_contract",
            list(data_df.columns) == MODULE1_WORKBOOK_DATA_COLUMNS,
            0 if list(data_df.columns) == MODULE1_WORKBOOK_DATA_COLUMNS else 1,
            "" if list(data_df.columns) == MODULE1_WORKBOOK_DATA_COLUMNS else "Data sheet columns differ from MODULE1_WORKBOOK_DATA_COLUMNS.",
        )
    )
    issues.append(
        _workbook_check(
            "details_columns_match_contract",
            list(details_df.columns) == MODULE1_INPUT_COLUMNS,
            0 if list(details_df.columns) == MODULE1_INPUT_COLUMNS else 1,
            "" if list(details_df.columns) == MODULE1_INPUT_COLUMNS else "Details sheet columns differ from MODULE1_INPUT_COLUMNS.",
        )
    )
    issues.append(
        _workbook_check(
            "factors_columns_match_contract",
            list(factors_df.columns) == MODULE1_WORKBOOK_FACTOR_COLUMNS,
            0 if list(factors_df.columns) == MODULE1_WORKBOOK_FACTOR_COLUMNS else 1,
            "" if list(factors_df.columns) == MODULE1_WORKBOOK_FACTOR_COLUMNS else "Factors sheet columns differ from MODULE1_WORKBOOK_FACTOR_COLUMNS.",
        )
    )

    if list(details_df.columns) == MODULE1_INPUT_COLUMNS:
        flat_report = validate_module1_input_structure(_normalize_module1_input_columns(details_df))
        for report_row in flat_report.to_dict(orient="records"):
            report_row["check_name"] = "details_" + str(report_row["check_name"])
            issues.append(report_row)

    if list(data_df.columns) == MODULE1_WORKBOOK_DATA_COLUMNS and list(details_df.columns) == MODULE1_INPUT_COLUMNS:
        comparable_details = details_df[MODULE1_WORKBOOK_DATA_COLUMNS].copy()
        data_matches_details = data_df.fillna("").equals(comparable_details.fillna(""))
        issues.append(
            _workbook_check(
                "data_rows_match_details",
                data_matches_details,
                0 if data_matches_details else 1,
                "" if data_matches_details else "Data sheet should equal the LEAP-facing columns from Details.",
            )
        )

    lifecycle_issues, lifecycle_details = _validate_profile_sheet_layout(lifecycle_df)
    issues.append(_workbook_check("lifecycle_sheet_layout_valid", lifecycle_issues == 0, lifecycle_issues, lifecycle_details))
    vintage_issues, vintage_details = _validate_profile_sheet_layout(vintage_df)
    issues.append(_workbook_check("vintage_sheet_layout_valid", vintage_issues == 0, vintage_issues, vintage_details))

    return pd.DataFrame(issues)


def build_source_flags(default_filled_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Branch Path",
        "Variable",
        "Scenario",
        "Region",
        "input_source",
        "source_type",
        "source_name",
        "source_scope",
        "source_date",
        "default_version",
        "researcher_review_recommended",
        "review_reason",
    ]
    return default_filled_df[columns].copy()


def build_missing_data_report(default_filled_df: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["Region", "Scenario", "Variable", "input_source"]
    report = default_filled_df.groupby(group_cols, dropna=False).size().reset_index(name="row_count")
    report["missing_field"] = "researcher_value"
    report["action_taken"] = "provided_value_inserted"
    report["severity"] = "review_needed"
    report["notes"] = "The Road model provided-values package is being used for these rows."
    return report[
        [
            "Region",
            "Scenario",
            "Variable",
            "missing_field",
            "input_source",
            "row_count",
            "action_taken",
            "severity",
            "notes",
        ]
    ]


def build_unit_check_report(default_filled_df: pd.DataFrame) -> pd.DataFrame:
    report = default_filled_df[[*MODULE1_KEY_COLUMNS, "Units"]].copy()
    report["expected_unit"] = report["Variable"].map(EXPECTED_UNITS_BY_VARIABLE)
    report["unit_check_status"] = report.apply(
        lambda row: "pass" if row["Units"] == row["expected_unit"] else "fail",
        axis=1,
    )
    report["notes"] = ""
    return report


def build_researcher_review_flags(default_filled_df: pd.DataFrame) -> pd.DataFrame:
    flags = default_filled_df[default_filled_df["researcher_review_recommended"]].copy()
    return flags[
        [
            *MODULE1_KEY_COLUMNS,
            *YEAR_COLUMNS,
            "Units",
            "review_reason",
            "notes",
        ]
    ]


def validate_module1_value_for_variable(variable: str, value: float) -> str:
    """Return a validation message for a single value, or an empty string if valid."""
    if not isfinite(value):
        return f"{variable} must be a finite number."

    rule = MODULE1_VALUE_VALIDATION_RULES.get(variable)
    if not rule:
        return ""

    minimum = rule.get("min")
    maximum = rule.get("max")
    if minimum is not None and value < minimum:
        return f"{variable} must be greater than or equal to {minimum}."
    if maximum is not None and value > maximum:
        return f"{variable} must be less than or equal to {maximum}."
    return ""


def _build_module1_value_validation_details(violations: list[str], sample_size: int = 10) -> str:
    if not violations:
        return ""
    shown = violations[:sample_size]
    suffix = "" if len(violations) <= sample_size else f"; plus {len(violations) - sample_size} more"
    return "; ".join(shown) + suffix


def _validate_module1_value_bounds(input_df: pd.DataFrame) -> tuple[int, str]:
    violations = []
    for row_idx, row in input_df.iterrows():
        variable = str(row.get("Variable", ""))
        if variable not in MODULE1_VALUE_VALIDATION_RULES:
            continue
        for year_col in YEAR_COLUMNS:
            raw_value = row.get(year_col)
            if pd.isna(raw_value) or str(raw_value).strip() == "":
                continue
            numeric_value = pd.to_numeric(raw_value, errors="coerce")
            if pd.isna(numeric_value):
                continue
            message = validate_module1_value_for_variable(variable, float(numeric_value))
            if message:
                branch = row.get("Branch Path", "")
                violations.append(f"row {row_idx + 2}, {year_col}, {branch}, {message}")

    return len(violations), _build_module1_value_validation_details(violations)


def _validate_module1_reconciliation_bound_pairs(input_df: pd.DataFrame) -> tuple[int, str]:
    bound_rows = input_df[
        input_df["Variable"].isin(["Reconciliation Bound Lower", "Reconciliation Bound Upper"])
    ].copy()
    if bound_rows.empty:
        return 0, ""

    compare_cols = ["Branch Path", "Scenario", "Region"]
    lower_df = bound_rows[bound_rows["Variable"] == "Reconciliation Bound Lower"].set_index(compare_cols)
    upper_df = bound_rows[bound_rows["Variable"] == "Reconciliation Bound Upper"].set_index(compare_cols)
    common_keys = lower_df.index.intersection(upper_df.index)
    violations = []

    for key in common_keys:
        lower_row = lower_df.loc[key]
        upper_row = upper_df.loc[key]
        if isinstance(lower_row, pd.DataFrame):
            lower_row = lower_row.iloc[0]
        if isinstance(upper_row, pd.DataFrame):
            upper_row = upper_row.iloc[0]

        for year_col in YEAR_COLUMNS:
            lower_value = pd.to_numeric(lower_row.get(year_col), errors="coerce")
            upper_value = pd.to_numeric(upper_row.get(year_col), errors="coerce")
            if pd.isna(lower_value) or pd.isna(upper_value):
                continue
            if float(lower_value) > float(upper_value):
                branch, scenario, region = key
                violations.append(
                    f"{year_col}, {branch}, {scenario}, {region}: lower {lower_value} exceeds upper {upper_value}"
                )

    return len(violations), _build_module1_value_validation_details(violations)


def build_default_catalog() -> pd.DataFrame:
    rows = []
    for variable, unit in EXPECTED_UNITS_BY_VARIABLE.items():
        rows.append(
            {
                "Variable": variable,
                "Units": unit,
                "source_type": "default_best_guess",
                "source_name": "APERC placeholder road defaults",
                "source_scope": "all_apec_economies_until_researcher_update",
                "source_date": SOURCE_DATE,
                "default_version": DEFAULT_VERSION,
                "researcher_review_recommended": False,
                "notes": "Editable provided-values catalog entry. Replace with documented source before production use.",
            }
        )
    return pd.DataFrame(rows)


def write_economy_package(
    economy: EconomyInfo,
    output_root: Path,
    scenarios: Iterable[str] = DEFAULT_SCENARIOS,
    years: Iterable[int] = DEFAULT_YEARS,
    default_input_df: pd.DataFrame | None = None,
) -> dict[str, Path]:
    economy_dir = output_root / DEFAULT_VERSION / economy.code
    economy_dir.mkdir(parents=True, exist_ok=True)

    if default_input_df is not None and not default_input_df.empty:
        source_regions = _transport_leap_source_regions(economy)
        default_filled = default_input_df[default_input_df["Region"].isin(source_regions)].copy()
        scenario_names = {_format_leap_scenario(scenario) for scenario in scenarios}
        default_filled = default_filled[default_filled["Scenario"].isin(scenario_names)].copy()
        if default_filled.empty:
            raise ValueError(f"No Road model default input workbook rows found for {economy.code}.")
        default_filled["Region"] = economy.name
        default_filled = default_filled[MODULE1_INPUT_COLUMNS]
    else:
        default_filled = build_default_assumptions(economy=economy, scenarios=scenarios, years=years)
        default_filled, _ = overlay_phev_utilisation_rates(default_filled_df=default_filled, economy=economy)

    # Harmonize legacy naming/scopes from seed workbooks to the current policy:
    # - Use Fuel Economy variable name.
    # - Keep HEV/EREV only for LPV branches.
    # - Remove truck PHEV rows.
    default_filled["Variable"] = default_filled["Variable"].replace(
        {"Final On-Road Fuel Economy": "Fuel Economy"}
    )
    branch_series = default_filled["Branch Path"].astype(str)
    is_hev_or_erev = branch_series.str.contains(r"\\(?:HEV|EREV)(?:\\|$)", regex=True)
    is_lpv_branch = branch_series.str.startswith("Demand\\Passenger road\\LPVs\\")
    is_truck_phev = branch_series.str.startswith("Demand\\Freight road\\Trucks\\") & branch_series.str.contains(
        r"\\PHEV(?:\\|$)",
        regex=True,
    )
    is_motorcycle_invalid_drive = (
        branch_series.str.startswith("Demand\\Passenger road\\Motorcycles\\")
        & branch_series.str.contains(r"\\(?:HEV|PHEV|FCEV)(?:\\|$)", regex=True)
    )
    default_filled = default_filled[
        ~((is_hev_or_erev & ~is_lpv_branch) | is_truck_phev | is_motorcycle_invalid_drive)
    ].copy()

    # Vehicle equivalent weights are only required for passenger branches.
    # If the seed workbook includes legacy freight rows, remove them so this
    # factor remains passenger-only in generated defaults.
    default_filled = default_filled[
        ~(
            default_filled["Variable"].eq("Vehicle Equivalent Weight")
            & default_filled["Branch Path"].astype(str).str.startswith("Demand\\Freight road")
        )
    ].copy()

    default_filled, transport_leap_overlay_report = overlay_transport_leap_export_values(
        default_filled_df=default_filled,
        economy=economy,
    )
    default_filled, model_factor_overlay_report = overlay_model_factor_sources(
        default_filled_df=default_filled,
        economy=economy,
    )
    default_filled, profile_overlay_report = overlay_survival_and_vintage_profiles(
        default_filled_df=default_filled,
        economy=economy,
    )
    # Temporary policy: deactivate researcher-review prioritization globally so
    # all rows are presented equally for manual review.
    default_filled["researcher_review_recommended"] = False
    default_filled["review_reason"] = ""

    model_factor_for_overlay_report = model_factor_overlay_report.rename(columns={"source_file": "source_region"}).copy()
    model_factor_for_overlay_report["source_scenario"] = ""
    model_factor_for_overlay_report["years_overlaid"] = str(BASE_YEAR)

    profile_for_overlay_report = profile_overlay_report.rename(columns={"source_file": "source_region"}).copy()
    profile_for_overlay_report["source_scenario"] = ""
    profile_for_overlay_report["years_overlaid"] = str(BASE_YEAR)

    transport_leap_overlay_report = pd.concat(
        [
            transport_leap_overlay_report,
            model_factor_for_overlay_report[[
                "status",
                "Branch Path",
                "Variable",
                "Scenario",
                "Region",
                "source_region",
                "source_scenario",
                "years_overlaid",
                "details",
            ]],
            profile_for_overlay_report[[
                "status",
                "Branch Path",
                "Variable",
                "Scenario",
                "Region",
                "source_region",
                "source_scenario",
                "years_overlaid",
                "details",
            ]],
        ],
        ignore_index=True,
    )
    source_flags = build_source_flags(default_filled)
    missing_report = build_missing_data_report(default_filled)
    unit_report = build_unit_check_report(default_filled)
    review_flags = build_researcher_review_flags(default_filled)
    structure_report = validate_module1_input_structure(default_filled)

    paths = {
        "default_filled_inputs": economy_dir / "road_module1_default_filled_inputs.csv",
    }

    # Remove old artifacts from prior runs so each economy folder stays CSV-only.
    for extra_file in economy_dir.glob("road_module1_*.csv"):
        if extra_file.name != paths["default_filled_inputs"].name:
            extra_file.unlink(missing_ok=True)

    for extra_file in economy_dir.glob("road_module1_*.xlsx"):
        extra_file.unlink(missing_ok=True)

    default_filled.to_csv(paths["default_filled_inputs"], index=False)

    # Keep these variables computed for optional debugging/use in interactive sessions.
    _ = (
        source_flags,
        transport_leap_overlay_report,
        missing_report,
        unit_report,
        structure_report,
        review_flags,
    )

    return paths


def write_all_economy_packages(
    output_root: str | Path = "outputs/road_module1_defaults",
    scenarios: Iterable[str] = DEFAULT_SCENARIOS,
    years: Iterable[int] = DEFAULT_YEARS,
    default_input_workbook_path: str | Path = ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH,
    require_default_input_workbook: bool = False,
) -> dict[str, dict[str, Path]]:
    output_root = Path(output_root)
    version_root = output_root / DEFAULT_VERSION
    version_root.mkdir(parents=True, exist_ok=True)
    default_input_df = pd.DataFrame()

    catalog_path = version_root / "road_module1_default_assumptions_catalog.csv"
    build_default_catalog().to_csv(catalog_path, index=False)

    schema_contract_path = version_root / "road_module1_input_schema_contract.csv"
    build_schema_contract().to_csv(schema_contract_path, index=False)

    all_paths = {}
    for economy in get_economies():
        all_paths[economy.code] = write_economy_package(
            economy=economy,
            output_root=output_root,
            scenarios=scenarios,
            years=years,
            default_input_df=default_input_df,
        )
        all_paths[economy.code]["default_catalog"] = catalog_path
        all_paths[economy.code]["input_schema_contract"] = schema_contract_path

    manifest_rows = []
    for economy_code, paths in all_paths.items():
        for file_type, path in paths.items():
            if file_type not in MODULE1_CORE_OUTPUT_FILE_TYPES:
                continue
            manifest_rows.append(
                {
                    "default_version": DEFAULT_VERSION,
                    "economy": economy_code,
                    "file_type": file_type,
                    "path": str(path),
                }
            )
    manifest_path = version_root / "road_module1_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)

    return all_paths


def list_default_versions(output_root: str | Path = "outputs/road_module1_defaults") -> list[str]:
    output_root = ROAD_MODULE1_DEFAULTS_OUTPUT_ROOT if output_root == "outputs/road_module1_defaults" else Path(output_root)
    if not output_root.exists():
        return []
    return sorted([path.name for path in output_root.iterdir() if path.is_dir()])


def list_default_economies(
    version: str = DEFAULT_VERSION,
    output_root: str | Path = "outputs/road_module1_defaults",
) -> list[dict[str, str]]:
    output_root = ROAD_MODULE1_DEFAULTS_OUTPUT_ROOT if output_root == "outputs/road_module1_defaults" else Path(output_root)
    version_root = output_root / version
    if not version_root.exists():
        return []

    economy_name_lookup = {economy.code: economy.name for economy in get_economies()}
    economies = []
    for economy_dir in sorted([path for path in version_root.iterdir() if path.is_dir()]):
        economies.append(
            {
                "economy": economy_dir.name,
                "economy_name": economy_name_lookup.get(economy_dir.name, economy_dir.name),
            }
        )
    return economies


def load_default_filled_inputs(
    economy: str,
    version: str = DEFAULT_VERSION,
    output_root: str | Path = "outputs/road_module1_defaults",
) -> pd.DataFrame:
    workbook_path = get_default_input_workbook_path(economy=economy, version=version, output_root=output_root)
    if workbook_path.exists():
        workbook_df = pd.read_excel(workbook_path, sheet_name="Details")
        return _normalize_module1_input_columns(workbook_df)

    filepath = get_default_filled_inputs_path(economy=economy, version=version, output_root=output_root)
    if not filepath.exists():
        raise FileNotFoundError(f"Default-filled Road model input workbook or CSV not found: {workbook_path} / {filepath}")
    return pd.read_csv(filepath)


def get_default_input_workbook_path(
    economy: str,
    version: str = DEFAULT_VERSION,
    output_root: str | Path = "outputs/road_module1_defaults",
) -> Path:
    output_root = ROAD_MODULE1_DEFAULTS_OUTPUT_ROOT if output_root == "outputs/road_module1_defaults" else Path(output_root)
    return output_root / version / economy / f"road_module1_inputs_{economy}.xlsx"


def get_default_filled_inputs_path(
    economy: str,
    version: str = DEFAULT_VERSION,
    output_root: str | Path = "outputs/road_module1_defaults",
) -> Path:
    output_root = ROAD_MODULE1_DEFAULTS_OUTPUT_ROOT if output_root == "outputs/road_module1_defaults" else Path(output_root)
    return output_root / version / economy / "road_module1_default_filled_inputs.csv"


def get_economy_info(economy_code: str) -> EconomyInfo:
    for economy in get_economies():
        if economy.code == economy_code:
            return economy
    raise ValueError(f"Unknown economy code: {economy_code}")


def load_builtin_transport_leap_provided_values(
    economy: str,
    version: str = DEFAULT_VERSION,
    output_root: str | Path = "outputs/road_module1_defaults",
) -> tuple[pd.DataFrame, pd.DataFrame, Path | None]:
    default_filled_df = load_default_filled_inputs(
        economy=economy,
        version=version,
        output_root=output_root,
    )
    workbook_path = find_transport_leap_export_path(economy=economy)
    overlaid_df, overlay_report = overlay_transport_leap_export_values(
        default_filled_df=default_filled_df,
        economy=get_economy_info(economy),
        workbook_path=workbook_path,
    )
    return overlaid_df, overlay_report, workbook_path


def normalize_provided_values_file(provided_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a user-provided file that follows the default-filled input structure."""
    normalized_df = provided_df.copy()
    rename_columns = {}
    for column in normalized_df.columns:
        column_as_text = str(column).strip()
        if column_as_text.endswith(".0") and column_as_text[:-2].isdigit():
            column_as_text = column_as_text[:-2]
        rename_columns[column] = column_as_text
    normalized_df = normalized_df.rename(columns=rename_columns)

    provided_year_columns = [column for column in YEAR_COLUMNS if column in normalized_df.columns]
    required_columns = [*MODULE1_KEY_COLUMNS, str(BASE_YEAR)]
    missing_columns = [column for column in required_columns if column not in normalized_df.columns]
    if missing_columns:
        raise ValueError("Provided values file is missing required columns: " + ", ".join(missing_columns))
    if not provided_year_columns:
        raise ValueError("Provided values file must include at least one supported year column.")

    for column in MODULE1_KEY_COLUMNS:
        normalized_df[column] = normalized_df[column].fillna("").astype(str).str.strip()
    for year_col in provided_year_columns:
        normalized_df[year_col] = pd.to_numeric(normalized_df[year_col], errors="coerce")

    return normalized_df


def apply_provided_values_file(
    default_filled_df: pd.DataFrame,
    provided_df: pd.DataFrame,
    source_name: str = "uploaded_provided_values_file",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Overlay uploaded provided values onto the generated provided-value template."""
    completed_df = default_filled_df.copy()
    for year_col in YEAR_COLUMNS:
        completed_df[year_col] = pd.to_numeric(completed_df[year_col], errors="coerce")

    normalized_provided_df = normalize_provided_values_file(provided_df)
    provided_year_columns = [column for column in YEAR_COLUMNS if column in normalized_provided_df.columns]
    key_to_index = {_override_key(row): idx for idx, row in completed_df.iterrows()}
    report_rows = []

    for _, provided_row in normalized_provided_df.iterrows():
        key = _override_key(provided_row)
        target_idx = key_to_index.get(key)
        if target_idx is None:
            report_rows.append(
                {
                    "status": "fail",
                    "issue": "provided_key_not_found",
                    "details": str({column: provided_row[column] for column in MODULE1_KEY_COLUMNS}),
                }
            )
            continue

        applied_years = []
        for year_col in provided_year_columns:
            provided_value = provided_row[year_col]
            if pd.isna(provided_value):
                continue
            completed_df.at[target_idx, year_col] = float(provided_value)
            applied_years.append(year_col)

        if not applied_years:
            continue

        completed_df.at[target_idx, "input_source"] = "provided"
        completed_df.at[target_idx, "source_type"] = "researcher_provided_file"
        completed_df.at[target_idx, "source_name"] = source_name
        completed_df.at[target_idx, "source_date"] = datetime.now().strftime("%Y-%m-%d")
        completed_df.at[target_idx, "researcher_review_recommended"] = False
        completed_df.at[target_idx, "review_reason"] = ""
        existing_notes = str(completed_df.at[target_idx, "notes"] or "").strip()
        upload_note = "Provided values file overlay applied."
        completed_df.at[target_idx, "notes"] = f"{existing_notes} {upload_note}".strip()
        report_rows.append(
            {
                "status": "applied",
                "issue": "",
                "details": f"{';'.join(applied_years)}: {key}",
            }
        )

    report_df = pd.DataFrame(report_rows)
    if report_df.empty:
        report_df = pd.DataFrame(columns=["status", "issue", "details"])

    return completed_df[MODULE1_INPUT_COLUMNS], report_df


def _override_key(row: pd.Series | dict[str, object]) -> tuple[object, ...]:
    return tuple(row[column] for column in MODULE1_KEY_COLUMNS)


def _write_csv_with_locked_file_fallback(df: pd.DataFrame, filepath: Path) -> Path:
    try:
        df.to_csv(filepath, index=False)
        return filepath
    except PermissionError:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_path = filepath.with_name(f"{filepath.stem}_{timestamp}{filepath.suffix}")
        df.to_csv(fallback_path, index=False)
        return fallback_path


def _write_excel_with_locked_file_fallback(df: pd.DataFrame, filepath: Path, sheet_name: str) -> Path:
    try:
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
        return filepath
    except PermissionError:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_path = filepath.with_name(f"{filepath.stem}_{timestamp}{filepath.suffix}")
        with pd.ExcelWriter(fallback_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
        return fallback_path


def _write_module1_workbook_with_locked_file_fallback(
    workbook_tables: dict[str, pd.DataFrame],
    filepath: Path,
) -> Path:
    try:
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            for sheet_name, table_df in workbook_tables.items():
                write_header = sheet_name not in {"Lifecycle", "Vintage"}
                table_df.to_excel(writer, sheet_name=sheet_name, index=False, header=write_header)
        return filepath
    except PermissionError:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_path = filepath.with_name(f"{filepath.stem}_{timestamp}{filepath.suffix}")
        with pd.ExcelWriter(fallback_path, engine="openpyxl") as writer:
            for sheet_name, table_df in workbook_tables.items():
                write_header = sheet_name not in {"Lifecycle", "Vintage"}
                table_df.to_excel(writer, sheet_name=sheet_name, index=False, header=write_header)
        return fallback_path


def _extract_age_from_branch_path(branch_path: str) -> int | None:
    last_part = str(branch_path or "").split("\\")[-1]
    if not last_part.lower().startswith("age "):
        return None
    try:
        return int(last_part.split(" ", 1)[1])
    except (IndexError, ValueError):
        return None


def _extract_transport_label_from_branch_path(branch_path: str) -> str:
    parts = str(branch_path or "").split("\\")
    if len(parts) > 1 and parts[1] == "Passenger road":
        return "passenger"
    if len(parts) > 1 and parts[1] == "Freight road":
        return "freight"
    return "road"


def _first_profile_value(row: pd.Series) -> float | None:
    for year_col in YEAR_COLUMNS:
        if year_col not in row or pd.isna(row[year_col]):
            continue
        try:
            return float(row[year_col])
        except (TypeError, ValueError):
            continue
    return None


def _format_lifecycle_area_name(economy: str) -> str:
    economy_suffix = str(economy)[2:] if len(str(economy)) > 2 else str(economy)
    return f"{economy_suffix} transport"


def _build_lifecycle_profile_excel_df(area_name: str, profile_name: str, profile: dict[int, float]) -> pd.DataFrame:
    rows = [
        ["Area:", area_name],
        ["Profile:", profile_name],
        [None, None],
        ["Year", "Value"],
    ]
    for age in sorted(profile):
        rows.append([age, profile[age]])
    return pd.DataFrame(rows)


def _build_lifecycle_profiles_from_completed_inputs(
    completed_df: pd.DataFrame,
    variable: str,
    *,
    normalize_to_percent: bool,
) -> dict[str, dict[int, float]]:
    profile_rows = completed_df[completed_df["Variable"].eq(variable)].copy()
    profiles: dict[str, dict[int, float]] = {}

    for _, row in profile_rows.iterrows():
        age = _extract_age_from_branch_path(row["Branch Path"])
        value = _first_profile_value(row)
        if age is None or value is None:
            continue
        transport_label = _extract_transport_label_from_branch_path(row["Branch Path"])
        profiles.setdefault(transport_label, {})[age] = value

    if normalize_to_percent:
        for transport_label, profile in profiles.items():
            total = sum(max(float(value), 0.0) for value in profile.values())
            if total <= 0:
                continue
            profiles[transport_label] = {
                age: max(float(value), 0.0) / total * 100
                for age, value in profile.items()
            }
    else:
        for transport_label, profile in profiles.items():
            max_value = max([float(value) for value in profile.values()], default=0.0)
            scale = 100 if max_value <= 1.5 else 1
            profiles[transport_label] = {
                age: float(value) * scale
                for age, value in profile.items()
            }

    return profiles


def _profile_sheet_from_completed_inputs(
    completed_df: pd.DataFrame,
    *,
    economy: str,
    variable: str,
    profile_suffix: str,
    normalize_to_percent: bool,
) -> pd.DataFrame:
    area_name = _format_lifecycle_area_name(economy)
    profiles = _build_lifecycle_profiles_from_completed_inputs(
        completed_df=completed_df,
        variable=variable,
        normalize_to_percent=normalize_to_percent,
    )
    rows = []
    for transport_label in ["passenger", "freight", *sorted(set(profiles) - {"passenger", "freight"})]:
        profile = profiles.get(transport_label, {})
        if not profile:
            continue
        if rows:
            rows.append([None, None])
        rows.extend(
            _build_lifecycle_profile_excel_df(
                area_name=area_name,
                profile_name=f"{transport_label.title()} road {profile_suffix}",
                profile=profile,
            ).values.tolist()
        )
    if not rows:
        rows = [["Area:", area_name], ["Profile:", profile_suffix], [None, None], ["Year", "Value"]]
    return pd.DataFrame(rows)


def _parameter_name_from_variable(variable: str) -> str:
    return str(variable or "").strip().lower().replace("-", " ").replace("/", " ").replace(" ", "_")


def _extract_vehicle_label_from_branch_path(branch_path: str) -> str:
    parts = [part for part in str(branch_path or "").split("\\") if part]
    if len(parts) <= 2:
        return "all"
    if parts[-1].lower().startswith("age "):
        return "all"
    if parts[2] in {"LPVs", "Buses", "Motorcycles", "LCVs", "Trucks"}:
        return parts[2]
    return "all"


def build_module1_factors_sheet(completed_df: pd.DataFrame) -> pd.DataFrame:
    factor_variables = {
        "PHEV Electric Driving Share",
        "Reconciliation Bound Lower",
        "Reconciliation Bound Upper",
        "Reconciliation Weight",
    }
    rows = []
    factor_rows = completed_df[completed_df["Variable"].isin(factor_variables)].copy()

    for _, row in factor_rows.iterrows():
        value = row.get(str(BASE_YEAR))
        if pd.isna(value):
            value = _first_profile_value(row)
        rows.append(
            {
                "Parameter": _parameter_name_from_variable(row["Variable"]),
                "Transport Type": _extract_transport_label_from_branch_path(row["Branch Path"]),
                "Vehicle Type": _extract_vehicle_label_from_branch_path(row["Branch Path"]),
                "Scenario": row["Scenario"],
                "Value": value,
                "Unit": row["Units"],
                "Notes": row.get("notes", ""),
            }
        )

    return pd.DataFrame(rows, columns=MODULE1_WORKBOOK_FACTOR_COLUMNS)


def build_module1_input_workbook_tables(
    completed_df: pd.DataFrame,
    economy: str,
    data_columns: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    details_df = completed_df[MODULE1_INPUT_COLUMNS].copy()
    data_df = details_df[data_columns or MODULE1_WORKBOOK_DATA_COLUMNS].copy()
    lifecycle_df = _profile_sheet_from_completed_inputs(
        completed_df=details_df,
        economy=economy,
        variable="Survival Rate",
        profile_suffix="survival",
        normalize_to_percent=False,
    )
    vintage_df = _profile_sheet_from_completed_inputs(
        completed_df=details_df,
        economy=economy,
        variable="Vintage Profile Share",
        profile_suffix="vintage",
        normalize_to_percent=True,
    )
    factors_df = build_module1_factors_sheet(details_df)
    return {
        "Data": data_df,
        "Lifecycle": lifecycle_df,
        "Vintage": vintage_df,
        "Factors": factors_df,
        "Details": details_df,
    }


def write_module1_input_workbook(
    completed_df: pd.DataFrame,
    economy: str,
    filepath: Path,
    data_columns: list[str] | None = None,
) -> Path:
    workbook_tables = build_module1_input_workbook_tables(
        completed_df=completed_df,
        economy=economy,
        data_columns=data_columns,
    )
    return _write_module1_workbook_with_locked_file_fallback(workbook_tables=workbook_tables, filepath=filepath)


def write_lifecycle_profile_exports(
    completed_df: pd.DataFrame,
    economy: str,
    output_dir: Path,
) -> dict[str, str]:
    area_name = _format_lifecycle_area_name(economy)
    lifecycle_paths: dict[str, str] = {}
    profile_specs = [
        (
            "survival",
            "Survival Rate",
            "Vehicle Survival (Road model)",
            False,
        ),
        (
            "vintage",
            "Vintage Profile Share",
            "Vehicle Vintage Profile (Road model)",
            True,
        ),
    ]

    for file_prefix, variable, profile_name, normalize_to_percent in profile_specs:
        profiles = _build_lifecycle_profiles_from_completed_inputs(
            completed_df=completed_df,
            variable=variable,
            normalize_to_percent=normalize_to_percent,
        )
        for transport_label, profile in profiles.items():
            if not profile:
                continue
            filename = f"road_module1_{file_prefix}_lifecycle_profile_{transport_label}.xlsx"
            filepath = output_dir / filename
            excel_df = _build_lifecycle_profile_excel_df(
                area_name=area_name,
                profile_name=f"{profile_name} - {transport_label.title()} road",
                profile=profile,
            )
            saved_path = _write_excel_with_locked_file_fallback(
                df=excel_df,
                filepath=filepath,
                sheet_name="Lifecycle Profiles",
            )
            lifecycle_paths[f"{file_prefix}_{transport_label}_path"] = str(saved_path.resolve())

    return lifecycle_paths


def apply_researcher_overrides(
    default_filled_df: pd.DataFrame,
    overrides: list[dict[str, object]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    completed_df = default_filled_df.copy()
    for year_col in YEAR_COLUMNS:
        completed_df[year_col] = pd.to_numeric(completed_df[year_col], errors="coerce")

    key_to_index = {_override_key(row): idx for idx, row in completed_df.iterrows()}
    applied_rows = []
    issues = []

    for override in overrides:
        key_payload = override.get("key", {})
        year = str(override.get("year", "")).strip()
        raw_value = override.get("value", None)
        comment = str(override.get("comment", "") or "").strip()

        if raw_value is None or str(raw_value).strip() == "":
            continue

        if year not in YEAR_COLUMNS:
            issues.append(
                {
                    "status": "fail",
                    "issue": "unknown_year_column",
                    "details": f"{year}: {key_payload}",
                }
            )
            continue

        try:
            parsed_value = float(raw_value)
        except (TypeError, ValueError):
            issues.append(
                {
                    "status": "fail",
                    "issue": "non_numeric_override",
                    "details": str(key_payload),
                }
            )
            continue

        try:
            key = tuple(key_payload[column] for column in MODULE1_KEY_COLUMNS)
        except KeyError as exc:
            issues.append(
                {
                    "status": "fail",
                    "issue": "missing_key_column",
                    "details": f"{exc}: {key_payload}",
                }
            )
            continue

        target_idx = key_to_index.get(key)
        if target_idx is None:
            issues.append(
                {
                    "status": "fail",
                    "issue": "override_key_not_found",
                    "details": str(key_payload),
                }
            )
            continue

        target_variable = str(completed_df.at[target_idx, "Variable"])
        validation_error = validate_module1_value_for_variable(target_variable, parsed_value)
        if validation_error:
            issues.append(
                {
                    "status": "fail",
                    "issue": "value_outside_measure_bounds",
                    "details": f"{year}: {validation_error} {key_payload}",
                }
            )
            continue

        completed_df.at[target_idx, year] = parsed_value
        completed_df.at[target_idx, "input_source"] = "researcher_override"
        completed_df.at[target_idx, "source_type"] = "researcher_input"
        completed_df.at[target_idx, "source_name"] = "website_researcher_form"
        completed_df.at[target_idx, "source_date"] = datetime.now().strftime("%Y-%m-%d")
        completed_df.at[target_idx, "researcher_review_recommended"] = False
        completed_df.at[target_idx, "review_reason"] = ""
        if comment:
            completed_df.at[target_idx, "notes"] = comment

        applied_rows.append(
            {
                "status": "applied",
                "issue": "",
                "details": f"{year}: {key_payload}",
            }
        )

    issue_report = pd.DataFrame(applied_rows + issues)
    if issue_report.empty:
        issue_report = pd.DataFrame(columns=["status", "issue", "details"])

    return completed_df[MODULE1_INPUT_COLUMNS], issue_report


def write_researcher_completed_package(
    economy: str,
    version: str,
    overrides: list[dict[str, object]],
    defaults_root: str | Path = "outputs/road_module1_defaults",
    output_root: str | Path = "outputs/road_module1_researcher_outputs",
) -> dict[str, object]:
    default_filled_df = load_default_filled_inputs(
        economy=economy,
        version=version,
        output_root=defaults_root,
    )
    completed_df, override_report = apply_researcher_overrides(
        default_filled_df=default_filled_df,
        overrides=overrides,
    )

    output_root = (
        ROAD_MODULE1_RESEARCHER_OUTPUT_ROOT
        if output_root == "outputs/road_module1_researcher_outputs"
        else Path(output_root)
    )
    output_dir = output_root / version / economy
    output_dir.mkdir(parents=True, exist_ok=True)

    workbook_path = output_dir / f"road_module1_inputs_{economy}.xlsx"

    workbook_path = write_module1_input_workbook(
        completed_df=completed_df,
        economy=economy,
        filepath=workbook_path,
        data_columns=MODULE1_WORKBOOK_RESEARCHER_DATA_COLUMNS,
    )
    cleanup_patterns = [
        "road_module1_researcher_completed_inputs*.csv",
        "road_module1_researcher_output_structure_validation_report*.csv",
        "road_module1_researcher_output_workbook_structure_validation_report*.csv",
        "road_module1_researcher_override_report*.csv",
        "road_module1_*_lifecycle_profile_*.xlsx",
    ]
    for pattern in cleanup_patterns:
        for old_output in output_dir.glob(pattern):
            try:
                old_output.unlink(missing_ok=True)
            except PermissionError:
                pass

    override_issue_count = int(override_report["status"].eq("fail").sum()) if not override_report.empty else 0
    validation_passed = override_issue_count == 0

    return {
        "status": "success" if validation_passed and override_issue_count == 0 else "validation_error",
        "completed_inputs_path": str(workbook_path.resolve()),
        "rows_written": len(completed_df),
        "overrides_applied": int(override_report["status"].eq("applied").sum()) if not override_report.empty else 0,
        "override_issue_count": override_issue_count,
        "structure_validation_passed": validation_passed,
    }
