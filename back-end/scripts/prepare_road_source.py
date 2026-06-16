#%%
"""
Prepare Road Module 1 processed source CSVs from a LEAP export workbook.

This script reads a LEAP transport export with the header on Excel row 3,
filters road-relevant rows, expands either annual FOR_VIEWING columns or LEAP
Data(...) expressions into long rows, and writes one intermediate source CSV
per economy.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


# --- Stable paths ---
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_DIR = BACKEND_DIR.parent
ROAD_MODEL_DATA_DIR = BACKEND_DIR / "data" / "road_model"
DEFAULT_EXPORT_PATH = (
    ROAD_MODEL_DATA_DIR
    / "leap_import_workbooks"
    / "transport_leap_export_combined_ALL_ECONS_domestic_international_Target_20260526.xlsx"
)
DEFAULT_EXPORT_SCENARIOS = ("Target", "Reference")
PROCESSED_SOURCE_DIR = ROAD_MODEL_DATA_DIR / "processed_source"

EXPORT_SHEET_NAME = "FOR_VIEWING"
EXPORT_HEADER_ROW = 2
ROAD_PREFIXES = ("Demand\\Passenger road", "Demand\\Freight road")
KEEP_COLUMNS = ["Branch Path", "Variable", "Scenario", "Year", "Value", "Units"]


# PHEV is only valid for LPVs and LCVs. Buses and Motorcycles may appear in
# the LEAP export with PHEV drive-type rows, but these are out of scope.
PHEV_OUT_OF_SCOPE_VEHICLE_SEGMENTS = ("\\Buses\\", "\\Motorcycles\\")


def _is_out_of_scope_phev_row(branch_path: str) -> bool:
    if "PHEV" not in branch_path:
        return False
    return any(seg in branch_path for seg in PHEV_OUT_OF_SCOPE_VEHICLE_SEGMENTS)


ECONOMY_REGION_TO_CODE = {
    "Australia": "01AUS",
    "Brunei Darussalam": "02BD",
    "Canada": "03CDA",
    "Chile": "04CHL",
    "People's Republic of China": "05PRC",
    "China": "05PRC",
    "Hong Kong, China": "06HKC",
    "Indonesia": "07INA",
    "Japan": "08JPN",
    "Republic of Korea": "09ROK",
    "Korea": "09ROK",
    "Malaysia": "10MAS",
    "Mexico": "11MEX",
    "New Zealand": "12NZ",
    "Papua New Guinea": "13PNG",
    "Peru": "14PE",
    "Philippines": "15PHL",
    "Russia": "16RUS",
    "Singapore": "17SGP",
    "Chinese Taipei": "18CT",
    "Thailand": "19THA",
    "United States of America": "20USA",
    "United States": "20USA",
    "Viet Nam": "21VN",
}


def parse_leap_expression(expression: object) -> dict[int, float]:
    """Parse a LEAP scalar or Data(year, value, ...) expression into a year/value dict."""
    if pd.isna(expression):
        return {}
    text = str(expression).strip()
    if not text:
        return {}
    try:
        return {2022: float(text)}
    except ValueError:
        pass
    match = re.match(r"^Data\((.*)\)$", text, flags=re.IGNORECASE)
    if not match:
        return {}
    parts = [part.strip() for part in match.group(1).split(",")]
    values: dict[int, float] = {}
    for idx in range(0, len(parts) - 1, 2):
        try:
            year = int(float(parts[idx]))
            value = float(parts[idx + 1])
        except ValueError:
            continue
        values[year] = value
    return values


def load_road_export_rows(export_path: Path, sheet_name: str = EXPORT_SHEET_NAME) -> pd.DataFrame:
    """Load and filter road rows from the LEAP export workbook."""
    if not export_path.exists():
        raise FileNotFoundError(f"LEAP export workbook not found: {export_path}")
    df = pd.read_excel(export_path, sheet_name=sheet_name, header=EXPORT_HEADER_ROW)
    df = df.copy()
    df["Branch Path"] = df["Branch Path"].fillna("").astype(str).str.strip()
    df["Variable"] = df["Variable"].fillna("").astype(str).str.strip()
    road_mask = df["Branch Path"].str.startswith(ROAD_PREFIXES)
    df = df[road_mask].copy()
    phev_oos_mask = df["Branch Path"].apply(_is_out_of_scope_phev_row)
    return df[~phev_oos_mask].copy()


def _year_columns(export_df: pd.DataFrame) -> list[object]:
    year_columns: list[object] = []
    for column in export_df.columns:
        try:
            year = int(float(column))
        except (TypeError, ValueError):
            continue
        if 1900 <= year <= 2200:
            year_columns.append(column)
    return year_columns


def expand_for_viewing_to_long(export_df: pd.DataFrame) -> pd.DataFrame:
    """Expand annual FOR_VIEWING columns into the processed source long schema."""
    year_columns = _year_columns(export_df)
    if not year_columns:
        return pd.DataFrame(columns=["Region", *KEEP_COLUMNS])
    id_columns = ["Region", "Branch Path", "Variable", "Scenario", "Units"]
    long_df = export_df[id_columns + year_columns].melt(
        id_vars=id_columns,
        value_vars=year_columns,
        var_name="Year",
        value_name="Value",
    )
    long_df["Year"] = pd.to_numeric(long_df["Year"], errors="coerce")
    long_df["Value"] = pd.to_numeric(long_df["Value"], errors="coerce")
    long_df = long_df.dropna(subset=["Year", "Value"]).copy()
    long_df["Year"] = long_df["Year"].astype(int)
    return long_df


def expand_export_to_long(export_df: pd.DataFrame) -> pd.DataFrame:
    """Expand LEAP Expression rows into the processed source long schema."""
    if "Expression" not in export_df.columns:
        return expand_for_viewing_to_long(export_df)

    rows: list[dict[str, object]] = []
    for _, source_row in export_df.iterrows():
        values = parse_leap_expression(source_row.get("Expression"))
        for year, value in values.items():
            rows.append(
                {
                    "Region": source_row.get("Region", ""),
                    "Branch Path": source_row.get("Branch Path", ""),
                    "Variable": source_row.get("Variable", ""),
                    "Scenario": source_row.get("Scenario", ""),
                    "Year": year,
                    "Value": value,
                    "Units": source_row.get("Units", ""),
                }
            )
    return pd.DataFrame(rows)


def _transport_export_sort_key(path: Path) -> tuple[str, float]:
    match = re.search(r"_(\d{8})(?:\D|$)", path.stem)
    date_token = match.group(1) if match else ""
    return date_token, path.stat().st_mtime


def find_latest_all_economies_exports(
    workbook_dir: Path = ROAD_MODEL_DATA_DIR / "leap_import_workbooks",
    scenarios: Iterable[str] = DEFAULT_EXPORT_SCENARIOS,
) -> list[Path]:
    """Find the latest combined all-economies export for each requested scenario."""
    export_paths: list[Path] = []
    for scenario in scenarios:
        scenario_text = str(scenario).strip()
        if not scenario_text:
            continue
        candidates = [
            path
            for path in workbook_dir.glob(
                f"transport_leap_export_combined_ALL_ECONS*_domestic_international_{scenario_text}_*.xlsx"
            )
            if path.is_file()
        ]
        if not candidates:
            continue
        export_paths.append(max(candidates, key=_transport_export_sort_key))
    return export_paths


def write_processed_source_files(long_df: pd.DataFrame, output_dir: Path) -> list[Path]:
    """Write one processed source CSV per economy."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for region, region_df in long_df.groupby("Region", dropna=False):
        economy = ECONOMY_REGION_TO_CODE.get(str(region).strip())
        if not economy:
            continue
        output = output_dir / f"road_module1_source_{economy}.csv"
        region_df[KEEP_COLUMNS].sort_values(["Branch Path", "Variable", "Scenario", "Year"]).to_csv(output, index=False)
        written.append(output)
    return written


def prepare_road_source(
    export_path: Path | Iterable[Path] | None = DEFAULT_EXPORT_PATH,
    output_dir: Path = PROCESSED_SOURCE_DIR,
) -> list[Path]:
    """Run the LEAP-export-to-processed-source preparation workflow."""
    os.chdir(REPO_DIR)
    if export_path is None:
        export_paths = find_latest_all_economies_exports()
    elif isinstance(export_path, (str, Path)):
        export_paths = [Path(export_path)]
    else:
        export_paths = [Path(path) for path in export_path]

    if not export_paths:
        raise FileNotFoundError(
            "No all-economies Target/Reference LEAP export workbooks found in "
            f"{ROAD_MODEL_DATA_DIR / 'leap_import_workbooks'}."
        )

    long_frames: list[pd.DataFrame] = []
    for source_order, path in enumerate(export_paths):
        export_df = load_road_export_rows(path)
        long_df = expand_export_to_long(export_df)
        if long_df.empty:
            continue
        long_df = long_df.copy()
        long_df["_source_order"] = source_order
        long_frames.append(long_df)

    if not long_frames:
        return []

    long_df = pd.concat(long_frames, ignore_index=True)
    key_columns = ["Region", "Branch Path", "Variable", "Scenario", "Year"]
    long_df = (
        long_df.sort_values([*key_columns, "_source_order"])
        .drop_duplicates(subset=key_columns, keep="last")
        .drop(columns=["_source_order"])
    )
    return write_processed_source_files(long_df, output_dir)


# --- Frequently changed toggles ---
RUN_PREPARE_ROAD_SOURCE = False
EXPORT_PATH = None
OUTPUT_DIR = PROCESSED_SOURCE_DIR


# --- Run blocks ---
if __name__ == "__main__":
    if RUN_PREPARE_ROAD_SOURCE:
        WRITTEN_FILES = prepare_road_source(EXPORT_PATH, OUTPUT_DIR)
        print(f"Wrote {len(WRITTEN_FILES)} processed source files.")
        for path in WRITTEN_FILES[:10]:
            print(path)

#%%
