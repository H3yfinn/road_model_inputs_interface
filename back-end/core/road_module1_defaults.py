from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from html import escape
from math import isfinite
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_VERSION = "v2026_06_05_road_module1_sources"
SOURCE_DATE = "2026-05-25"
BASE_YEAR = 2022
DEFAULT_SCENARIOS = ["current_accounts"]
DEFAULT_YEARS = [2022]
YEAR_COLUMNS = [str(year) for year in DEFAULT_YEARS]
# Future years where stock-share trajectories are anchored for researchers to edit.
STOCK_SHARE_PROJECTION_YEARS = [2040, 2060]
TRANSPORT_LEAP_EXPORT_ALL_ECONS_PATTERN = "transport_leap_export_combined_ALL_ECONS*.xlsx"
TRANSPORT_LEAP_EXPORT_SHEET = "FOR_VIEWING"
TRANSPORT_LEAP_EXPORT_HEADER_ROW = 2
TRANSPORT_LEAP_EXPORT_SCENARIO_PRIORITY = ["Current Accounts", "Target"]
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

import os

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

# Support env var overrides for web deployment; default to local paths
_data_root_env = os.getenv("ROAD_MODEL_DATA_ROOT")
DATA_ROOT = Path(_data_root_env) if _data_root_env else BACKEND_ROOT / "data"

_output_root_env = os.getenv("ROAD_MODEL_OUTPUT_ROOT")
_output_root = Path(_output_root_env) if _output_root_env else BACKEND_ROOT / "outputs"

MULTINODE_BACKEND_DATA_DIR = DATA_ROOT / "multinodeenergy_backend"
ROAD_MODEL_DATA_DIR = DATA_ROOT / "road_model"
TRANSPORT_LEAP_EXPORT_DIR = ROAD_MODEL_DATA_DIR / "leap_import_workbooks"
PROCESSED_SOURCE_DIR = ROAD_MODEL_DATA_DIR / "processed_source"
SUPPLEMENTAL_SOURCE_DIR = ROAD_MODEL_DATA_DIR / "supplemental_source_files"
MANUALLY_FILLED_ROWS_DIR = ROAD_MODEL_DATA_DIR / "manually_filled_rows"
SOURCE_PRIORITY_PATH = ROAD_MODEL_DATA_DIR / "road_module1_source_priorities.csv"
ROAD_MODULE1_DEFAULTS_OUTPUT_ROOT = _output_root / "road_module1_defaults"
ROAD_MODULE1_RESEARCHER_OUTPUT_ROOT = _output_root / "road_module1_researcher_outputs"
ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH = ROAD_MODEL_DATA_DIR / "road_model_default_input_workbook.xlsx"
ROAD_MODEL_DEFAULT_INPUT_SHEET = "road_model_default_inputs"
ROAD_MODEL_PHEV_UTILISATION_SHEET = "phev_utilisation_source"
PHEV_UTILISATION_SOURCE_CSV = SUPPLEMENTAL_SOURCE_DIR / "apec_phev_utilisation_rates.csv"
PASSENGER_SATURATION_SOURCE_CSV = SUPPLEMENTAL_SOURCE_DIR / "apec_passenger_vehicle_saturation.csv"
RECONCILIATION_FACTORS_SOURCE_CSV = SUPPLEMENTAL_SOURCE_DIR / "apec_reconciliation_factors.csv"
VEHICLE_EQUIVALENT_WEIGHTS_SOURCE_CSV = SUPPLEMENTAL_SOURCE_DIR / "apec_vehicle_equivalent_weights.csv"
SURVIVAL_PROFILE_SOURCE_XLSX = SUPPLEMENTAL_SOURCE_DIR / "vehicle_survival_modified_00_APEC.xlsx"
VINTAGE_PROFILE_SOURCE_XLSX = SUPPLEMENTAL_SOURCE_DIR / "vintage_modelled_from_survival_00_APEC.xlsx"
LIFECYCLE_PROFILE_FACTORS_SOURCE_CSV = SUPPLEMENTAL_SOURCE_DIR / "apec_lifecycle_profile_factors.csv"


def _read_required_csv(path: Path, required_columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            "Required Road Module 1 source file was not found: "
            f"{path}. Populate back-end/data/road_model before generating defaults."
        )
    df = pd.read_csv(path)
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing required columns: {', '.join(missing)}"
        )
    return df


def _assumption_value(key: str, default: float = 0.0) -> float:
    return float(_DEFAULT_ASSUMPTIONS.get(key, default))




_DEFAULT_ASSUMPTIONS: dict[str, float] = {}

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

# Population is intentionally not required for the strict, source-backed
# Module 1 workflow (workbook + overlays). Keep a zero-population fallback for
# legacy synthetic defaults paths only.
ECONOMIES = [
    (economy_code, region_names[0], 0.0)
    for economy_code, region_names in ECONOMY_CODE_TO_LEAP_REGION_NAMES.items()
]

VEHICLE_TYPES: list[tuple[str, str, float, float]] = []

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

DEFAULT_DRIVE_SHARES: dict[str, dict[str, float]] = {}

DEFAULT_GASOLINE_DIESEL_SHARE_TOLERANCE = float(
    _assumption_value("gasoline_diesel_share_tolerance", 0.0)
)

# Explicitly constrain which drive types are valid for each vehicle type in
# Module 1 default generation. This prevents placeholder rows for combinations
# that are out of scope in the current road data tree.
VALID_DRIVES_BY_VEHICLE_TYPE: dict[str, set[str]] = {}

MILEAGE_KM_PER_YEAR: dict[str, float] = {}

EFFICIENCY_MJ_PER_KM: dict[str, float] = {}

EXPECTED_UNITS = {
    "base_year_stock": "vehicles",
    "current_sales_share": "share",
    "efficiency": "MJ_per_100km",
    "mileage": "vehicle_km_per_vehicle",
    "passenger_saturation": "vehicles_per_1000_people",
    "passenger_saturation_reached": "boolean",
    "phev_electric_driving_share": "share",
    "reconciliation_bound_lower": "share",
    "reconciliation_bound_upper": "share",
    "reconciliation_weight": "weight",
    "survival_rate": "share",
    "vehicle_equivalent_weight": "vehicle_equivalent",
    "vehicle_equivalent_weight_lower_bound": "vehicle_equivalent",
    "vehicle_equivalent_weight_upper_bound": "vehicle_equivalent",
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

MODULE1_LONG_KEY_COLUMNS = [
    "Economy",
    "Scenario",
    "Branch Path",
    "Variable",
    "Year",
]

MODULE1_LONG_VALUE_COLUMNS = [
    "Value",
    "Units",
    "Source",
    "Comment",
]

MODULE1_LONG_COLUMNS = [
    *MODULE1_LONG_KEY_COLUMNS,
    *MODULE1_LONG_VALUE_COLUMNS,
]

VEHICLE_TYPE_STOCK_SHARE_BRANCHES = {
    "passenger": [
        "Demand\\Passenger road\\Motorcycles",
        "Demand\\Passenger road\\Buses",
        "Demand\\Passenger road\\LPVs",
    ],
    "freight": [
        "Demand\\Freight road\\Trucks",
        "Demand\\Freight road\\LCVs",
    ],
}

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
    "gasoline_diesel_share_tolerance": "Gasoline/Diesel Share Tolerance",
    "mileage": "Mileage",
    "passenger_saturation": "Passenger Vehicle Saturation",
    "passenger_saturation_reached": "Passenger Saturation Reached",
    "phev_electric_driving_share": "PHEV Electric Driving Share",
    "reconciliation_weight_stock": "Reconciliation Weight Stock",
    "reconciliation_weight_mileage": "Reconciliation Weight Mileage",
    "reconciliation_weight_efficiency": "Reconciliation Weight Efficiency",
    "reconciliation_bound_lower_mileage": "Reconciliation Bound Lower Mileage",
    "reconciliation_bound_upper_mileage": "Reconciliation Bound Upper Mileage",
    "reconciliation_bound_lower_efficiency": "Reconciliation Bound Lower Efficiency",
    "reconciliation_bound_upper_efficiency": "Reconciliation Bound Upper Efficiency",
    "survival_rate": "Survival Rate",
    "turnover_rate_bound_lower": "Turnover Rate Bound Lower",
    "turnover_rate_bound_upper": "Turnover Rate Bound Upper",
    "vehicle_equivalent_weight": "Vehicle Equivalent Weight",
    "vehicle_equivalent_weight_lower_bound": "Vehicle Equivalent Weight Lower Bound",
    "vehicle_equivalent_weight_upper_bound": "Vehicle Equivalent Weight Upper Bound",
    "vintage_profile_share": "Vintage Profile Share",
}

PARAMETER_TO_LEAP_METADATA = {
    "base_year_stock": ("", "Device", ""),
    "current_sales_share": ("%", "Share", ""),
    "efficiency": ("", "MJ/100 km", ""),
    "gasoline_diesel_share_tolerance": ("%", "Share", ""),
    "mileage": ("", "Kilometer", ""),
    "passenger_saturation": ("", "Device", "1000 people"),
    "passenger_saturation_reached": ("", "Boolean", ""),
    "phev_electric_driving_share": ("%", "Share", ""),
    "reconciliation_weight_stock": ("", "Weight", ""),
    "reconciliation_weight_mileage": ("", "Weight", ""),
    "reconciliation_weight_efficiency": ("", "Weight", ""),
    "reconciliation_bound_lower_mileage": ("%", "Share", ""),
    "reconciliation_bound_upper_mileage": ("%", "Share", ""),
    "reconciliation_bound_lower_efficiency": ("%", "Share", ""),
    "reconciliation_bound_upper_efficiency": ("%", "Share", ""),
    "survival_rate": ("%", "Share", ""),
    "turnover_rate_bound_lower": ("%", "Share", ""),
    "turnover_rate_bound_upper": ("%", "Share", ""),
    "vehicle_equivalent_weight": ("", "Vehicle equivalent", ""),
    "vehicle_equivalent_weight_lower_bound": ("", "Vehicle equivalent", ""),
    "vehicle_equivalent_weight_upper_bound": ("", "Vehicle equivalent", ""),
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
    "Gasoline/Diesel Share Tolerance": {
        "min": 0,
        "max": 100,
        "description": "Gasoline/Diesel Share Tolerance must be between 0 and 100.",
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
    "Passenger Saturation Reached": {
        "min": 0,
        "max": 1,
        "description": "Passenger Saturation Reached must be 0 or 1.",
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
    "Vehicle Equivalent Weight Lower Bound": {
        "min": 0,
        "description": "Vehicle Equivalent Weight Lower Bound cannot be negative.",
    },
    "Vehicle Equivalent Weight Upper Bound": {
        "min": 0,
        "description": "Vehicle Equivalent Weight Upper Bound cannot be negative.",
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


def _economies_from_default_input(default_input_df: pd.DataFrame) -> list[EconomyInfo]:
    if default_input_df is None or default_input_df.empty or "Region" not in default_input_df.columns:
        return []

    regions = (
        default_input_df["Region"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda s: s.ne("")]
        .unique()
        .tolist()
    )
    economies: list[EconomyInfo] = []
    seen: set[str] = set()
    for region in regions:
        code = LEAP_REGION_NAME_TO_ECONOMY_CODE.get(region)
        if not code or code in seen:
            continue
        canonical_name = ECONOMY_CODE_TO_LEAP_REGION_NAMES.get(code, [region])[0]
        economies.append(EconomyInfo(code=code, name=canonical_name, population_million=0.0))
        seen.add(code)
    return economies


def _base_stock_total(economy: EconomyInfo, transport_type: str) -> float:
    population = economy.population_million * 1_000_000
    if population <= 0:
        return 0.0
    if transport_type == "passenger":
        return population * _assumption_value("base_stock_multiplier.passenger", 0.0)
    return population * _assumption_value("base_stock_multiplier.freight", 0.0)


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


def _stamp_row_source(
    df: pd.DataFrame,
    idx: int,
    *,
    source_type: str,
    source_name: str,
    source_scope: str,
    source_date: str = "",
    note: str = "",
) -> None:
    df.at[idx, "input_source"] = "provided"
    df.at[idx, "source_type"] = source_type
    df.at[idx, "source_name"] = source_name
    df.at[idx, "source_scope"] = source_scope
    df.at[idx, "source_date"] = source_date
    df.at[idx, "researcher_review_recommended"] = False
    df.at[idx, "review_reason"] = ""
    df.at[idx, "notes"] = note


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
    """Load PHEV electric utilisation rates from the source CSV.

    Supports both the legacy single-rate-per-economy format and the current
    per-vehicle-type format (vehicle_type column with values "LPVs" / "LCVs").
    """
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


def _phev_rate_for_branch(
    source_rows: pd.DataFrame,
    branch_path: str,
    economy_code: str,
) -> tuple[float, pd.Series] | tuple[None, None]:
    """Return (rate, source_row) matched by the vehicle type in the branch path.

    Looks for an exact vehicle_type match in the PHEV utilisation CSV.  If no
    row exists for that vehicle type (e.g. Buses, Motorcycles), returns None so
    the branch is skipped rather than inheriting a wrong rate.
    """
    has_vt = "vehicle_type" in source_rows.columns and source_rows["vehicle_type"].notna().any()
    if has_vt:
        parts = str(branch_path).split("\\")
        # vehicle type is parts[2] (Demand\Transport road\VehicleType\...)
        vehicle_type = parts[2] if len(parts) > 2 else ""
        vt_rows = source_rows[source_rows["vehicle_type"] == vehicle_type]
        if vt_rows.empty:
            return None, None
        source_row = vt_rows.iloc[0]
    else:
        source_row = source_rows.iloc[0]
    rate = source_row["phev_utilisation_rate"]
    if pd.isna(rate):
        return None, None
    return float(rate), source_row


def overlay_phev_utilisation_rates(
    default_filled_df: pd.DataFrame,
    economy: EconomyInfo,
    source_path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the PHEV utilisation CSV for base-year PHEV electric driving share rows.

    When the source CSV has a vehicle_type column, applies LPVs rate to passenger
    branch paths and LCVs rate to freight branch paths. Falls back to a single
    economy-level rate when no vehicle_type column is present.
    """
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

    overlaid_df = default_filled_df.copy()
    target_mask = overlaid_df["Variable"].eq("PHEV Electric Driving Share")
    report_rows = []

    # If PHEV Electric Driving Share rows are absent (e.g. source is a raw LEAP
    # export that doesn't include supplemental rows), infer the PHEV parent branches
    # from existing data and build fully-populated rows directly from source_rows.
    # Every value comes from the apec_phev_utilisation_rates CSV — nothing is generated.
    if not target_mask.any():
        branch_series = overlaid_df["Branch Path"].astype(str)
        # Match any branch where a path segment is exactly "PHEV" or starts with
        # "PHEV " (e.g. "PHEV large", "PHEV medium", "PHEV small").
        phev_child_mask = branch_series.str.contains(r"\\PHEV(?:\s+\S+)?\\", regex=True, na=False)

        def _phev_parent(bp: str) -> str:
            parts = bp.split("\\")
            idx = next(
                (i for i, p in enumerate(parts) if p == "PHEV" or p.startswith("PHEV ")),
                None,
            )
            return "\\".join(parts[: idx + 1]) if idx is not None else ""

        phev_parent_branches = [
            p for p in
            branch_series[phev_child_mask].map(_phev_parent).unique().tolist()
            if p
        ]
        scenarios = overlaid_df["Scenario"].dropna().unique().tolist() or ["Current Accounts"]
        new_rows: list[dict] = []
        for branch_path in phev_parent_branches:
            rate, source_row = _phev_rate_for_branch(source_rows, branch_path, economy.code)
            if rate is None:
                report_rows.append({
                    "status": "skipped",
                    "Branch Path": branch_path,
                    "Variable": "PHEV Electric Driving Share",
                    "Scenario": "",
                    "Region": economy.name,
                    "source_year": "",
                    "details": "No matching vehicle_type row in source.",
                })
                continue
            note = (
                f"PHEV utilisation rate from {resolved_path.name}; source data_year "
                f"{int(source_row['data_year']) if not pd.isna(source_row['data_year']) else ''}; "
                f"evidence_grade {source_row['evidence_grade']}; "
                f"range {source_row['lower_rate']}-{source_row['upper_rate']}; "
                f"{source_row['estimation_status']}. Future-year changes are handled by LEAP adjustment variables."
            )
            for scenario in scenarios:
                new_row = {column: pd.NA for column in MODULE1_INPUT_COLUMNS}
                new_row.update({
                    "Branch Path": branch_path,
                    "Variable": "PHEV Electric Driving Share",
                    "Scenario": scenario,
                    "Region": economy.name,
                    "Scale": "%",
                    "Units": "Share",
                    "Per...": "",
                    str(BASE_YEAR): rate,
                    "input_source": "provided",
                    "source_type": "apec_phev_utilisation_rates",
                    "source_name": resolved_path.name,
                    "source_scope": economy.code,
                    "source_date": str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else "",
                    "notes": note,
                    "standardized_label_status": "standardized",
                    "researcher_review_recommended": False,
                    "review_reason": "",
                })
                report_rows.append({
                    "status": "applied",
                    "Branch Path": branch_path,
                    "Variable": "PHEV Electric Driving Share",
                    "Scenario": scenario,
                    "Region": economy.name,
                    "source_year": new_row["source_date"],
                    "details": f"{BASE_YEAR}={rate}",
                })
                new_rows.append(new_row)
        if new_rows:
            overlaid_df = pd.concat([overlaid_df, pd.DataFrame(new_rows)], ignore_index=True)
            target_mask = overlaid_df["Variable"].eq("PHEV Electric Driving Share")

    for idx in overlaid_df[target_mask].index:
        branch_path = overlaid_df.at[idx, "Branch Path"]
        rate, source_row = _phev_rate_for_branch(source_rows, branch_path, economy.code)
        if rate is None:
            report_rows.append({
                "status": "skipped",
                "Branch Path": branch_path,
                "Variable": "PHEV Electric Driving Share",
                "Scenario": overlaid_df.at[idx, "Scenario"],
                "Region": economy.name,
                "source_year": "",
                "details": "No matching vehicle_type row in source.",
            })
            continue
        note = (
            f"PHEV utilisation rate from {resolved_path.name}; source data_year "
            f"{int(source_row['data_year']) if not pd.isna(source_row['data_year']) else ''}; "
            f"evidence_grade {source_row['evidence_grade']}; "
            f"range {source_row['lower_rate']}-{source_row['upper_rate']}; "
            f"{source_row['estimation_status']}. Future-year changes are handled by LEAP adjustment variables."
        )
        overlaid_df.at[idx, str(BASE_YEAR)] = rate
        for year_col in YEAR_COLUMNS:
            if int(year_col) > BASE_YEAR:
                overlaid_df.at[idx, year_col] = pd.NA
        _stamp_row_source(overlaid_df, idx, source_type="apec_phev_utilisation_rates", source_name=resolved_path.name, source_scope=economy.code, source_date=str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else "", note=note)
        report_rows.append({
            "status": "applied",
            "Branch Path": branch_path,
            "Variable": "PHEV Electric Driving Share",
            "Scenario": overlaid_df.at[idx, "Scenario"],
            "Region": economy.name,
            "source_year": overlaid_df.at[idx, "source_date"],
            "details": f"{BASE_YEAR}={rate}",
        })

    return overlaid_df[MODULE1_INPUT_COLUMNS], pd.DataFrame(report_rows)


def load_lifecycle_profile_factors(source_path: str | Path | None = None) -> tuple[pd.DataFrame, Path | None]:
    """Load APEC-wide and economy-level lifecycle calibration factors from the source CSV."""
    resolved_path: Path | None = None
    if source_path is not None:
        resolved_path = Path(source_path) if Path(source_path).exists() else None
    else:
        if LIFECYCLE_PROFILE_FACTORS_SOURCE_CSV.exists():
            resolved_path = LIFECYCLE_PROFILE_FACTORS_SOURCE_CSV

    if resolved_path is None:
        return pd.DataFrame(), None

    df = pd.read_csv(resolved_path)
    numeric_cols = [
        "data_year",
        "turnover_rate_lower",
        "turnover_rate_upper",
        "scale_age_band_age_min",
        "scale_age_band_age_max",
        "scale_age_band_factor",
        "smoothing_window",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["project_code", "economy", "transport_type", "fit_mode"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df, resolved_path


def overlay_lifecycle_profile_factors(
    default_filled_df: pd.DataFrame,
    economy: "EconomyInfo",
    source_path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Update Turnover Rate Bound Lower / Upper rows using apec_lifecycle_profile_factors.csv.

    Economy-specific rows (matched by project_code) take priority over blank APEC defaults.
    """
    lf_df, resolved_path = load_lifecycle_profile_factors(source_path)
    if lf_df.empty or resolved_path is None:
        return default_filled_df, pd.DataFrame(
            [
                {
                    "status": "skipped",
                    "Variable": "Turnover Rate Bound",
                    "Region": economy.name,
                    "details": "Lifecycle profile factors CSV was not found.",
                }
            ]
        )

    economy_norm = economy.code.replace("_", "").upper()
    economy_rows = lf_df[lf_df["project_code"].str.replace("_", "").str.upper() == economy_norm]
    apec_rows = lf_df[lf_df["project_code"] == ""]

    report_rows = []
    overlaid_df = default_filled_df.copy()

    for transport_type in ["passenger", "freight"]:
        # Economy-specific overrides APEC default for this transport type
        econ_tt = economy_rows[economy_rows["transport_type"] == transport_type]
        apec_tt = apec_rows[apec_rows["transport_type"] == transport_type]
        source_row_candidates = econ_tt if not econ_tt.empty else apec_tt
        if source_row_candidates.empty:
            report_rows.append(
                {
                    "status": "skipped",
                    "Variable": "Turnover Rate Bound",
                    "Region": economy.name,
                    "transport_type": transport_type,
                    "details": "No lifecycle factors row found.",
                }
            )
            continue

        source_row = source_row_candidates.iloc[0]
        lower = source_row.get("turnover_rate_lower")
        upper = source_row.get("turnover_rate_upper")
        data_year = source_row.get("data_year")
        evidence_grade = source_row.get("evidence_grade", "")
        estimation_status = source_row.get("estimation_status", "")

        road_branch = "Passenger road" if transport_type == "passenger" else "Freight road"
        note = (
            f"Lifecycle calibration bounds from {resolved_path.name}; "
            f"data_year {int(data_year) if not pd.isna(data_year) else ''}; "
            f"evidence_grade {evidence_grade}; {estimation_status}. "
            f"Used by Module 4 to calibrate survival curves to implied turnover rate."
        )

        for variable, value in [
            ("Turnover Rate Bound Lower", lower),
            ("Turnover Rate Bound Upper", upper),
        ]:
            if pd.isna(value):
                continue
            target_mask = (
                overlaid_df["Variable"].eq(variable)
                & overlaid_df["Branch Path"].astype(str).str.startswith(f"Demand\\{road_branch}")
            )
            for idx in overlaid_df[target_mask].index:
                overlaid_df.at[idx, str(BASE_YEAR)] = float(value)
                _stamp_row_source(overlaid_df, idx, source_type="apec_lifecycle_profile_factors", source_name=resolved_path.name, source_scope=economy.code, source_date=str(int(data_year)) if not pd.isna(data_year) else "", note=note)
                report_rows.append(
                    {
                        "status": "applied",
                        "Variable": variable,
                        "Region": economy.name,
                        "transport_type": transport_type,
                        "details": f"{BASE_YEAR}={float(value)}",
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
        "reached_saturation_lenient",
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
    saturation_df["reached_saturation_lenient"] = (
        saturation_df["reached_saturation_lenient"]
        .fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes", "y", "reached", "saturated"})
    )
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
    _RECONCILIATION_NUMERIC_COLUMNS = [
        "weight_stock",
        "weight_mileage",
        "weight_efficiency",
        "bound_lower_mileage",
        "bound_upper_mileage",
        "bound_lower_efficiency",
        "bound_upper_efficiency",
        "data_year",
    ]
    required_columns = ["transport_type"] + _RECONCILIATION_NUMERIC_COLUMNS
    missing_columns = [column for column in required_columns if column not in factors_df.columns]
    if missing_columns:
        raise ValueError(
            "Reconciliation factors CSV is missing required columns: " + ", ".join(missing_columns)
        )

    factors_df = factors_df.copy()
    factors_df["transport_type"] = factors_df["transport_type"].fillna("").astype(str).str.strip().str.lower()
    for column in _RECONCILIATION_NUMERIC_COLUMNS:
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
    required_columns = ["vehicle_type", "vehicle_equivalent_weight", "lower_bound", "upper_bound", "data_year"]
    missing_columns = [column for column in required_columns if column not in weights_df.columns]
    if missing_columns:
        raise ValueError(
            "Vehicle equivalent weights CSV is missing required columns: " + ", ".join(missing_columns)
        )

    weights_df = weights_df.copy()
    weights_df["vehicle_type"] = weights_df["vehicle_type"].fillna("").astype(str).str.strip().str.lower()
    for column in ["vehicle_equivalent_weight", "lower_bound", "upper_bound", "data_year"]:
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
            reached_saturation_value = 1.0 if bool(source_row["reached_saturation_lenient"]) else 0.0
            if pd.isna(saturation_value):
                raise ValueError(f"Passenger saturation is missing for {economy.code}.")

            target_mask = (
                overlaid_df["Variable"].eq("Passenger Vehicle Saturation")
                & overlaid_df["Branch Path"].eq("Demand\\Passenger road")
            )
            # Create the row if it doesn't exist (e.g. raw LEAP export source),
            # populating the value directly from the saturation CSV.
            if not target_mask.any():
                scenarios = overlaid_df["Scenario"].dropna().unique().tolist() or ["Current Accounts"]
                new_rows = []
                for scenario in scenarios:
                    new_row = {column: pd.NA for column in MODULE1_INPUT_COLUMNS}
                    new_row.update({
                        "Branch Path": "Demand\\Passenger road",
                        "Variable": "Passenger Vehicle Saturation",
                        "Scenario": scenario,
                        "Region": economy.name,
                        "Scale": "",
                        "Units": "Device",
                        "Per...": "1000 people",
                        str(BASE_YEAR): float(saturation_value),
                        "input_source": "provided",
                        "source_type": "apec_passenger_saturation",
                        "source_name": saturation_path.name,
                        "source_scope": economy.code,
                        "source_date": str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else "",
                        "notes": (
                            f"Passenger saturation from {saturation_path.name}; "
                            f"lower={source_row['lower_bound']}, upper={source_row['upper_bound']}, "
                            f"grade={source_row['evidence_grade']}, status={source_row['estimation_status']}."
                        ),
                        "standardized_label_status": "standardized",
                        "researcher_review_recommended": False,
                        "review_reason": "",
                    })
                    new_rows.append(new_row)
                if new_rows:
                    overlaid_df = pd.concat([overlaid_df, pd.DataFrame(new_rows)], ignore_index=True)
                    target_mask = (
                        overlaid_df["Variable"].eq("Passenger Vehicle Saturation")
                        & overlaid_df["Branch Path"].eq("Demand\\Passenger road")
                    )
            for idx in overlaid_df[target_mask].index:
                overlaid_df.at[idx, str(BASE_YEAR)] = float(saturation_value)
                for year_col in YEAR_COLUMNS:
                    if int(year_col) > BASE_YEAR:
                        overlaid_df.at[idx, year_col] = pd.NA
                _stamp_row_source(overlaid_df, idx, source_type="apec_passenger_saturation", source_name=saturation_path.name, source_scope=economy.code, source_date=str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else "", note=(
                    f"Passenger saturation from {saturation_path.name}; "
                    f"lower={source_row['lower_bound']}, upper={source_row['upper_bound']}, "
                    f"grade={source_row['evidence_grade']}, "
                    f"status={source_row['estimation_status']}."
                ))
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

            reached_target_mask = (
                overlaid_df["Variable"].eq("Passenger Saturation Reached")
                & overlaid_df["Branch Path"].eq("Demand\\Passenger road")
            )
            if not reached_target_mask.any():
                scenarios = overlaid_df.loc[target_mask, "Scenario"].dropna().unique().tolist()
                if not scenarios:
                    scenarios = overlaid_df["Scenario"].dropna().unique().tolist()
                new_rows = []
                for scenario in scenarios:
                    new_row = {column: pd.NA for column in MODULE1_INPUT_COLUMNS}
                    new_row.update(
                        {
                            "Branch Path": "Demand\\Passenger road",
                            "Variable": "Passenger Saturation Reached",
                            "Scenario": scenario,
                            "Region": economy.name,
                            "Scale": "",
                            "Units": "Boolean",
                            "Per...": "",
                            str(BASE_YEAR): reached_saturation_value,
                        }
                    )
                    new_rows.append(new_row)
                if new_rows:
                    overlaid_df = pd.concat([overlaid_df, pd.DataFrame(new_rows)], ignore_index=True)
                    reached_target_mask = (
                        overlaid_df["Variable"].eq("Passenger Saturation Reached")
                        & overlaid_df["Branch Path"].eq("Demand\\Passenger road")
                    )

            for idx in overlaid_df[reached_target_mask].index:
                overlaid_df.at[idx, str(BASE_YEAR)] = reached_saturation_value
                for year_col in YEAR_COLUMNS:
                    if int(year_col) > BASE_YEAR:
                        overlaid_df.at[idx, year_col] = pd.NA
                _stamp_row_source(overlaid_df, idx, source_type="apec_passenger_saturation", source_name=saturation_path.name, source_scope=economy.code, source_date=str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else "", note=f"Lenient passenger saturation reached flag from {saturation_path.name}; reached_saturation_lenient={bool(source_row['reached_saturation_lenient'])}.")
                report_rows.append(
                    {
                        "status": "applied",
                        "Branch Path": overlaid_df.at[idx, "Branch Path"],
                        "Variable": "Passenger Saturation Reached",
                        "Scenario": overlaid_df.at[idx, "Scenario"],
                        "Region": economy.name,
                        "source_file": saturation_path.name,
                        "details": f"{BASE_YEAR}={reached_saturation_value}",
                    }
                )

    reconciliation_df, reconciliation_path = load_reconciliation_factors(reconciliation_source_path)
    if reconciliation_df.empty or reconciliation_path is None:
        report_rows.append(
            {
                "status": "skipped",
                "Branch Path": "Demand\\Passenger road;Demand\\Freight road",
                "Variable": "Reconciliation Weight/Bound per component",
                "Scenario": "",
                "Region": economy.name,
                "source_file": "",
                "details": "Reconciliation factors source CSV not found.",
            }
        )
    else:
        _LEAP_VAR_TO_CSV_COL = {
            "Reconciliation Weight Stock": "weight_stock",
            "Reconciliation Weight Mileage": "weight_mileage",
            "Reconciliation Weight Efficiency": "weight_efficiency",
            "Reconciliation Bound Lower Mileage": "bound_lower_mileage",
            "Reconciliation Bound Upper Mileage": "bound_upper_mileage",
            "Reconciliation Bound Lower Efficiency": "bound_lower_efficiency",
            "Reconciliation Bound Upper Efficiency": "bound_upper_efficiency",
        }
        reconciliation_by_transport = {
            row["transport_type"]: row
            for _, row in reconciliation_df.iterrows()
            if row["transport_type"] in {"passenger", "freight"}
        }
        # Create reconciliation rows for transport branches where they are absent,
        # populating values directly from reconciliation_by_transport (CSV source).
        _TRANSPORT_BRANCH = {
            "passenger": "Demand\\Passenger road",
            "freight":   "Demand\\Freight road",
        }
        scenarios = overlaid_df["Scenario"].dropna().unique().tolist() or ["Current Accounts"]
        for transport_type, branch_path in _TRANSPORT_BRANCH.items():
            source_row = reconciliation_by_transport.get(transport_type)
            if source_row is None:
                continue
            for variable, csv_col in _LEAP_VAR_TO_CSV_COL.items():
                source_value = source_row[csv_col]
                if pd.isna(source_value):
                    continue
                for scenario in scenarios:
                    already_exists = (
                        overlaid_df["Branch Path"].eq(branch_path)
                        & overlaid_df["Variable"].eq(variable)
                        & overlaid_df["Scenario"].eq(scenario)
                    ).any()
                    if already_exists:
                        continue
                    new_row = {column: pd.NA for column in MODULE1_INPUT_COLUMNS}
                    new_row.update({
                        "Branch Path": branch_path,
                        "Variable": variable,
                        "Scenario": scenario,
                        "Region": economy.name,
                        "Scale": "",
                        "Units": "Weight" if "Weight" in variable else "Share",
                        "Per...": "",
                        str(BASE_YEAR): float(source_value),
                        "input_source": "provided",
                        "source_type": "apec_reconciliation_factors",
                        "source_name": reconciliation_path.name,
                        "source_scope": transport_type,
                        "source_date": str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else "",
                        "notes": f"Reconciliation factor from {reconciliation_path.name} ({transport_type}).",
                        "standardized_label_status": "standardized",
                        "researcher_review_recommended": False,
                        "review_reason": "",
                    })
                    overlaid_df = pd.concat([overlaid_df, pd.DataFrame([new_row])], ignore_index=True)
                    report_rows.append({
                        "status": "applied",
                        "Branch Path": branch_path,
                        "Variable": variable,
                        "Scenario": scenario,
                        "Region": economy.name,
                        "source_file": reconciliation_path.name,
                        "details": f"{BASE_YEAR}={float(source_value)}",
                    })

        for idx, target_row in overlaid_df.iterrows():
            variable = str(target_row.get("Variable", ""))
            csv_col = _LEAP_VAR_TO_CSV_COL.get(variable)
            if csv_col is None:
                continue
            transport_type = _extract_transport_label_from_branch_path(str(target_row.get("Branch Path", "")))
            source_row = reconciliation_by_transport.get(transport_type)
            if source_row is None:
                continue

            source_value = source_row[csv_col]

            if pd.isna(source_value):
                continue

            overlaid_df.at[idx, str(BASE_YEAR)] = float(source_value)
            for year_col in YEAR_COLUMNS:
                if int(year_col) > BASE_YEAR:
                    overlaid_df.at[idx, year_col] = pd.NA
            _stamp_row_source(overlaid_df, idx, source_type="apec_reconciliation_factors", source_name=reconciliation_path.name, source_scope=transport_type, source_date=str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else "", note=f"Reconciliation factor from {reconciliation_path.name} ({transport_type}).")
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
        vehicle_key_to_branch_path = {
            "bus": "Demand\\Passenger road\\Buses",
            "passenger_car": "Demand\\Passenger road\\LPVs",
            "suv_light_truck": "Demand\\Passenger road\\LPVs",
            "motorcycle": "Demand\\Passenger road\\Motorcycles",
        }
        scenarios = (
            overlaid_df.loc[overlaid_df["Variable"].eq("Vehicle Equivalent Weight"), "Scenario"]
            .dropna()
            .unique()
            .tolist()
        )
        # If the main VEW rows are absent (raw LEAP source), fall back to all scenarios.
        if not scenarios:
            scenarios = overlaid_df["Scenario"].dropna().unique().tolist() or ["Current Accounts"]

        # Create the main Vehicle Equivalent Weight row when absent,
        # populating the value directly from the CSV source.
        for vehicle_key, source_row in weights_by_vehicle.items():
            branch_path = vehicle_key_to_branch_path.get(vehicle_key)
            if not branch_path:
                continue
            vew_value = source_row.get("vehicle_equivalent_weight")
            if pd.isna(vew_value):
                continue
            for scenario in scenarios:
                exists = (
                    overlaid_df["Branch Path"].eq(branch_path)
                    & overlaid_df["Variable"].eq("Vehicle Equivalent Weight")
                    & overlaid_df["Scenario"].eq(scenario)
                ).any()
                if exists:
                    continue
                new_row = {column: pd.NA for column in MODULE1_INPUT_COLUMNS}
                new_row.update({
                    "Branch Path": branch_path,
                    "Variable": "Vehicle Equivalent Weight",
                    "Scenario": scenario,
                    "Region": economy.name,
                    "Scale": "",
                    "Units": "Vehicle equivalent",
                    "Per...": "",
                    str(BASE_YEAR): float(vew_value),
                    "input_source": "provided",
                    "source_type": "apec_vehicle_equivalent_weights",
                    "source_name": vehicle_weights_path.name,
                    "source_scope": vehicle_key,
                    "source_date": str(int(source_row["data_year"])) if not pd.isna(source_row.get("data_year")) else "",
                    "notes": f"Vehicle equivalent weight from {vehicle_weights_path.name} ({vehicle_key}).",
                    "standardized_label_status": "standardized",
                    "researcher_review_recommended": False,
                    "review_reason": "",
                })
                overlaid_df = pd.concat([overlaid_df, pd.DataFrame([new_row])], ignore_index=True)

        for vehicle_key, source_row in weights_by_vehicle.items():
            branch_path = vehicle_key_to_branch_path.get(vehicle_key)
            if not branch_path:
                continue
            for variable, source_column in {
                "Vehicle Equivalent Weight Lower Bound": "lower_bound",
                "Vehicle Equivalent Weight Upper Bound": "upper_bound",
            }.items():
                if pd.isna(source_row[source_column]):
                    continue
                for scenario in scenarios:
                    exists = (
                        overlaid_df["Branch Path"].eq(branch_path)
                        & overlaid_df["Variable"].eq(variable)
                        & overlaid_df["Scenario"].eq(scenario)
                    ).any()
                    if exists:
                        continue
                    new_row = {column: pd.NA for column in MODULE1_INPUT_COLUMNS}
                    new_row.update(
                        {
                            "Branch Path": branch_path,
                            "Variable": variable,
                            "Scenario": scenario,
                            "Region": economy.name,
                            "Scale": "",
                            "Units": "Vehicle equivalent",
                            "Per...": "",
                            str(BASE_YEAR): float(source_row[source_column]),
                        }
                    )
                    overlaid_df = pd.concat([overlaid_df, pd.DataFrame([new_row])], ignore_index=True)
        for idx, target_row in overlaid_df.iterrows():
            variable = str(target_row.get("Variable", ""))
            source_column_by_variable = {
                "Vehicle Equivalent Weight": "vehicle_equivalent_weight",
                "Vehicle Equivalent Weight Lower Bound": "lower_bound",
                "Vehicle Equivalent Weight Upper Bound": "upper_bound",
            }
            source_column = source_column_by_variable.get(variable)
            if source_column is None:
                continue
            vehicle_key = _vehicle_type_from_weight_branch_path(str(target_row.get("Branch Path", "")))
            source_row = weights_by_vehicle.get(vehicle_key)
            if source_row is None:
                continue
            source_value = source_row[source_column]
            if pd.isna(source_value):
                continue

            overlaid_df.at[idx, str(BASE_YEAR)] = float(source_value)
            for year_col in YEAR_COLUMNS:
                if int(year_col) > BASE_YEAR:
                    overlaid_df.at[idx, year_col] = pd.NA
            _stamp_row_source(overlaid_df, idx, source_type="apec_vehicle_equivalent_weights", source_name=vehicle_weights_path.name, source_scope=vehicle_key, source_date=str(int(source_row["data_year"])) if not pd.isna(source_row["data_year"]) else "", note=f"{variable} from {vehicle_weights_path.name} ({vehicle_key}).")
            report_rows.append(
                {
                    "status": "applied",
                    "Branch Path": target_row["Branch Path"],
                    "Variable": variable,
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


def _load_age_profile_records_from_leap_style_sheet(sheet_df: pd.DataFrame) -> pd.DataFrame:
    """Parse LEAP-style lifecycle blocks (Area/Profile/Year/Value) from a sheet."""
    if sheet_df is None or sheet_df.empty or sheet_df.shape[1] < 2:
        return pd.DataFrame(columns=["economy_code", "transport_type", "age", "value"])

    rows: list[dict[str, object]] = []
    current_area = ""
    current_profile = ""
    in_data_block = False

    for idx in range(len(sheet_df)):
        col0_raw = sheet_df.iloc[idx, 0]
        col1_raw = sheet_df.iloc[idx, 1]

        col0_text = str(col0_raw).strip() if not pd.isna(col0_raw) else ""
        col1_text = str(col1_raw).strip() if not pd.isna(col1_raw) else ""
        col0_lower = col0_text.lower()

        if col0_lower == "area:":
            current_area = col1_text
            in_data_block = False
            continue

        if col0_lower == "profile:":
            current_profile = col1_text
            in_data_block = False
            continue

        if col0_lower == "year" and col1_text.lower() == "value":
            in_data_block = True
            continue

        if not in_data_block:
            continue

        age = pd.to_numeric(col0_raw, errors="coerce")
        value = pd.to_numeric(col1_raw, errors="coerce")
        if pd.isna(age) or pd.isna(value):
            continue

        transport_hint = current_profile if current_profile else current_area
        rows.append(
            {
                "economy_code": _normalize_apec_economy_code(current_area),
                "transport_type": _normalize_transport_type(transport_hint),
                "age": int(age),
                "value": float(value),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["economy_code", "transport_type", "age", "value"])

    return pd.DataFrame(rows)


def _load_age_profile_records_from_workbook(
    workbook_path: Path,
    value_column_candidates: list[str],
) -> pd.DataFrame:
    all_sheets = pd.read_excel(workbook_path, sheet_name=None)
    parsed_frames: list[pd.DataFrame] = []

    for _, sheet_df in all_sheets.items():
        if sheet_df is None or sheet_df.empty:
            continue

        leap_style_df = _load_age_profile_records_from_leap_style_sheet(sheet_df)
        if not leap_style_df.empty:
            parsed_frames.append(leap_style_df)

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
    if economy_subset.empty:
        economy_subset = records.copy()

    generic_by_age: dict[int, float] = {}

    for _, row in economy_subset.iterrows():
        transport_type = str(row.get("transport_type", "")).strip().lower()
        age = int(row["age"])
        value = float(row["value"])
        if transport_type in {"passenger", "freight"}:
            lookup[(transport_type, age)] = value
        else:
            generic_by_age[age] = value

    if generic_by_age:
        for transport_type in ("passenger", "freight"):
            for age, value in generic_by_age.items():
                lookup.setdefault((transport_type, age), value)
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

        # If age-series rows for this variable are absent (e.g. source is a raw LEAP
        # export that doesn't include supplemental rows), build them directly from the
        # profile xlsx — values, source attribution and all — in a single pass.
        # Nothing is invented here: every value comes from profile_lookup which was
        # read from the xlsx file above.
        existing_age_mask = overlaid_df["Variable"].eq(variable_name)
        if not existing_age_mask.any():
            transport_branches = {
                "passenger": "Demand\\Passenger road",
                "freight": "Demand\\Freight road",
            }
            scenarios = overlaid_df["Scenario"].dropna().unique().tolist() or ["Current Accounts"]
            new_rows: list[dict] = []
            for (transport_type, age), profile_value in profile_lookup.items():
                branch_path = transport_branches.get(transport_type)
                if not branch_path:
                    continue
                age_branch = f"{branch_path}\\Age {age}"
                for scenario in scenarios:
                    new_row = {column: pd.NA for column in MODULE1_INPUT_COLUMNS}
                    new_row.update({
                        "Branch Path": age_branch,
                        "Variable": variable_name,
                        "Scenario": scenario,
                        "Region": economy.name,
                        "Scale": "%",
                        "Units": "Share",
                        "Per...": "",
                        str(BASE_YEAR): float(profile_value),
                        "input_source": "provided",
                        "source_type": source_type,
                        "source_name": profile_path.name,
                        "source_scope": economy.code,
                        "source_date": SOURCE_DATE,
                        "notes": (
                            f"{variable_name} imported from {profile_path.name}; "
                            f"transport={transport_type}, age={age}."
                        ),
                        "standardized_label_status": "standardized",
                        "researcher_review_recommended": False,
                        "review_reason": "",
                    })
                    report_rows.append({
                        "status": "applied",
                        "Branch Path": age_branch,
                        "Variable": variable_name,
                        "Scenario": scenario,
                        "Region": economy.name,
                        "source_file": profile_path.name,
                        "details": f"{BASE_YEAR}={float(profile_value)}",
                    })
                    new_rows.append(new_row)
            if new_rows:
                overlaid_df = pd.concat([overlaid_df, pd.DataFrame(new_rows)], ignore_index=True)
            continue  # rows are fully populated; skip the update-in-place loop below

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

            _stamp_row_source(overlaid_df, idx, source_type=source_type, source_name=profile_path.name, source_scope=economy.code, source_date=SOURCE_DATE, note=f"{variable_name} imported from {profile_path.name}; transport={transport_label}, age={age}.")
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
    return None


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

    # PHEV is only valid for LPVs and LCVs — drop Bus/Motorcycle PHEV rows from the source.
    _phev_oos = (
        workbook_df["Branch Path"].str.contains("PHEV", na=False)
        & (
            workbook_df["Branch Path"].str.contains(r"\\Buses\\", na=False)
            | workbook_df["Branch Path"].str.contains(r"\\Motorcycles\\", na=False)
        )
    )
    workbook_df = workbook_df[~_phev_oos].copy()

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
        overlaid_df.at[idx, "input_source"] = "provided"
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


PROCESSED_SOURCE_COLUMNS = ["Branch Path", "Variable", "Scenario", "Year", "Value", "Units"]
MANUAL_FILLED_SOURCE_COLUMNS = ["Economy", *PROCESSED_SOURCE_COLUMNS]
MANUAL_DO_NOT_USE_COLUMN = "DO_NOT_USE"
SOURCE_PRIORITY_COLUMNS = ["source_type", "source_name", "priority", "notes"]
DEFAULT_SOURCE_PRIORITIES = {
    ("processed_source", "*"): 10,
    ("manual_missing_rows", "manually_entered_missing_rows.csv"): -1,
}
FINAL_VALUE_OVERRIDE_DIR = ROAD_MODEL_DATA_DIR / "final_value_overrides"
FINAL_VALUE_OVERRIDE_COLUMNS = [*PROCESSED_SOURCE_COLUMNS, "share_decreased_from", "note", MANUAL_DO_NOT_USE_COLUMN]
FINAL_VALUE_OVERRIDE_REPORT_COLUMNS = [
    "action",
    "Branch Path",
    "Variable",
    "Scenario",
    "Year",
    "old_value",
    "new_value",
    "delta",
    "Units",
    "source_name",
    "details",
]
SHARE_BALANCED_VARIABLES = {"Sales Share", "Stock Share"}
PERCENT_SCALE_VARIABLES = {
    "Sales Share",
    "Stock Share",
    "Device Share",
    "PHEV Electric Driving Share",
    "Survival Rate",
    "Vintage Profile Share",
}


def _processed_source_path(economy: EconomyInfo) -> Path:
    return PROCESSED_SOURCE_DIR / f"road_module1_source_{economy.code}.csv"


def _final_value_override_paths(economy: EconomyInfo) -> list[Path]:
    if not FINAL_VALUE_OVERRIDE_DIR.exists():
        return []

    paths: list[Path] = []
    for suffix in ["csv", "xlsx", "xls"]:
        paths.extend(
            [
                *FINAL_VALUE_OVERRIDE_DIR.glob(f"module1_final_value_overrides_{economy.code}.{suffix}"),
                *FINAL_VALUE_OVERRIDE_DIR.glob(f"module1_final_value_override_{economy.code}.{suffix}"),
            ]
        )
    return sorted(set(paths))


def _source_priority_sort_value(priority: int | float) -> float:
    """Sort value for source priorities: 1 is highest; negative values are fallback tiers."""
    priority = int(priority)
    if priority < 0:
        return 1_000_000 + abs(priority)
    return float(priority)


def _load_source_priorities(path: Path = SOURCE_PRIORITY_PATH) -> dict[tuple[str, str], int]:
    priorities = dict(DEFAULT_SOURCE_PRIORITIES)
    if not path.exists():
        return priorities

    df = _read_required_csv(path, SOURCE_PRIORITY_COLUMNS)
    for _, row in df.iterrows():
        source_type = str(row["source_type"] or "").strip()
        source_name = str(row["source_name"] or "").strip()
        priority = pd.to_numeric(pd.Series([row["priority"]]), errors="coerce").iloc[0]
        if not source_type or not source_name or pd.isna(priority):
            continue
        priorities[(source_type, source_name)] = int(priority)
    return priorities


def _lookup_source_priority(
    priorities: dict[tuple[str, str], int],
    source_type: str,
    source_name: str,
) -> int:
    source_type = str(source_type or "").strip()
    source_name = str(source_name or "").strip()
    return priorities.get(
        (source_type, source_name),
        priorities.get((source_type, "*"), 100),
    )


def _manual_filled_source_paths() -> list[Path]:
    if not MANUALLY_FILLED_ROWS_DIR.exists():
        return []
    return sorted(MANUALLY_FILLED_ROWS_DIR.glob("*.csv"))


def _is_do_not_use_value(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "do not use", "x"}


def _load_manual_filled_rows(economy: EconomyInfo) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    allowed_economies = {economy.code, economy.code.replace("_", ""), economy.name}
    for path in _manual_filled_source_paths():
        source_df = _read_required_csv(path, MANUAL_FILLED_SOURCE_COLUMNS)
        source_df = source_df.copy()
        source_df = source_df.rename(
            columns={
                "DO NOT USE": MANUAL_DO_NOT_USE_COLUMN,
                "do_not_use": MANUAL_DO_NOT_USE_COLUMN,
                "do not use": MANUAL_DO_NOT_USE_COLUMN,
            }
        )
        if MANUAL_DO_NOT_USE_COLUMN in source_df.columns:
            source_df = source_df[~source_df[MANUAL_DO_NOT_USE_COLUMN].map(_is_do_not_use_value)].copy()
        source_df["Economy"] = source_df["Economy"].fillna("").astype(str).str.strip()
        source_df = source_df[source_df["Economy"].isin(allowed_economies)].copy()
        if source_df.empty:
            continue
        source_df = source_df[PROCESSED_SOURCE_COLUMNS].copy()
        source_df["_source_type"] = "manual_missing_rows"
        source_df["_source_name"] = path.name
        source_df["_source_note"] = "Loaded from manually filled missing-row source."
        frames.append(source_df)
    if not frames:
        return pd.DataFrame(columns=[*PROCESSED_SOURCE_COLUMNS, "_source_type", "_source_name", "_source_note"])
    return pd.concat(frames, ignore_index=True)


def _load_ranked_source_rows(economy: EconomyInfo) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    source_path = _processed_source_path(economy)
    if source_path.exists():
        processed_df = _read_required_csv(source_path, PROCESSED_SOURCE_COLUMNS).copy()
        processed_df["_source_type"] = "processed_source"
        processed_df["_source_name"] = source_path.name
        processed_df["_source_note"] = "Loaded from preprocessed Road Module 1 source."
        frames.append(processed_df)

    manual_df = _load_manual_filled_rows(economy)
    if not manual_df.empty:
        frames.append(manual_df)

    if not frames:
        return pd.DataFrame(columns=[*PROCESSED_SOURCE_COLUMNS, "_source_type", "_source_name", "_source_note"])

    source_df = pd.concat(frames, ignore_index=True, sort=False)
    priorities = _load_source_priorities()
    source_df["_priority"] = [
        _lookup_source_priority(priorities, source_type, source_name)
        for source_type, source_name in zip(source_df["_source_type"], source_df["_source_name"])
    ]
    source_df["_priority_sort"] = source_df["_priority"].map(_source_priority_sort_value)
    return source_df


def _read_final_value_override_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported final value override file type: {path}")

    missing = [column for column in FINAL_VALUE_OVERRIDE_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing required override columns: {', '.join(missing)}"
        )
    df = df.copy()
    df = df.rename(
        columns={
            "DO NOT USE": MANUAL_DO_NOT_USE_COLUMN,
            "do_not_use": MANUAL_DO_NOT_USE_COLUMN,
            "do not use": MANUAL_DO_NOT_USE_COLUMN,
        }
    )
    if MANUAL_DO_NOT_USE_COLUMN in df.columns:
        df = df[~df[MANUAL_DO_NOT_USE_COLUMN].map(_is_do_not_use_value)].copy()
    df["_override_source_name"] = path.name
    return df


def _value_override_key(row: pd.Series | dict[str, object]) -> tuple[str, str, str, int]:
    return (
        str(row["Branch Path"]).strip(),
        str(row["Variable"]).strip(),
        str(row["Scenario"]).strip(),
        int(row["Year"]),
    )


def _branch_parent(branch_path: str) -> str:
    path = str(branch_path or "").strip()
    if "\\" not in path:
        return ""
    return path.rsplit("\\", 1)[0]


def _resolve_share_decreased_from_branch(target_branch_path: str, share_decreased_from: str) -> str:
    source_branch = str(share_decreased_from or "").strip()
    if not source_branch:
        return ""
    if "\\" in source_branch:
        return source_branch
    parent = _branch_parent(target_branch_path)
    return f"{parent}\\{source_branch}" if parent else source_branch


def _normalize_final_value_override_rows(
    override_df: pd.DataFrame,
    economy: EconomyInfo,
) -> pd.DataFrame:
    df = override_df.copy()
    for column in ["Branch Path", "Variable", "Scenario", "Units", "share_decreased_from"]:
        df[column] = df[column].fillna("").astype(str).str.strip()
    if "Region" in df.columns:
        df["Region"] = df["Region"].fillna("").astype(str).str.strip()
        allowed_regions = {"", economy.code, economy.name, *ECONOMY_CODE_TO_LEAP_REGION_NAMES.get(economy.code, [])}
        bad_region_mask = ~df["Region"].isin(allowed_regions)
        if bad_region_mask.any():
            sample = df.loc[bad_region_mask, ["Region", "Branch Path", "Variable"]].head(5).to_dict(orient="records")
            raise ValueError(
                f"Final value overrides for {economy.code} include rows for another region. Sample: {sample}"
            )

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    missing_required_mask = (
        df["Branch Path"].eq("")
        | df["Variable"].eq("")
        | df["Scenario"].eq("")
        | df["Year"].isna()
        | df["Value"].isna()
    )
    if missing_required_mask.any():
        sample = df.loc[missing_required_mask, FINAL_VALUE_OVERRIDE_COLUMNS].head(5).to_dict(orient="records")
        raise ValueError(f"Final value override rows have missing required values. Sample: {sample}")

    df["Year"] = df["Year"].astype(int)
    duplicate_mask = df.duplicated(subset=["Branch Path", "Variable", "Scenario", "Year"], keep=False)
    if duplicate_mask.any():
        sample = df.loc[duplicate_mask, ["Branch Path", "Variable", "Scenario", "Year"]].head(5).to_dict(orient="records")
        raise ValueError(f"Final value overrides have duplicate row keys. Sample: {sample}")
    return df


def _apply_final_share_group_rebalance(
    final_df: pd.DataFrame,
    share_adjustments: list[dict[str, object]],
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    df = final_df.copy()
    report_rows: list[dict[str, object]] = []
    if not share_adjustments:
        return df, report_rows

    groups_to_normalize: set[tuple[str, str, str, str]] = set()
    fixed_branches_by_group: dict[tuple[str, str, str, str], set[str]] = {}

    for adjustment in share_adjustments:
        parent_path = str(adjustment["parent_path"])
        variable = str(adjustment["Variable"])
        year_col = str(adjustment["Year"])
        scenario = str(adjustment["Scenario"])
        group_key = (parent_path, variable, year_col, scenario)
        fixed_branches_by_group.setdefault(group_key, set()).add(str(adjustment["Branch Path"]))
        decreased_from_branch = str(adjustment.get("share_decreased_from", "") or "").strip()
        delta = pd.to_numeric(adjustment.get("delta"), errors="coerce")

        if not decreased_from_branch:
            groups_to_normalize.add(group_key)
            continue

        fixed_branches_by_group.setdefault(group_key, set()).add(decreased_from_branch)
        if year_col not in df.columns:
            raise ValueError(f"Final value override year is not available in generated defaults: {year_col}")
        group_mask = (
            df["Variable"].eq(variable)
            & df["Scenario"].eq(scenario)
            & df["Branch Path"].map(_branch_parent).eq(parent_path)
        )
        group_df = df[group_mask].copy()
        if group_df.empty:
            continue

        df.loc[group_mask, year_col] = pd.to_numeric(df.loc[group_mask, year_col], errors="coerce")
        if pd.isna(delta) or abs(float(delta)) <= 0.000001:
            continue

        decrease_mask = group_mask & df["Branch Path"].eq(decreased_from_branch)
        if not decrease_mask.any():
            raise ValueError(
                f"share_decreased_from branch was not found in the same sibling group: "
                f"{decreased_from_branch} for {variable} under {parent_path} | {scenario} | {year_col}"
            )
        target_idx = df[decrease_mask].index[0]
        old_value = df.at[target_idx, year_col]
        adjusted_value = float(df.at[target_idx, year_col]) - float(delta)
        if adjusted_value < -0.000001:
            raise ValueError(
                f"share_decreased_from branch would become negative: "
                f"{decreased_from_branch} for {variable} under {parent_path} | {scenario} | {year_col}"
            )
        df.at[target_idx, year_col] = max(0.0, adjusted_value)
        df.at[target_idx, "input_source"] = "provided"
        df.at[target_idx, "source_type"] = "final_value_override"
        df.at[target_idx, "source_name"] = "final_value_overrides"
        df.at[target_idx, "notes"] = "Adjusted to keep final overridden sibling shares summing to 100."
        report_rows.append(
            {
                "action": "share_decreased_from_adjustment",
                "Branch Path": df.at[target_idx, "Branch Path"],
                "Variable": variable,
                "Scenario": scenario,
                "Year": int(year_col),
                "old_value": old_value,
                "new_value": max(0.0, adjusted_value),
                "delta": max(0.0, adjusted_value) - float(old_value),
                "Units": df.at[target_idx, "Units"],
                "source_name": "final_value_overrides",
                "details": f"Adjusted by {-float(delta)} from {adjustment['Branch Path']}.",
            }
        )

    for parent_path, variable, year_col, scenario in groups_to_normalize:
        if year_col not in df.columns:
            raise ValueError(f"Final value override year is not available in generated defaults: {year_col}")
        group_mask = (
            df["Variable"].eq(variable)
            & df["Scenario"].eq(scenario)
            & df["Branch Path"].map(_branch_parent).eq(parent_path)
        )
        group_df = df[group_mask].copy()
        if group_df.empty:
            continue

        df.loc[group_mask, year_col] = pd.to_numeric(df.loc[group_mask, year_col], errors="coerce")
        group_total = float(df.loc[group_mask, year_col].sum())
        if abs(group_total - 100.0) <= 0.000001:
            continue
        if group_total <= 0:
            raise ValueError(
                f"Cannot normalize {variable} shares with non-positive total under "
                f"{parent_path} | {scenario} | {year_col}."
            )
        fixed_branches = fixed_branches_by_group.get((parent_path, variable, year_col, scenario), set())
        fixed_mask = group_mask & df["Branch Path"].isin(fixed_branches)
        flexible_mask = group_mask & ~df["Branch Path"].isin(fixed_branches)
        fixed_total = float(df.loc[fixed_mask, year_col].sum())
        flexible_total = float(df.loc[flexible_mask, year_col].sum())
        target_flexible_total = 100.0 - fixed_total
        if target_flexible_total < -0.000001:
            raise ValueError(
                f"Cannot normalize {variable} shares because fixed override rows exceed 100 under "
                f"{parent_path} | {scenario} | {year_col}."
            )
        if flexible_total <= 0:
            raise ValueError(
                f"Cannot normalize {variable} shares because non-overridden siblings have non-positive total under "
                f"{parent_path} | {scenario} | {year_col}."
            )
        for idx in df[flexible_mask].index:
            old_value = df.at[idx, year_col]
            new_value = float(df.at[idx, year_col]) / flexible_total * target_flexible_total
            df.at[idx, year_col] = new_value
            df.at[idx, "input_source"] = "provided"
            df.at[idx, "source_type"] = "final_value_override"
            df.at[idx, "source_name"] = "final_value_overrides"
            df.at[idx, "notes"] = "Scaled to keep final overridden sibling shares summing to 100."
            report_rows.append(
                {
                    "action": "share_group_scaled_to_residual",
                    "Branch Path": df.at[idx, "Branch Path"],
                    "Variable": variable,
                    "Scenario": scenario,
                    "Year": int(year_col),
                    "old_value": old_value,
                    "new_value": new_value,
                    "delta": new_value - float(old_value),
                    "Units": df.at[idx, "Units"],
                    "source_name": "final_value_overrides",
                    "details": (
                        f"Scaled non-overridden siblings from {flexible_total} to "
                        f"{target_flexible_total}; fixed override total was {fixed_total}."
                    ),
                }
            )

    return df, report_rows


def apply_final_value_overrides_with_report(
    final_df: pd.DataFrame,
    economy: EconomyInfo,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Overlay optional final value rows after all source overlays have run."""
    override_paths = _final_value_override_paths(economy)
    if not override_paths:
        return final_df, pd.DataFrame(columns=FINAL_VALUE_OVERRIDE_REPORT_COLUMNS)

    override_df = pd.concat(
        [_read_final_value_override_file(path) for path in override_paths],
        ignore_index=True,
    )
    override_df = _normalize_final_value_override_rows(override_df, economy)
    completed_df = final_df.copy()
    report_rows: list[dict[str, object]] = []

    key_to_index = {
        (
            str(row["Branch Path"]).strip(),
            str(row["Variable"]).strip(),
            str(row["Scenario"]).strip(),
        ): idx
        for idx, row in completed_df.iterrows()
    }
    share_adjustments: list[dict[str, object]] = []

    for _, override_row in override_df.iterrows():
        branch_path, variable, scenario, year = _value_override_key(override_row)
        key = (branch_path, variable, scenario)
        year_col = str(year)
        target_idx = key_to_index.get(key)
        if target_idx is None:
            raise ValueError(
                "Final value override row does not match an existing generated row: "
                f"{dict(zip(['Branch Path', 'Variable', 'Scenario', 'Year'], [branch_path, variable, scenario, year]))}"
            )
        if year_col not in completed_df.columns:
            raise ValueError(f"Final value override year is not available in generated defaults: {year_col}")

        old_value = completed_df.at[target_idx, year_col]
        completed_df.at[target_idx, year_col] = float(override_row["Value"])
        completed_df.at[target_idx, "Units"] = str(override_row["Units"]).strip()
        completed_df.at[target_idx, "input_source"] = "provided"
        completed_df.at[target_idx, "source_type"] = "final_value_override"
        completed_df.at[target_idx, "source_name"] = str(override_row["_override_source_name"])
        completed_df.at[target_idx, "source_scope"] = economy.code
        completed_df.at[target_idx, "source_date"] = datetime.now().strftime("%Y-%m-%d")
        completed_df.at[target_idx, "researcher_review_recommended"] = False
        completed_df.at[target_idx, "review_reason"] = ""
        completed_df.at[target_idx, "notes"] = "Final value override applied after all source overlays."
        old_numeric = pd.to_numeric(old_value, errors="coerce")
        delta_value = pd.NA if pd.isna(old_numeric) else float(override_row["Value"]) - float(old_numeric)
        report_rows.append(
            {
                "action": "direct_override",
                "Branch Path": branch_path,
                "Variable": variable,
                "Scenario": scenario,
                "Year": year,
                "old_value": old_value,
                "new_value": float(override_row["Value"]),
                "delta": delta_value,
                "Units": str(override_row["Units"]).strip(),
                "source_name": str(override_row["_override_source_name"]),
                "details": "Value from final override spreadsheet.",
            }
        )

        if variable in SHARE_BALANCED_VARIABLES:
            parent_path = _branch_parent(branch_path)
            decreased_from_branch = _resolve_share_decreased_from_branch(
                target_branch_path=branch_path,
                share_decreased_from=str(override_row["share_decreased_from"]),
            )
            if decreased_from_branch and _branch_parent(decreased_from_branch) != parent_path:
                raise ValueError(
                    f"share_decreased_from must be in the same sibling group as the override row. "
                    f"Override: {branch_path}; share_decreased_from: {decreased_from_branch}"
                )
            share_adjustments.append(
                {
                    "parent_path": parent_path,
                    "Branch Path": branch_path,
                    "Variable": variable,
                    "Scenario": scenario,
                    "Year": year_col,
                    "delta": delta_value,
                    "share_decreased_from": decreased_from_branch,
                }
            )

    completed_df, rebalance_report_rows = _apply_final_share_group_rebalance(completed_df, share_adjustments)
    report_rows.extend(rebalance_report_rows)
    report_df = pd.DataFrame(report_rows)
    if report_df.empty:
        report_df = pd.DataFrame(columns=FINAL_VALUE_OVERRIDE_REPORT_COLUMNS)
    return completed_df[MODULE1_INPUT_COLUMNS], report_df[FINAL_VALUE_OVERRIDE_REPORT_COLUMNS]


def apply_final_value_overrides(final_df: pd.DataFrame, economy: EconomyInfo) -> pd.DataFrame:
    overlaid_df, _ = apply_final_value_overrides_with_report(final_df, economy)
    return overlaid_df


def _format_report_number(value: object) -> str:
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return ""
    return f"{float(numeric_value):,.6g}"


def _final_override_chart_svg(row: pd.Series, chart_width: int = 420, chart_height: int = 80) -> str:
    old_value = pd.to_numeric(row.get("old_value"), errors="coerce")
    new_value = pd.to_numeric(row.get("new_value"), errors="coerce")
    if pd.isna(old_value) or pd.isna(new_value):
        return "<div class=\"empty-chart\">No numeric before/after values</div>"

    old_float = float(old_value)
    new_float = float(new_value)
    max_abs = max(abs(old_float), abs(new_float), 1.0)
    bar_max_width = chart_width - 140
    old_width = abs(old_float) / max_abs * bar_max_width
    new_width = abs(new_float) / max_abs * bar_max_width
    old_text = escape(_format_report_number(old_float))
    new_text = escape(_format_report_number(new_float))
    delta_text = escape(_format_report_number(new_float - old_float))
    return f"""
<svg width="{chart_width}" height="{chart_height}" viewBox="0 0 {chart_width} {chart_height}" role="img" aria-label="Final override before and after chart">
  <text x="0" y="18" font-family="Arial" font-size="12" fill="#333">Old</text>
  <rect x="54" y="7" width="{old_width:.2f}" height="16" fill="#8aa0b5"></rect>
  <text x="{min(58 + old_width, chart_width - 76):.2f}" y="19" font-family="Arial" font-size="11" fill="#222">{old_text}</text>
  <text x="0" y="46" font-family="Arial" font-size="12" fill="#333">New</text>
  <rect x="54" y="35" width="{new_width:.2f}" height="16" fill="#257f5b"></rect>
  <text x="{min(58 + new_width, chart_width - 76):.2f}" y="47" font-family="Arial" font-size="11" fill="#222">{new_text}</text>
  <text x="0" y="72" font-family="Arial" font-size="12" fill="#333">Delta: {delta_text}</text>
</svg>
""".strip()


def write_final_value_override_visibility_report(
    report_df: pd.DataFrame,
    output_dir: Path,
    economy: EconomyInfo,
) -> tuple[Path | None, Path | None]:
    """Write CSV and browser-openable HTML charts for final value overrides."""
    if report_df.empty:
        return None, None

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "road_module1_final_value_override_report.csv"
    html_path = output_dir / "road_module1_final_value_override_report.html"
    report_df.to_csv(csv_path, index=False)

    cards = []
    for _, row in report_df.iterrows():
        title = f"{row.get('Variable', '')} | {row.get('Scenario', '')} | {row.get('Year', '')}"
        subtitle = str(row.get("Branch Path", ""))
        details = str(row.get("details", ""))
        cards.append(
            f"""
<section class="card">
  <h2>{escape(title)}</h2>
  <div class="path">{escape(subtitle)}</div>
  <div class="meta">{escape(str(row.get('action', '')))} | {escape(str(row.get('Units', '')))} | {escape(str(row.get('source_name', '')))}</div>
  {_final_override_chart_svg(row)}
  <p>{escape(details)}</p>
</section>
""".strip()
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Final Value Override Report - {escape(economy.code)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; background: #f7f8fa; }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    .summary {{ margin: 0 0 20px; color: #52606d; }}
    .card {{ background: white; border: 1px solid #d9e2ec; border-radius: 8px; padding: 14px 16px; margin: 0 0 14px; }}
    h2 {{ font-size: 16px; margin: 0 0 6px; }}
    .path {{ font-size: 13px; color: #334e68; margin-bottom: 4px; }}
    .meta {{ font-size: 12px; color: #627d98; margin-bottom: 10px; }}
    p {{ margin: 8px 0 0; font-size: 13px; color: #52606d; }}
    .empty-chart {{ font-size: 13px; color: #9aa5b1; }}
  </style>
</head>
<body>
  <h1>Final Value Override Report - {escape(economy.code)}</h1>
  <p class="summary">{len(report_df)} override-related row changes. CSV: {escape(csv_path.name)}</p>
  {''.join(cards)}
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")
    return csv_path, html_path


def load_processed_source_inputs(
    economy: EconomyInfo,
    scenarios: Iterable[str] = DEFAULT_SCENARIOS,
) -> pd.DataFrame:
    """Load priority-ranked source rows into the internal Module 1 wide schema."""
    source_df = _load_ranked_source_rows(economy)
    if source_df.empty:
        return pd.DataFrame(columns=MODULE1_INPUT_COLUMNS)

    source_df = source_df.copy()
    for column in ["Branch Path", "Variable", "Scenario", "Units"]:
        source_df[column] = source_df[column].fillna("").astype(str).str.strip()
    source_df["Year"] = pd.to_numeric(source_df["Year"], errors="coerce")
    source_df["Value"] = pd.to_numeric(source_df["Value"], errors="coerce")
    source_df = source_df.dropna(subset=["Year", "Value"])
    if source_df.empty:
        return pd.DataFrame(columns=MODULE1_INPUT_COLUMNS)
    source_df["Year"] = source_df["Year"].astype(int)
    base_year_key_columns = ["Branch Path", "Variable", "Scenario", "Units"]
    has_base_year = set(
        source_df.loc[source_df["Year"].eq(BASE_YEAR), base_year_key_columns]
        .astype(str)
        .agg("\u241f".join, axis=1)
    )
    fallback_base_rows = []
    prior_year_df = source_df[source_df["Year"].lt(BASE_YEAR)].copy()
    for _, group_df in prior_year_df.groupby(base_year_key_columns, dropna=False):
        key = "\u241f".join(str(group_df.iloc[0][column]) for column in base_year_key_columns)
        if key in has_base_year:
            continue
        latest_row = group_df.sort_values("Year").iloc[-1].copy()
        latest_row["Year"] = BASE_YEAR
        fallback_base_rows.append(latest_row)
    if fallback_base_rows:
        source_df = pd.concat([source_df, pd.DataFrame(fallback_base_rows)], ignore_index=True)
    source_df["Year"] = source_df["Year"].astype(str)
    source_df = source_df[source_df["Year"].isin(YEAR_COLUMNS)].copy()
    source_df = source_df[
        source_df["Branch Path"].ne("")
        & source_df["Variable"].ne("")
        & source_df["Scenario"].ne("")
    ].copy()
    if source_df.empty:
        return pd.DataFrame(columns=MODULE1_INPUT_COLUMNS)

    scenario_names = {_format_leap_scenario(scenario) for scenario in scenarios}
    scenario_aliases = set(scenario_names)
    if "Current Accounts" in scenario_names:
        scenario_aliases.add("Reference")
    if "Reference" in scenario_names:
        scenario_aliases.add("Current Accounts")
    source_df = source_df[source_df["Scenario"].isin(scenario_aliases)].copy()
    if source_df.empty:
        return pd.DataFrame(columns=MODULE1_INPUT_COLUMNS)

    key_columns = ["Branch Path", "Variable", "Scenario", "Year"]
    source_df["_value_text"] = source_df["Value"].round(12).astype(str)
    same_priority_conflicts = source_df.duplicated(subset=[*key_columns, "_priority", "_value_text"], keep=False)
    unresolved_conflicts = source_df.duplicated(subset=[*key_columns, "_priority"], keep=False) & ~same_priority_conflicts
    if unresolved_conflicts.any():
        sample = source_df.loc[
            unresolved_conflicts,
            [*key_columns, "Value", "_source_type", "_source_name", "_priority"],
        ].head(10).to_dict(orient="records")
        raise ValueError(f"Source rows have conflicting values at the same priority. Sample: {sample}")

    source_df = source_df.sort_values(
        [*key_columns, "_priority_sort", "_source_type", "_source_name"],
        na_position="last",
    )
    source_df = source_df.drop_duplicates(subset=key_columns, keep="first").copy()

    source_df["Region"] = economy.name
    source_df["Scale"] = source_df["Variable"].map(
        lambda variable: "%" if str(variable) in PERCENT_SCALE_VARIABLES else ""
    )
    source_df["Per..."] = ""
    source_df["input_source"] = "provided"
    source_df["standardized_label_status"] = "standardized"
    source_df["notes"] = source_df["_source_note"].fillna("")
    source_df["source_type"] = source_df["_source_type"].fillna("")
    source_df["source_name"] = source_df["_source_name"].fillna("")
    source_df["source_scope"] = economy.code
    source_df["source_date"] = SOURCE_DATE
    source_df["default_version"] = DEFAULT_VERSION
    source_df["researcher_review_recommended"] = False
    source_df["review_reason"] = ""

    index_columns = [column for column in MODULE1_INPUT_COLUMNS if column not in YEAR_COLUMNS]
    wide_df = (
        source_df.pivot_table(
            index=index_columns,
            columns="Year",
            values="Value",
            aggfunc="first",
            dropna=True,
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    for column in MODULE1_INPUT_COLUMNS:
        if column not in wide_df.columns:
            wide_df[column] = pd.NA
    for year_col in YEAR_COLUMNS:
        wide_df[year_col] = pd.to_numeric(wide_df[year_col], errors="coerce")
    return wide_df[MODULE1_INPUT_COLUMNS]


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


def _wide_defaults_to_long(defaults_df: pd.DataFrame, economy: str) -> pd.DataFrame:
    """Convert internal wide Module 1 rows to the canonical long CSV contract."""
    rows: list[dict[str, object]] = []
    if defaults_df.empty:
        return pd.DataFrame(columns=MODULE1_LONG_COLUMNS)

    for _, row in defaults_df.iterrows():
        source = row.get("source_name", row.get("Source", ""))
        comment = row.get("notes", row.get("Comment", ""))
        for year_col in YEAR_COLUMNS:
            if year_col not in defaults_df.columns:
                continue
            value = row.get(year_col)
            if pd.isna(value):
                continue
            rows.append(
                {
                    "Economy": economy,
                    "Scenario": row.get("Scenario", ""),
                    "Branch Path": row.get("Branch Path", ""),
                    "Variable": row.get("Variable", ""),
                    "Year": int(year_col),
                    "Value": value,
                    "Units": row.get("Units", ""),
                    "Source": source,
                    "Comment": comment,
                }
            )

    return pd.DataFrame(rows, columns=MODULE1_LONG_COLUMNS)


def _long_defaults_to_ui_wide(long_df: pd.DataFrame, economy: str, region_name: str | None = None) -> pd.DataFrame:
    """Convert canonical long rows back to the legacy wide shape used by the UI/backend helpers."""
    if long_df.empty:
        return pd.DataFrame(columns=MODULE1_INPUT_COLUMNS)

    df = long_df.copy()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.dropna(subset=["Year"])
    df["Year"] = df["Year"].astype(int).astype(str)
    df["Region"] = region_name or economy
    if "Source" not in df.columns:
        df["Source"] = ""
    if "Comment" not in df.columns:
        df["Comment"] = ""

    index_cols = ["Branch Path", "Variable", "Scenario", "Region", "Units", "Source", "Comment"]
    wide = (
        df.pivot_table(
            index=index_cols,
            columns="Year",
            values="Value",
            aggfunc="first",
            dropna=True,
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    for column in MODULE1_INPUT_COLUMNS:
        if column not in wide.columns:
            wide[column] = pd.NA
    wide["Scale"] = wide["Variable"].map(lambda variable: "%" if str(variable) in {"Sales Share", "Stock Share", "PHEV Electric Driving Share", "Survival Rate", "Vintage Profile Share"} else "")
    wide["Per..."] = ""
    wide["input_source"] = "provided"
    wide["standardized_label_status"] = "standardized"
    wide["notes"] = wide["Comment"].fillna("")
    wide["source_type"] = "module1_long_csv"
    wide["source_name"] = wide["Source"].fillna("")
    wide["source_scope"] = economy
    wide["source_date"] = ""
    wide["default_version"] = DEFAULT_VERSION
    wide["researcher_review_recommended"] = False
    wide["review_reason"] = ""
    return wide[MODULE1_INPUT_COLUMNS]


def _stock_share_transport_group(branch_path: str) -> str:
    path = str(branch_path or "")
    if path in VEHICLE_TYPE_STOCK_SHARE_BRANCHES["passenger"]:
        return "passenger"
    if path in VEHICLE_TYPE_STOCK_SHARE_BRANCHES["freight"]:
        return "freight"
    return ""


def _canonical_stock_share_branch_from_stock_path(branch_path: str) -> str:
    path = str(branch_path or "")
    for branch in [
        *VEHICLE_TYPE_STOCK_SHARE_BRANCHES["passenger"],
        *VEHICLE_TYPE_STOCK_SHARE_BRANCHES["freight"],
    ]:
        if path == branch or path.startswith(branch + "\\"):
            return branch
    return ""


def _ensure_vehicle_type_stock_share_rows(defaults_df: pd.DataFrame, economy: EconomyInfo) -> pd.DataFrame:
    """
    Ensure the five LEAP vehicle-type Stock Share rows exist and sum to 100 by transport group.

    Base-year share is always derived from base-year Stock rows and overwritten.
    Future-year columns (STOCK_SHARE_PROJECTION_YEARS) are seeded to the base-year
    share if not already set by a researcher — existing non-null values are preserved.
    """
    df = defaults_df.copy()
    if str(BASE_YEAR) not in df.columns:
        return df

    # Ensure projection-year columns exist in the DataFrame (they may not if DEFAULT_YEARS is base-year only).
    for yr in STOCK_SHARE_PROJECTION_YEARS:
        if str(yr) not in df.columns:
            df[str(yr)] = pd.NA

    source = df.copy()
    source["_canonical_stock_share_branch"] = source["Branch Path"].map(_canonical_stock_share_branch_from_stock_path)
    source = source[
        source["Variable"].eq("Stock")
        & source["_canonical_stock_share_branch"].astype(str).ne("")
    ].copy()
    source[str(BASE_YEAR)] = pd.to_numeric(source[str(BASE_YEAR)], errors="coerce")
    stock_by_branch = source.groupby("_canonical_stock_share_branch", dropna=False)[str(BASE_YEAR)].sum()

    new_rows = []
    scenarios = df["Scenario"].dropna().astype(str).loc[lambda s: s.ne("")].unique().tolist()
    if not scenarios:
        scenarios = ["Current Accounts"]

    for scenario in scenarios:
        for transport_type, branch_paths in VEHICLE_TYPE_STOCK_SHARE_BRANCHES.items():
            transport_total = float(stock_by_branch.reindex(branch_paths).fillna(0.0).sum())
            for branch_path in branch_paths:
                share = 0.0
                if transport_total > 0:
                    share = float(stock_by_branch.get(branch_path, 0.0)) / transport_total * 100.0
                existing_mask = (
                    df["Branch Path"].eq(branch_path)
                    & df["Variable"].eq("Stock Share")
                    & df["Scenario"].eq(scenario)
                )
                if existing_mask.any():
                    for idx in df[existing_mask].index:
                        df.at[idx, str(BASE_YEAR)] = share
                        df.at[idx, "Scale"] = "%"
                        df.at[idx, "Units"] = "Share"
                        df.at[idx, "Per..."] = ""
                        # Seed future years to base-year share only if researcher hasn't set them.
                        for yr in STOCK_SHARE_PROJECTION_YEARS:
                            existing_val = df.at[idx, str(yr)]
                            if pd.isna(existing_val):
                                df.at[idx, str(yr)] = share
                    continue
                new_row = {column: pd.NA for column in MODULE1_INPUT_COLUMNS}
                # Also initialise projection-year columns that aren't in MODULE1_INPUT_COLUMNS yet.
                for yr in STOCK_SHARE_PROJECTION_YEARS:
                    new_row[str(yr)] = share
                new_row.update(
                    {
                        "Branch Path": branch_path,
                        "Variable": "Stock Share",
                        "Scenario": scenario,
                        "Region": economy.name,
                        "Scale": "%",
                        "Units": "Share",
                        "Per...": "",
                        str(BASE_YEAR): share,
                        "input_source": "provided",
                        "standardized_label_status": "standardized",
                        "notes": (
                            f"Base-year stock split derived from {BASE_YEAR} Stock rows; "
                            f"{', '.join(str(y) for y in STOCK_SHARE_PROJECTION_YEARS)} seeded to "
                            "base-year value — edit to define a trajectory."
                        ),
                        "source_type": "derived_from_stock",
                        "source_name": "Module 1 base-year Stock rows",
                        "source_scope": transport_type,
                        "source_date": SOURCE_DATE,
                        "default_version": DEFAULT_VERSION,
                        "researcher_review_recommended": False,
                        "review_reason": "",
                    }
                )
                new_rows.append(new_row)

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    # Return only canonical columns, plus any projection-year columns we added.
    output_cols = MODULE1_INPUT_COLUMNS + [
        str(yr) for yr in STOCK_SHARE_PROJECTION_YEARS if str(yr) not in MODULE1_INPUT_COLUMNS
    ]
    return df[[c for c in output_cols if c in df.columns]]


def build_default_assumptions(economy: EconomyInfo, scenarios: Iterable[str], years: Iterable[int]) -> pd.DataFrame:
    raise RuntimeError(
        "Synthetic seed CSV defaults are archived. Generate Module 1 defaults from "
        "back-end/data/road_model/processed_source or road_model_default_input_workbook.xlsx."
    )

    rows: list[dict[str, object]] = []
    reconciliation_values = {
        "reconciliation_weight_stock": _assumption_value("reconciliation_weight_stock", 0.0),
        "reconciliation_weight_mileage": _assumption_value("reconciliation_weight_mileage", 0.0),
        "reconciliation_weight_efficiency": _assumption_value("reconciliation_weight_efficiency", 0.0),
        "reconciliation_bound_lower_mileage": _assumption_value("reconciliation_bound_lower_mileage", 0.0),
        "reconciliation_bound_upper_mileage": _assumption_value("reconciliation_bound_upper_mileage", 0.0),
        "reconciliation_bound_lower_efficiency": _assumption_value("reconciliation_bound_lower_efficiency", 0.0),
        "reconciliation_bound_upper_efficiency": _assumption_value("reconciliation_bound_upper_efficiency", 0.0),
    }
    turnover_bounds = {
        "lower": _assumption_value("turnover_rate_bound_lower", 0.0),
        "upper": _assumption_value("turnover_rate_bound_upper", 0.0),
    }
    passenger_saturation_cfg = {
        "vehicles_per_1000_people": _assumption_value("passenger_saturation_vehicles_per_1000_people", 0.0),
        "reached": _assumption_value("passenger_saturation_reached", 0.0),
    }
    phev_formula = {
        "base": _assumption_value("phev_electric_driving_share_formula.base", 0.0),
        "max": _assumption_value("phev_electric_driving_share_formula.max", 0.0),
        "annual_change": _assumption_value("phev_electric_driving_share_formula.annual_change", 0.0),
    }
    max_age = int(_assumption_value("age_profiles.max_age", 0.0))
    passenger_age_profile = {
        "survival_age_divisor": _assumption_value("age_profiles.passenger.survival_age_divisor", 1.0),
        "survival_exponent": _assumption_value("age_profiles.passenger.survival_exponent", 1.0),
        "vintage_decay_base": _assumption_value("age_profiles.passenger.vintage_decay_base", 1.0),
    }
    freight_age_profile = {
        "survival_age_divisor": _assumption_value("age_profiles.freight.survival_age_divisor", 1.0),
        "survival_exponent": _assumption_value("age_profiles.freight.survival_exponent", 1.0),
        "vintage_decay_base": _assumption_value("age_profiles.freight.vintage_decay_base", 1.0),
    }
    vehicle_equivalent_bounds = {
        "passenger_car": {
            "lower": _assumption_value("vehicle_equivalent_bounds.passenger_car.lower", 1.0),
            "upper": _assumption_value("vehicle_equivalent_bounds.passenger_car.upper", 1.0),
        },
        "suv_light_truck": {
            "lower": _assumption_value("vehicle_equivalent_bounds.suv_light_truck.lower", 1.0),
            "upper": _assumption_value("vehicle_equivalent_bounds.suv_light_truck.upper", 1.0),
        },
        "bus": {
            "lower": _assumption_value("vehicle_equivalent_bounds.bus.lower", 1.0),
            "upper": _assumption_value("vehicle_equivalent_bounds.bus.upper", 1.0),
        },
        "motorcycle": {
            "lower": _assumption_value("vehicle_equivalent_bounds.motorcycle.lower", 1.0),
            "upper": _assumption_value("vehicle_equivalent_bounds.motorcycle.upper", 1.0),
        },
    }
    mileage_annual_change = _assumption_value("mileage_annual_change", 0.0)
    efficiency_annual_change = _assumption_value("efficiency_annual_change", 0.0)

    for scenario in scenarios:
        for transport_type in ["passenger", "freight"]:
            for parameter, default_value in reconciliation_values.items():
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type="all",
                        drive="all",
                        fuel="all",
                        parameter=parameter,
                        value=default_value,
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
                    parameter="turnover_rate_bound_lower",
                        value=float(turnover_bounds.get("lower", 0.0)),
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
                    parameter="turnover_rate_bound_upper",
                        value=float(turnover_bounds.get("upper", 0.0)),
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
                        value=float(passenger_saturation_cfg.get("vehicles_per_1000_people", 0.0)),
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
                        parameter="passenger_saturation_reached",
                        value=float(passenger_saturation_cfg.get("reached", 0.0)),
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
                        value=min(
                            float(phev_formula.get("max", 0.0)),
                            float(phev_formula.get("base", 0.0))
                            * _year_multiplier(year, float(phev_formula.get("annual_change", 0.0))),
                        ),
                    )
                )
            for age in range(0, max_age + 1):
                if transport_type == "freight":
                    survival = max(
                        0.0,
                        1 - (age / float(freight_age_profile.get("survival_age_divisor", 1.0)))
                        ** float(freight_age_profile.get("survival_exponent", 1.0)),
                    )
                    vintage_weight = float(freight_age_profile.get("vintage_decay_base", 1.0)) ** age
                else:
                    survival = max(
                        0.0,
                        1 - (age / float(passenger_age_profile.get("survival_age_divisor", 1.0)))
                        ** float(passenger_age_profile.get("survival_exponent", 1.0)),
                    )
                    vintage_weight = float(passenger_age_profile.get("vintage_decay_base", 1.0)) ** age

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
                bounds = dict(vehicle_equivalent_bounds.get(vehicle_type, {}))
                lower_bound = float(bounds.get("lower", vehicle_equivalent_weight))
                upper_bound = float(bounds.get("upper", vehicle_equivalent_weight))
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
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type=vehicle_type,
                        drive="all",
                        fuel="all",
                        parameter="vehicle_equivalent_weight_lower_bound",
                        value=lower_bound,
                    )
                )
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type=vehicle_type,
                        drive="all",
                        fuel="all",
                        parameter="vehicle_equivalent_weight_upper_bound",
                        value=upper_bound,
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
                        value=MILEAGE_KM_PER_YEAR[vehicle_type] * _year_multiplier(year, mileage_annual_change),
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
                            value=EFFICIENCY_MJ_PER_KM[drive] * 100 * _year_multiplier(year, efficiency_annual_change),
                        )
                    )

            if "ice_gasoline" in drive_shares and "ice_diesel" in drive_shares:
                paired_share_note = (
                    "Paired gasoline/diesel share control at the top-level vehicle type only; "
                    "excludes alternative fuels such as biogasoline and other non-conventional blends."
                )
                rows.append(
                    _row(
                        economy=economy,
                        scenario=scenario,
                        year=BASE_YEAR,
                        transport_type=transport_type,
                        vehicle_type=vehicle_type,
                        drive="all",
                        fuel="all",
                        parameter="gasoline_diesel_share_tolerance",
                        value=DEFAULT_GASOLINE_DIESEL_SHARE_TOLERANCE,
                        notes=paired_share_note,
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
        economy_df = load_processed_source_inputs(economy=economy, scenarios=scenarios)
        if economy_df.empty:
            raise ValueError(
                f"No processed Road Module 1 source rows found for {economy.code}. "
                "Run back-end/scripts/prepare_road_source.py or use write_all_economy_packages "
                "with road_model_default_input_workbook.xlsx."
            )
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
                "source_type": "processed_source_or_default_input_workbook",
                "source_name": "processed_source/road_module1_source_<ECONOMY>.csv",
                "source_scope": "economy_specific",
                "source_date": SOURCE_DATE,
                "default_version": DEFAULT_VERSION,
                "researcher_review_recommended": False,
                "notes": "Canonical Module 1 values come from preprocessed LEAP source rows or the legacy default input workbook fallback.",
            }
        )
    return pd.DataFrame(rows)


def _placeholder_default_value_rows(default_filled_df: pd.DataFrame) -> pd.DataFrame:
    """Return rows that still carry placeholder default values after source overlays."""
    df = default_filled_df.copy()
    year_values = df[YEAR_COLUMNS].apply(pd.to_numeric, errors="coerce")
    has_any_year_value = year_values.notna().any(axis=1)
    source_type = df["source_type"].astype(str).str.strip().str.lower()

    placeholder_mask = has_any_year_value & source_type.eq("default_best_guess")
    return df[placeholder_mask].copy()


def _raise_if_placeholder_defaults_remain(default_filled_df: pd.DataFrame, economy: EconomyInfo) -> None:
    remaining_defaults = _placeholder_default_value_rows(default_filled_df)
    if remaining_defaults.empty:
        return

    grouped = (
        remaining_defaults
        .groupby(["Variable", "input_source", "source_type"], dropna=False)
        .size()
        .reset_index(name="row_count")
        .sort_values(["row_count", "Variable"], ascending=[False, True])
    )
    summary_lines = [
        f"- {row.Variable} | input_source={row.input_source} | source_type={row.source_type} | rows={int(row.row_count)}"
        for row in grouped.itertuples(index=False)
    ]

    sample_cols = ["Branch Path", "Variable", "Scenario", "Region", "input_source", "source_type"]
    sample_rows = remaining_defaults[sample_cols].head(25)
    sample_lines = [
        f"- {row['Variable']} | {row['Branch Path']} | {row['Scenario']} | {row['Region']} | {row['input_source']} | {row['source_type']}"
        for _, row in sample_rows.iterrows()
    ]

    raise ValueError(
        "Strict source-backed generation failed for "
        f"{economy.code}: {len(remaining_defaults)} rows still use placeholder defaults. "
        "Update source files or loader logic so all values come from real inputs.\n\n"
        "Counts by variable/source:\n"
        + "\n".join(summary_lines)
        + "\n\nSample affected rows:\n"
        + "\n".join(sample_lines)
    )


def write_economy_package(
    economy: EconomyInfo,
    output_root: Path,
    scenarios: Iterable[str] = DEFAULT_SCENARIOS,
    years: Iterable[int] = DEFAULT_YEARS,
    default_input_df: pd.DataFrame | None = None,
    enforce_source_backed_values: bool = True,
) -> dict[str, Path]:
    economy_dir = output_root / DEFAULT_VERSION / economy.code
    economy_dir.mkdir(parents=True, exist_ok=True)

    processed_source_filled = load_processed_source_inputs(economy=economy, scenarios=scenarios)
    if not processed_source_filled.empty:
        default_filled = processed_source_filled.copy()
    elif default_input_df is not None and not default_input_df.empty:
        source_regions = _transport_leap_source_regions(economy)
        default_filled = default_input_df[default_input_df["Region"].isin(source_regions)].copy()
        scenario_names = {_format_leap_scenario(scenario) for scenario in scenarios}
        scenario_aliases = set(scenario_names)
        if "Current Accounts" in scenario_names:
            scenario_aliases.add("Reference")
        if "Reference" in scenario_names:
            scenario_aliases.add("Current Accounts")
        default_filled = default_filled[default_filled["Scenario"].isin(scenario_aliases)].copy()
        if default_filled.empty:
            raise ValueError(f"No Road model default input workbook rows found for {economy.code}.")
        default_filled["Region"] = economy.name
        workbook_source_name = Path(ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH).name
        default_filled["input_source"] = "provided"
        default_filled.loc[
            default_filled["source_type"].astype(str).str.strip().str.lower().eq("default_best_guess"),
            "source_type",
        ] = "default_input_workbook"
        default_filled.loc[
            default_filled["source_name"].astype(str).str.strip().eq(""),
            "source_name",
        ] = workbook_source_name
        default_filled.loc[
            default_filled["source_scope"].astype(str).str.strip().eq(""),
            "source_scope",
        ] = economy.code
        default_filled.loc[
            default_filled["source_date"].astype(str).str.strip().eq(""),
            "source_date",
        ] = SOURCE_DATE
        default_filled = default_filled[MODULE1_INPUT_COLUMNS]
    else:
        raise ValueError(
            f"No Road model source rows found for {economy.code}. Add "
            f"{_processed_source_path(economy)} or provide {ROAD_MODEL_DEFAULT_INPUT_WORKBOOK_PATH}."
        )

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
    # HEV is out of scope for Motorcycles (LPV-only policy), but PHEV and FCEV
    # are in scope — they should appear with 0 stock in the base year.
    is_motorcycle_hev = (
        branch_series.str.startswith("Demand\\Passenger road\\Motorcycles\\")
        & branch_series.str.contains(r"\\HEV(?:\\|$)", regex=True)
    )
    default_filled = default_filled[
        ~((is_hev_or_erev & ~is_lpv_branch) | is_truck_phev | is_motorcycle_hev)
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
    default_filled, _ = overlay_phev_utilisation_rates(
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
    default_filled = _ensure_vehicle_type_stock_share_rows(default_filled, economy)
    # Rows created by overlay functions may have NA in metadata columns — fill them
    # so downstream validation (which expects strings) doesn't fail.
    for _col, _fill in [("input_source", "provided"), ("source_type", ""), ("source_name", ""),
                         ("source_scope", ""), ("source_date", ""), ("notes", ""),
                         ("standardized_label_status", "standardized")]:
        if _col in default_filled.columns:
            default_filled[_col] = default_filled[_col].fillna(_fill)
    default_filled, final_value_override_report = apply_final_value_overrides_with_report(default_filled, economy)
    # Temporary policy: deactivate researcher-review prioritization globally so
    # all rows are presented equally for manual review.
    default_filled["researcher_review_recommended"] = False
    default_filled["review_reason"] = ""

    if enforce_source_backed_values:
        _raise_if_placeholder_defaults_remain(default_filled, economy)

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
        "default_filled_inputs": economy_dir / _default_filled_inputs_filename(economy.code),
    }

    # Remove old artifacts from prior runs so each economy folder stays current.
    for extra_file in economy_dir.glob("road_module1_*.csv"):
        if extra_file.name != paths["default_filled_inputs"].name:
            extra_file.unlink(missing_ok=True)

    for extra_file in economy_dir.glob("road_module1_*.xlsx"):
        extra_file.unlink(missing_ok=True)

    for extra_file in economy_dir.glob("road_module1_*.html"):
        extra_file.unlink(missing_ok=True)

    override_report_csv_path, override_report_html_path = write_final_value_override_visibility_report(
        report_df=final_value_override_report,
        output_dir=economy_dir,
        economy=economy,
    )
    if override_report_csv_path is not None:
        paths["final_value_override_report_csv"] = override_report_csv_path
    if override_report_html_path is not None:
        paths["final_value_override_report_html"] = override_report_html_path

    long_defaults = _wide_defaults_to_long(default_filled, economy=economy.code)
    long_defaults.to_csv(paths["default_filled_inputs"], index=False)

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
    enforce_source_backed_values: bool = True,
) -> dict[str, dict[str, Path]]:
    output_root = Path(output_root)
    version_root = output_root / DEFAULT_VERSION
    version_root.mkdir(parents=True, exist_ok=True)
    default_input_df = load_default_input_workbook(
        workbook_path=default_input_workbook_path,
        require_exists=require_default_input_workbook,
    )

    has_processed_source = PROCESSED_SOURCE_DIR.exists() and any(
        PROCESSED_SOURCE_DIR.glob("road_module1_source_*.csv")
    )
    if enforce_source_backed_values and default_input_df.empty and not has_processed_source:
        raise ValueError(
            "Strict source-backed generation requires preprocessed Road Module 1 source rows "
            "or a populated Road model default input workbook. "
            f"Expected data at: {PROCESSED_SOURCE_DIR} or {default_input_workbook_path}"
        )

    catalog_path = version_root / "road_module1_default_assumptions_catalog.csv"
    build_default_catalog().to_csv(catalog_path, index=False)

    schema_contract_path = version_root / "road_module1_input_schema_contract.csv"
    build_schema_contract().to_csv(schema_contract_path, index=False)

    all_paths = {}
    economies_to_write = _economies_from_default_input(default_input_df)
    if not economies_to_write:
        economies_to_write = get_economies()

    for economy in economies_to_write:
        all_paths[economy.code] = write_economy_package(
            economy=economy,
            output_root=output_root,
            scenarios=scenarios,
            years=years,
            default_input_df=default_input_df,
            enforce_source_backed_values=enforce_source_backed_values,
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


def _default_filled_inputs_filename(economy: str) -> str:
    return f"road_module1_values_{economy}.csv"


def _legacy_default_filled_inputs_filename(economy: str) -> str:
    return f"road_module1_default_filled_inputs_{economy}.csv"


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
    legacy_filepath = filepath.with_name(_legacy_default_filled_inputs_filename(economy))
    legacy_unsuffixed_filepath = filepath.with_name("road_module1_default_filled_inputs.csv")

    if not filepath.exists():
        if legacy_filepath.exists():
            filepath = legacy_filepath
        elif legacy_unsuffixed_filepath.exists():
            filepath = legacy_unsuffixed_filepath

    if not filepath.exists():
        raise FileNotFoundError(
            "Default-filled Road model input workbook or CSV not found: "
            f"{workbook_path} / {filepath} / {legacy_filepath} / {legacy_unsuffixed_filepath}"
        )
    df = pd.read_csv(filepath)
    if set(MODULE1_LONG_KEY_COLUMNS + ["Value"]).issubset(df.columns):
        return _long_defaults_to_ui_wide(
            df,
            economy=economy,
            region_name=get_economy_info(economy).name if economy else None,
        )
    return df


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
    return output_root / version / economy / _default_filled_inputs_filename(economy)


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


def _normalize_long_upload_file(provided_df: pd.DataFrame) -> pd.DataFrame:
    normalized_df = provided_df.copy()
    normalized_df = normalized_df.rename(columns={column: str(column).strip() for column in normalized_df.columns})
    missing_columns = [column for column in MODULE1_LONG_KEY_COLUMNS for _ in [0] if column not in normalized_df.columns]
    if missing_columns:
        raise ValueError("Provided values file is missing required long-key columns: " + ", ".join(missing_columns))
    for column in MODULE1_LONG_KEY_COLUMNS:
        normalized_df[column] = normalized_df[column].fillna("").astype(str).str.strip()
    normalized_df["Year"] = pd.to_numeric(normalized_df["Year"], errors="coerce")
    if normalized_df["Year"].isna().any():
        raise ValueError("Provided values file has non-numeric Year values.")
    normalized_df["Year"] = normalized_df["Year"].astype(int)
    if "Value" in normalized_df.columns:
        normalized_df["Value"] = pd.to_numeric(normalized_df["Value"], errors="coerce")
    duplicate_mask = normalized_df.duplicated(subset=MODULE1_LONG_KEY_COLUMNS, keep=False)
    if duplicate_mask.any():
        sample = normalized_df.loc[duplicate_mask, MODULE1_LONG_KEY_COLUMNS].head(5).to_dict(orient="records")
        raise ValueError(f"Provided values file has duplicate row keys. Sample: {sample}")
    return normalized_df


def _apply_long_provided_values_file(
    default_filled_df: pd.DataFrame,
    provided_df: pd.DataFrame,
    source_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    completed_df = default_filled_df.copy()
    for year_col in YEAR_COLUMNS:
        if year_col in completed_df.columns:
            completed_df[year_col] = pd.to_numeric(completed_df[year_col], errors="coerce")

    normalized_provided_df = _normalize_long_upload_file(provided_df)
    uploaded_economies = normalized_provided_df["Economy"].dropna().astype(str).str.strip().unique().tolist()
    if len(uploaded_economies) != 1:
        raise ValueError("Provided values file must contain exactly one Economy value.")
    default_long = _wide_defaults_to_long(completed_df, economy=uploaded_economies[0])
    default_key_set = {
        tuple(row[column] for column in MODULE1_LONG_KEY_COLUMNS)
        for _, row in default_long.iterrows()
    }
    report_rows = []

    for _, provided_row in normalized_provided_df.iterrows():
        key = tuple(provided_row[column] for column in MODULE1_LONG_KEY_COLUMNS)
        if key not in default_key_set:
            report_rows.append(
                {
                    "status": "fail",
                    "issue": "provided_key_not_found",
                    "details": str({column: provided_row[column] for column in MODULE1_LONG_KEY_COLUMNS}),
                }
            )
            continue

        value = provided_row.get("Value", pd.NA)
        if pd.isna(value):
            continue
        branch_path = provided_row["Branch Path"]
        variable = provided_row["Variable"]
        scenario = provided_row["Scenario"]
        year_col = str(int(provided_row["Year"]))
        target_mask = (
            completed_df["Branch Path"].eq(branch_path)
            & completed_df["Variable"].eq(variable)
            & completed_df["Scenario"].eq(scenario)
        )
        if year_col not in completed_df.columns:
            completed_df[year_col] = pd.NA
        for idx in completed_df[target_mask].index:
            old_value = completed_df.at[idx, year_col]
            if pd.notna(old_value) and float(old_value) == float(value):
                continue
            completed_df.at[idx, year_col] = float(value)
            completed_df.at[idx, "input_source"] = "provided"
            completed_df.at[idx, "source_type"] = "researcher_provided_file"
            completed_df.at[idx, "source_name"] = source_name
            completed_df.at[idx, "source_date"] = datetime.now().strftime("%Y-%m-%d")
            if "Comment" in normalized_provided_df.columns:
                completed_df.at[idx, "notes"] = str(provided_row.get("Comment", "") or "").strip()
            report_rows.append(
                {
                    "status": "applied",
                    "issue": "",
                    "details": f"{year_col}: {branch_path} | {variable} | {scenario}",
                }
            )

    report_df = pd.DataFrame(report_rows)
    if report_df.empty:
        report_df = pd.DataFrame(columns=["status", "issue", "details"])
    return completed_df[MODULE1_INPUT_COLUMNS], report_df


def apply_provided_values_file(
    default_filled_df: pd.DataFrame,
    provided_df: pd.DataFrame,
    source_name: str = "uploaded_provided_values_file",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Overlay uploaded provided values onto the generated provided-value template."""
    if set(MODULE1_LONG_KEY_COLUMNS + ["Value"]).issubset(provided_df.columns):
        return _apply_long_provided_values_file(default_filled_df, provided_df, source_name)

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
            existing_notes = str(completed_df.at[target_idx, "notes"] or "").strip()
            if not existing_notes:
                completed_df.at[target_idx, "notes"] = comment
            elif comment not in existing_notes:
                completed_df.at[target_idx, "notes"] = f"{existing_notes} {comment}".strip()

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
