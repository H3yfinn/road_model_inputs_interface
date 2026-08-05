#%%
"""Generate the separate PRC zero-sales-year replacement-share override package."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
INTERFACE_REPO = BACKEND_DIR.parent
LEAP_TRANSPORT_REPO = INTERFACE_REPO.parent / "leap_transport"
SOURCE_CSV = BACKEND_DIR / "data/road_model/processed_source/road_module1_source_05PRC.csv"
WORKBOOK_DIR = BACKEND_DIR / "data/road_model/leap_import_workbooks"
CHECKPOINT = LEAP_TRANSPORT_REPO / "intermediate_data/transport_data_05_PRC_Target_2022_2060.pkl"
SURVIVAL_PATH = LEAP_TRANSPORT_REPO / "data/lifecycle_profiles/vehicle_survival_modified_05_PRC.xlsx"
VINTAGE_PATH = LEAP_TRANSPORT_REPO / "data/lifecycle_profiles/vintage_modelled_from_survival_05_PRC.xlsx"
OUTPUT_DIR = BACKEND_DIR / "data/road_model/final_value_overrides/sales_shares_9th_replacement"
OUTPUT_CSV = OUTPUT_DIR / "module1_final_value_overrides_05PRC.csv"

VEHICLE_TYPE_MAP = {
    "car": ("passenger", "LPVs", "small"),
    "suv": ("passenger", "LPVs", "medium"),
    "lt": ("passenger", "LPVs", "large"),
    "2w": ("passenger", "Motorcycles", "all"),
    "bus": ("passenger", "Buses", "all"),
    "lcv": ("freight", "LCVs", "all"),
    "mt": ("freight", "Trucks", "medium"),
    "ht": ("freight", "Trucks", "heavy"),
}

DRIVE_MAP = {
    "bev": "BEV",
    "fcev": "FCEV",
    "phev": "PHEV",
    "phev_d": "PHEV",
    "phev_g": "PHEV",
    "erev_d": "EREV",
    "erev_g": "EREV",
    "hev": "HEV",
    "hev_d": "HEV",
    "hev_g": "HEV",
    "ice": "ICE",
    "ice_d": "ICE",
    "ice_g": "ICE",
    "cng": "ICE",
    "lng": "ICE",
    "lpg": "ICE",
}


def _branch_path(transport_type: str, vehicle_type: str, size: str, drive: str) -> str:
    transport_label = "Passenger road" if transport_type == "passenger" else "Freight road"
    if size == "all":
        return rf"Demand\{transport_label}\{vehicle_type}\{drive}"
    return rf"Demand\{transport_label}\{vehicle_type}\{drive} {size}"


def build_override_rows() -> pd.DataFrame:
    sys.path.insert(0, str(LEAP_TRANSPORT_REPO / "codebase"))
    from functions.sales_curve_estimate import (  # pylint: disable=import-outside-toplevel
        compute_sales_from_stock_targets,
        load_survival_and_vintage_profiles,
    )

    source = pd.read_csv(SOURCE_CSV)
    source_leaf_rows = source[
        (source["Variable"] == "Sales Share")
        & (source["Scenario"] == "Target")
        & (source["Branch Path"].str.count(r"\\") >= 3)
    ].copy()
    allowed_branch_keys = set(
        zip(source_leaf_rows["Branch Path"], source_leaf_rows["Scenario"], source_leaf_rows["Year"])
    )
    workbook_candidates = sorted(
        WORKBOOK_DIR.glob("transport_leap_export_combined_05_PRC_domestic_international_Target_*.xlsx")
    )
    if workbook_candidates:
        workbook_df = pd.read_excel(workbook_candidates[-1], sheet_name="FOR_VIEWING", header=2)
        workbook_branches = workbook_df[
            (workbook_df["Variable"].fillna("").astype(str).str.strip() == "Sales Share")
            & (workbook_df["Scenario"].fillna("").astype(str).str.strip() == "Target")
            & (workbook_df["Branch Path"].fillna("").astype(str).str.count(r"\\") >= 3)
        ]["Branch Path"].dropna().astype(str).unique()
        allowed_branch_keys.update(
            (branch, "Target", year)
            for branch in workbook_branches
            for year in range(2023, 2061)
        )

    df = pd.read_pickle(CHECKPOINT)
    df = df[
        (df["Economy"] == "05_PRC")
        & (df["Scenario"] == "Target")
        & (df["Medium"] == "road")
        & (df["Transport Type"].isin(["passenger", "freight"]))
        & (df["Vehicle Type"].isin(VEHICLE_TYPE_MAP))
    ].copy()
    df["Date"] = pd.to_numeric(df["Date"], errors="coerce").astype(int)
    df["interface_parent"] = df["Vehicle Type"].map(lambda value: VEHICLE_TYPE_MAP[value][1])
    df["interface_drive"] = df["Drive"].map(DRIVE_MAP)
    df = df[df["interface_drive"].notna()].copy()

    current_parent_totals = df.groupby(["Date", "interface_parent"], dropna=False)["Sales"].sum()
    stock_series = df.groupby(["Date", "interface_parent", "Vehicle Type", "Drive"], dropna=False)["Stocks"].sum()

    survival, vintage = load_survival_and_vintage_profiles(
        SURVIVAL_PATH,
        VINTAGE_PATH,
        vehicle_keys=("PRC",),
        survival_is_cumulative=True,
    )
    survival_curve = survival["PRC"]
    vintage_profile = vintage["PRC"]

    replacement_detail: list[dict[str, object]] = []
    for (parent, vehicle_type), group in stock_series.groupby(level=[1, 2]):
        stock_wide = group.droplevel([1, 2]).unstack("Drive").fillna(0.0).sort_index()
        replacement = pd.DataFrame(index=stock_wide.index, columns=stock_wide.columns, dtype=float)
        for drive in stock_wide.columns:
            replacement[drive], _, _ = compute_sales_from_stock_targets(
                stock_wide[drive], survival_curve, vintage_profile, return_retirements=True
            )
        mapped_replacement = pd.DataFrame(index=replacement.index)
        for drive in replacement.columns:
            mapped_drive = DRIVE_MAP.get(str(drive))
            if mapped_drive:
                mapped_replacement[mapped_drive] = mapped_replacement.get(mapped_drive, 0.0) + replacement[drive]

        for year in replacement.index:
            for drive, value in mapped_replacement.loc[year].items():
                branch = _branch_path(
                    VEHICLE_TYPE_MAP[vehicle_type][0],
                    parent,
                    VEHICLE_TYPE_MAP[vehicle_type][2],
                    drive,
                )
                if (branch, "Target", int(year)) in allowed_branch_keys:
                    replacement_detail.append(
                        {
                            "parent": parent,
                            "year": int(year),
                            "branch": branch,
                            "value": float(value),
                        }
                    )

    replacement_detail_df = pd.DataFrame(replacement_detail)
    replacement_rows: list[dict[str, object]] = []
    for (parent, year), group in replacement_detail_df.groupby(["parent", "year"], dropna=False):
        if float(current_parent_totals.get((int(year), parent), 0.0)) > 0:
            continue
        supported_total = float(group["value"].sum())
        if supported_total <= 0:
            continue
        for _, row in group.groupby("branch", as_index=False)["value"].sum().iterrows():
            replacement_rows.append(
                {
                    "Branch Path": row["branch"],
                    "Variable": "Sales Share",
                    "Scenario": "Target",
                    "Year": int(year),
                    "Value": float(row["value"] / supported_total * 100.0),
                    "Units": "Share",
                    "share_decreased_from": "",
                    "note": "Survival-based replacement sales share used only where current PRC sales total is zero; 9th-edition shares retained in earlier years.",
                    "DO_NOT_USE": "",
                }
            )

    overrides = pd.DataFrame(replacement_rows)
    if overrides.empty:
        raise ValueError("No replacement-sales override rows were generated.")
    bad = overrides.apply(lambda row: (row["Branch Path"], row["Scenario"], row["Year"]) not in allowed_branch_keys, axis=1)
    if bad.any():
        raise ValueError(f"Generated rows do not match existing interface rows: {overrides.loc[bad].head().to_dict('records')}")
    return overrides.sort_values(["Branch Path", "Scenario", "Year"]).reset_index(drop=True)


def write_override_file() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    overrides = build_override_rows()
    overrides.to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {len(overrides):,} rows to {OUTPUT_CSV}")
    return OUTPUT_CSV


if __name__ == "__main__":
    write_override_file()
#%%
