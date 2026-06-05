"""
One-time preprocessing script to replace large source files with smaller equivalents:

1. Splits transport_leap_export_combined_ALL_ECONS_*.xlsx into per-economy files
   (code already prefers per-economy files over ALL_ECONS)

2. Filters 00APEC_2024_low_with_subtotals.csv to only rows the app actually uses:
   - is_subtotal=True rows (used by get_total_energy)
   - is_subtotal=False rows where product prefix <= 17 (used by get_active_fuels / get_fuel_limits)

Run from repo root: python back-end/scripts/preprocess_large_files.py
"""

import re
from pathlib import Path

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = BACKEND_ROOT / "data"
LEAP_EXPORT_DIR = DATA_ROOT / "road_model" / "leap_import_workbooks"
MULTINODE_DIR = DATA_ROOT / "multinodeenergy_backend"

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

REGION_TO_ECONOMY_CODE = {
    region: code
    for code, regions in ECONOMY_CODE_TO_LEAP_REGION_NAMES.items()
    for region in regions
}


def economy_to_token(economy_code: str) -> str:
    code = economy_code.strip().upper()
    if len(code) >= 5 and code[:2].isdigit():
        return f"{code[:2]}_{code[2:]}"
    return code


def split_leap_export_xlsx():
    candidates = sorted(LEAP_EXPORT_DIR.glob("transport_leap_export_combined_ALL_ECONS_*.xlsx"))
    if not candidates:
        print("No ALL_ECONS xlsx found — skipping split.")
        return
    source = candidates[-1]
    date_match = re.search(r"Target_(\d+)", source.stem)
    date_tag = date_match.group(1) if date_match else "unknown"
    print(f"Splitting {source.name} ...")

    df = pd.read_excel(source, sheet_name="FOR_VIEWING", header=2)
    df.columns = df.columns.str.strip()

    if "Region" not in df.columns:
        print("ERROR: 'Region' column not found in FOR_VIEWING sheet.")
        return

    written = 0
    for region_name, group in df.groupby("Region", sort=False):
        economy_code = REGION_TO_ECONOMY_CODE.get(str(region_name).strip())
        if not economy_code:
            print(f"  WARNING: no economy code for region '{region_name}' — skipping")
            continue
        token = economy_to_token(economy_code)
        out_name = f"transport_leap_export_combined_{token}_domestic_international_Target_{date_tag}.xlsx"
        out_path = LEAP_EXPORT_DIR / out_name

        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            # Write two blank rows then the data so header lands on row 3 (index 2), matching TRANSPORT_LEAP_EXPORT_HEADER_ROW=2
            blank = pd.DataFrame(columns=group.columns)
            blank.to_excel(writer, sheet_name="FOR_VIEWING", index=False, startrow=0)
            group.to_excel(writer, sheet_name="FOR_VIEWING", index=False, startrow=2, header=True)

        mb = out_path.stat().st_size / 1024 / 1024
        print(f"  {out_name}  ({mb:.1f} MB)")
        written += 1

    print(f"Split into {written} per-economy files.")
    print(f"You can now delete {source.name} from the repo.")


# Exact flows the frontend queries (see front-end/app.js sectors list)
QUERIED_FLOWS = {
    "14 Industry sector",
    "15 Transport sector",
    "16 Other sector",
    "16.01 Commercial and public services",
    "16.02 Residential",
}
# Frontend year range (front-end/app.js: for y = 2022 down to 2000)
YEAR_MIN = 2000
YEAR_MAX = 2022


def filter_apec_csv():
    candidates = sorted(MULTINODE_DIR.glob("00APEC_*.csv"))
    if not candidates:
        print("No APEC CSV found -- skipping filter.")
        return
    source = candidates[-1]
    print(f"Filtering {source.name} ...")

    df = pd.read_csv(source, low_memory=False)
    df.columns = df.columns.str.strip().str.lower()

    original_rows = len(df)
    original_mb = source.stat().st_size / 1024 / 1024

    # Keep only the rows for flows the app actually queries
    df = df[df["flows"].isin(QUERIED_FLOWS)].copy()

    # Drop year columns outside the frontend's selectable range
    year_cols_to_drop = [
        c for c in df.columns
        if str(c).strip().isdigit() and not (YEAR_MIN <= int(c) <= YEAR_MAX)
    ]
    df = df.drop(columns=year_cols_to_drop)

    df.to_csv(source, index=False)

    new_mb = source.stat().st_size / 1024 / 1024
    print(f"  Rows: {original_rows} -> {len(df)} ({original_rows - len(df)} removed)")
    print(f"  Year cols dropped: {len(year_cols_to_drop)} ({year_cols_to_drop[0] if year_cols_to_drop else 'none'}..{year_cols_to_drop[-1] if year_cols_to_drop else ''})")
    print(f"  Size: {original_mb:.1f} MB -> {new_mb:.1f} MB")


if __name__ == "__main__":
    split_leap_export_xlsx()
    print()
    filter_apec_csv()
