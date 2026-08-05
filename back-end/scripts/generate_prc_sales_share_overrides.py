#%%
"""Generate survival-based replacement sales-share overrides for all economies.

The normal 9th-edition sales shares are retained whenever the source sales total
is positive.  Only zero-sales parent/year combinations are replaced, using
vehicle-level survival/vintage turnover and the existing interface leaf rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
INTERFACE_REPO = BACKEND_DIR.parent
LEAP_TRANSPORT_REPO = INTERFACE_REPO.parent / "leap_transport"
SOURCE_DIR = BACKEND_DIR / "data/road_model/processed_source"
WORKBOOK_DIR = BACKEND_DIR / "data/road_model/leap_import_workbooks"
OUTPUT_DIR = BACKEND_DIR / "data/road_model/final_value_overrides/sales_shares_9th_replacement"
STATIC_DIR = INTERFACE_REPO / "front-end/road-module1-static/v2026_06_05_road_module1_sources"
OUTPUT_COLUMNS = ["Branch Path", "Variable", "Scenario", "Year", "Value", "Units", "share_decreased_from", "note", "DO_NOT_USE"]

ECONOMY_CODES = [
    path.name.removeprefix("transport_data_").removesuffix("_Target_2022_2060.pkl")
    for path in sorted((LEAP_TRANSPORT_REPO / "intermediate_data").glob("transport_data_*_Target_2022_2060.pkl"))
    if not path.name.startswith("transport_data_00_")
]

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
    "bev": "BEV", "fcev": "FCEV", "phev": "PHEV", "phev_d": "PHEV", "phev_g": "PHEV",
    "erev_d": "EREV", "erev_g": "EREV", "hev": "HEV", "hev_d": "HEV", "hev_g": "HEV",
    "ice": "ICE", "ice_d": "ICE", "ice_g": "ICE", "cng": "ICE", "lng": "ICE", "lpg": "ICE",
}


def _compact_code(economy_code: str) -> str:
    return economy_code.replace("_", "")


def _branch_path(transport_type: str, vehicle_type: str, size: str, drive: str) -> str:
    transport_label = "Passenger road" if transport_type == "passenger" else "Freight road"
    if size == "all":
        return rf"Demand\{transport_label}\{vehicle_type}\{drive}"
    return rf"Demand\{transport_label}\{vehicle_type}\{drive} {size}"


def _allowed_branch_keys(compact_code: str) -> set[tuple[str, str, int]]:
    source_path = SOURCE_DIR / f"road_module1_source_{compact_code}.csv"
    source = pd.read_csv(source_path)
    source_leaf_rows = source[
        (source["Variable"] == "Sales Share")
        & (source["Scenario"] == "Target")
        & (source["Branch Path"].str.count(r"\\") >= 3)
    ]
    allowed = set(zip(source_leaf_rows["Branch Path"], source_leaf_rows["Scenario"], source_leaf_rows["Year"]))

    candidates = sorted(WORKBOOK_DIR.glob(
        f"transport_leap_export_combined_{compact_code[:2]}_{compact_code[2:]}_domestic_international_Target_*.xlsx"
    ))
    if candidates:
        workbook_df = pd.read_excel(candidates[-1], sheet_name="FOR_VIEWING", header=2)
        branches = workbook_df[
            (workbook_df["Variable"].fillna("").astype(str).str.strip() == "Sales Share")
            & (workbook_df["Scenario"].fillna("").astype(str).str.strip() == "Target")
            & (workbook_df["Branch Path"].fillna("").astype(str).str.count(r"\\") >= 3)
        ]["Branch Path"].dropna().astype(str).unique()
        allowed.update((branch, "Target", year) for branch in branches for year in range(2023, 2061))

    # The static bundle is the actual browser/model hand-off contract.  Do not
    # create specialist rows for workbook branches that the interface has
    # filtered out, because uploaded rows cannot introduce new branch keys.
    static_path = STATIC_DIR / f"{compact_code}.csv"
    if static_path.exists():
        static = pd.read_csv(static_path)
        static_keys = static[
            (static["Variable"] == "Sales Share")
            & (static["Scenario"] == "Target")
        ]
        allowed = set(zip(static_keys["Branch Path"], static_keys["Scenario"], static_keys["Year"]))
    return allowed


def build_override_rows(economy_code: str) -> pd.DataFrame:
    """Build overrides for one canonical leap_transport economy code."""
    sys.path.insert(0, str(LEAP_TRANSPORT_REPO / "codebase"))
    from functions.sales_curve_estimate import (  # pylint: disable=import-outside-toplevel
        compute_sales_from_stock_targets,
        load_survival_and_vintage_profiles,
    )

    compact_code = _compact_code(economy_code)
    allowed_branch_keys = _allowed_branch_keys(compact_code)
    checkpoint = LEAP_TRANSPORT_REPO / f"intermediate_data/transport_data_{economy_code}_Target_2022_2060.pkl"
    survival_path = LEAP_TRANSPORT_REPO / f"data/lifecycle_profiles/vehicle_survival_modified_{economy_code}.xlsx"
    vintage_path = LEAP_TRANSPORT_REPO / f"data/lifecycle_profiles/vintage_modelled_from_survival_{economy_code}.xlsx"

    source = pd.read_pickle(checkpoint)
    source = source[
        (source["Economy"] == economy_code)
        & (source["Scenario"] == "Target")
        & (source["Medium"] == "road")
        & (source["Transport Type"].isin(["passenger", "freight"]))
        & (source["Vehicle Type"].isin(VEHICLE_TYPE_MAP))
    ].copy()
    source["Date"] = pd.to_numeric(source["Date"], errors="coerce").astype(int)
    source["interface_parent"] = source["Vehicle Type"].map(lambda value: VEHICLE_TYPE_MAP[value][1])
    source["interface_drive"] = source["Drive"].map(DRIVE_MAP)
    source = source[source["interface_drive"].notna()].copy()

    current_parent_totals = source.groupby(["Date", "interface_parent"], dropna=False)["Sales"].sum()
    stock_series = source.groupby(["Date", "interface_parent", "Vehicle Type", "Drive"], dropna=False)["Stocks"].sum()
    profile_key = economy_code.split("_", 1)[1]
    survival, vintage = load_survival_and_vintage_profiles(
        survival_path, vintage_path, vehicle_keys=(profile_key,), survival_is_cumulative=True
    )

    replacement_detail: list[dict[str, object]] = []
    for (parent, vehicle_type), group in stock_series.groupby(level=[1, 2]):
        stock_wide = group.droplevel([1, 2]).unstack("Drive").fillna(0.0).sort_index()
        replacement = pd.DataFrame(index=stock_wide.index, columns=stock_wide.columns, dtype=float)
        for drive in stock_wide.columns:
            replacement[drive], _, _ = compute_sales_from_stock_targets(
                stock_wide[drive], survival[profile_key], vintage[profile_key], return_retirements=True
            )
        mapped_replacement = pd.DataFrame(index=replacement.index)
        for drive in replacement.columns:
            mapped_drive = DRIVE_MAP.get(str(drive))
            if mapped_drive:
                mapped_replacement[mapped_drive] = mapped_replacement.get(mapped_drive, 0.0) + replacement[drive]
        for year in replacement.index:
            for drive, value in mapped_replacement.loc[year].items():
                transport_type, interface_parent, size = VEHICLE_TYPE_MAP[vehicle_type]
                branch = _branch_path(transport_type, interface_parent, size, drive)
                if (branch, "Target", int(year)) in allowed_branch_keys:
                    replacement_detail.append({"parent": parent, "year": int(year), "branch": branch, "value": float(value)})

    detail = pd.DataFrame(replacement_detail)
    rows: list[dict[str, object]] = []
    for (parent, year), group in detail.groupby(["parent", "year"], dropna=False):
        if float(current_parent_totals.get((int(year), parent), 0.0)) > 0:
            continue
        supported_total = float(group["value"].sum())
        if supported_total <= 0:
            continue
        for _, row in group.groupby("branch", as_index=False)["value"].sum().iterrows():
            rows.append({
                "Branch Path": row["branch"], "Variable": "Sales Share", "Scenario": "Target", "Year": int(year),
                "Value": float(row["value"] / supported_total * 100.0), "Units": "Share", "share_decreased_from": "",
                "note": f"Survival-based replacement sales share used only where current {compact_code} sales total is zero; 9th-edition shares retained in earlier years.",
                "DO_NOT_USE": "",
            })

    overrides = pd.DataFrame(rows)
    if overrides.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    bad = overrides.apply(lambda row: (row["Branch Path"], row["Scenario"], row["Year"]) not in allowed_branch_keys, axis=1)
    if bad.any():
        raise ValueError(f"Generated rows do not match existing interface rows for {economy_code}: {overrides.loc[bad].head().to_dict('records')}")
    return overrides[OUTPUT_COLUMNS].sort_values(["Branch Path", "Scenario", "Year"]).reset_index(drop=True)


def write_override_files() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    for economy_code in ECONOMY_CODES:
        output_path = OUTPUT_DIR / f"module1_final_value_overrides_{_compact_code(economy_code)}.csv"
        overrides = build_override_rows(economy_code)
        overrides.to_csv(output_path, index=False)
        outputs.append(output_path)
        print(f"Wrote {len(overrides):,} rows to {output_path}")
    return outputs


if __name__ == "__main__":
    write_override_files()
#%%
