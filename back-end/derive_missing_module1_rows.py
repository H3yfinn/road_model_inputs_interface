"""
Derive missing Mileage and Fuel Economy rows for excluded fuel branches.

Reads all generated Module 1 output CSVs, finds the 514 (Branch Path, Variable)
gaps that are currently exempted by road_module1_static_fuel_branch_exclusions.csv,
and derives values via aggregation so those exclusions can be retired.

Derivation rules (applied in order):
  Mileage       — median across all fuels for same economy + drive_type + size
  Fuel Economy  — median across all economies for same drive_type + size + fuel
                  fallback: median across all economies for same drive_type + size
                  (covers fuel types with no cross-economy Fuel Economy data at all)

Output: CSV rows ready to append to manually_filled_rows/manually_entered_missing_rows.csv

Usage:
    python derive_missing_module1_rows.py            # prints summary + saves output CSV
    python derive_missing_module1_rows.py --dry-run  # prints only, does not write
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
BACK_END = Path(__file__).resolve().parent
MODULE1_OUTPUT_DIR = REPO_ROOT.parent / "leap_road_model" / "input_data" / "module1_defaults" / "v2026_06_05_road_module1_sources"
EXCLUSIONS_CSV = BACK_END / "data" / "road_model" / "config" / "road_module1_static_fuel_branch_exclusions.csv"
MANUALLY_FILLED_CSV = BACK_END / "data" / "road_model" / "manually_filled_rows" / "manually_entered_missing_rows.csv"
OUTPUT_CSV = BACK_END / "data" / "road_model" / "derived_missing_rows_REVIEW.csv"

SCENARIO = "Current Accounts"
YEAR = 2022
MILEAGE_UNITS = "Kilometer"
FUEL_ECONOMY_UNITS = "MJ/100 km"

# For drive types that exist in the contract but appear in NO economy's ESTO data,
# map to a proxy drive type to source aggregated values from.
# "electric" proxy is used when the fuel is Electricity or Hydrogen;
# "fossil" proxy is used for all other fuels.
_PROXY_DRIVES: dict[str, dict[str, str]] = {
    "EREV heavy": {"fossil": "ICE heavy", "electric": "BEV heavy"},
    "EREV medium": {"fossil": "ICE medium", "electric": "BEV medium"},
    "PHEV heavy": {"fossil": "ICE heavy", "electric": "BEV heavy"},
    "PHEV medium": {"fossil": "ICE medium", "electric": "BEV medium"},
    "PHEV": {"fossil": "ICE", "electric": "BEV"},  # Buses PHEV
}
_ELECTRIC_FUELS = {"Electricity", "Hydrogen"}


def _parse_branch(branch_path: str) -> dict[str, str]:
    """Extract components from a fuel-level (depth-5) branch path."""
    parts = branch_path.split("\\")
    # e.g. ['Demand', 'Freight road', 'Trucks', 'EREV heavy', 'Efuel']
    result: dict[str, str] = {}
    if len(parts) >= 5:
        result["transport"] = parts[1]   # 'Freight road' / 'Passenger road'
        result["vehicle_type"] = parts[2]  # 'Trucks', 'LPVs', etc.
        result["drive_size"] = parts[3]    # 'EREV heavy', 'BEV', 'ICE medium', etc.
        result["fuel"] = parts[4]
        # Split drive_size into drive and size where possible
        ds = parts[3]
        size_match = re.search(r"\b(small|medium|large|heavy|light)\b", ds, re.IGNORECASE)
        if size_match:
            result["size"] = size_match.group(1).lower()
            result["drive"] = ds[: size_match.start()].strip()
        else:
            result["size"] = ""
            result["drive"] = ds
    return result


def _load_all_outputs() -> pd.DataFrame:
    """Load Mileage and Fuel Economy rows from all generated economy CSVs."""
    frames = []
    for econ_dir in sorted(MODULE1_OUTPUT_DIR.iterdir()):
        csv_path = econ_dir / f"road_module1_values_{econ_dir.name}.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        df = df[df["Variable"].isin(["Mileage", "Fuel Economy"])].copy()
        df["Economy"] = econ_dir.name
        frames.append(df[["Economy", "Branch Path", "Variable", "Value", "Units"]])
    if not frames:
        raise SystemExit(f"No economy CSVs found in {MODULE1_OUTPUT_DIR}")
    return pd.concat(frames, ignore_index=True)


def _load_gaps(pool: pd.DataFrame) -> pd.DataFrame:
    """Return the (Economy, Branch Path, Variable) triples that need filling.

    Includes both:
    - absent rows (branch+variable not in pool at all), and
    - zero-value rows (branch+variable present but Value == 0.0), because a zero
      mileage or efficiency is physically invalid and just as problematic as NaN.
    """
    exclusions = pd.read_csv(EXCLUSIONS_CSV)

    # Build a mapping (economy_no_underscore, branch_path, variable) → value for fast lookup
    pool_map: dict[tuple[str, str, str], float] = {}
    for _, r in pool.iterrows():
        key = (str(r["Economy"]).replace("_", ""), str(r["Branch Path"]), str(r["Variable"]))
        pool_map[key] = float(r["Value"]) if not pd.isna(r["Value"]) else float("nan")

    gaps = []
    for _, row in exclusions.iterrows():
        econ_code = str(row["Economy"]).strip()
        bp = str(row["Branch Path"]).strip()
        for var in ["Mileage", "Fuel Economy"]:
            key = (econ_code, bp, var)
            val = pool_map.get(key)
            if val is None or (not pd.isna(val) and val <= 0) or pd.isna(val):
                gaps.append({"Economy": econ_code, "Branch Path": bp, "Variable": var})
    return pd.DataFrame(gaps) if gaps else pd.DataFrame(columns=["Economy", "Branch Path", "Variable"])


def _effective_drive_size(drive_size: str, fuel: str) -> tuple[str, bool]:
    """Return (proxy_drive_size, is_proxy) for a drive type that may lack data in pool."""
    proxy_map = _PROXY_DRIVES.get(drive_size)
    if proxy_map is None:
        return drive_size, False
    kind = "electric" if fuel in _ELECTRIC_FUELS else "fossil"
    return proxy_map[kind], True


def _derive_mileage(gap_row: pd.Series, pool: pd.DataFrame) -> tuple[float | None, str]:
    """Derive Mileage for a gap via median across same economy + same drive_size.

    Falls back to a proxy drive_size (e.g. EREV heavy → ICE heavy) if no data exists.
    """
    parsed = _parse_branch(gap_row["Branch Path"])
    econ_dir = gap_row["Economy"].replace("_", "")
    vehicle_type = parsed.get("vehicle_type", "")
    drive_size = parsed.get("drive_size", "")
    fuel = parsed.get("fuel", "")

    for attempt_drive, is_proxy in [
        (drive_size, False),
        (_effective_drive_size(drive_size, fuel)[0], True),
    ]:
        if not attempt_drive:
            continue
        mask = (
            pool["Economy"].str.replace("_", "").eq(econ_dir)
            & pool["Variable"].eq("Mileage")
            & pool["Branch Path"].str.contains(
                re.escape(vehicle_type) + r"\\" + re.escape(attempt_drive),
                regex=True,
            )
        )
        candidates = pool.loc[mask, "Value"].dropna()
        candidates = candidates[candidates > 0]
        if not candidates.empty:
            val = float(candidates.median())
            proxy_note = f" (proxy from {attempt_drive})" if is_proxy else ""
            note = (
                f"Derived: median Mileage for {vehicle_type} {attempt_drive}{proxy_note} "
                f"in same economy across {len(candidates)} fuel(s)."
            )
            return val, note

        # If no same-economy data even with proxy, try cross-economy
        mask_cross = (
            pool["Variable"].eq("Mileage")
            & pool["Branch Path"].str.contains(
                re.escape(vehicle_type) + r"\\" + re.escape(attempt_drive),
                regex=True,
            )
        )
        candidates_cross = pool.loc[mask_cross, "Value"].dropna()
        candidates_cross = candidates_cross[candidates_cross > 0]
        if not candidates_cross.empty:
            val = float(candidates_cross.median())
            proxy_note = f" (proxy from {attempt_drive})" if is_proxy else ""
            note = (
                f"Derived: median Mileage for {vehicle_type} {attempt_drive}{proxy_note} "
                f"across {len(candidates_cross)} values from all economies (no same-economy data)."
            )
            return val, note

    return None, ""


def _derive_fuel_economy(gap_row: pd.Series, pool: pd.DataFrame) -> tuple[float | None, str]:
    """Derive Fuel Economy via cross-economy median for same drive_size+fuel.

    Falls back to a proxy drive_size if the original drive type has no data in the pool.
    """
    parsed = _parse_branch(gap_row["Branch Path"])
    vehicle_type = parsed.get("vehicle_type", "")
    drive_size = parsed.get("drive_size", "")
    fuel = parsed.get("fuel", "")

    proxy_drive, is_proxy = _effective_drive_size(drive_size, fuel)

    for attempt_drive in [drive_size, proxy_drive]:
        if not attempt_drive:
            continue
        # Attempt: same drive_size + same fuel across all economies
        mask = (
            pool["Variable"].eq("Fuel Economy")
            & pool["Branch Path"].str.contains(
                re.escape(vehicle_type) + r"\\" + re.escape(attempt_drive) + r"\\" + re.escape(fuel),
                regex=True,
            )
        )
        candidates = pool.loc[mask, "Value"].dropna()
        candidates = candidates[candidates > 0]
        if not candidates.empty:
            val = float(candidates.median())
            proxy_note = f" (proxy from {attempt_drive})" if attempt_drive != drive_size else ""
            note = (
                f"Derived: median Fuel Economy for {vehicle_type} {attempt_drive} {fuel}{proxy_note} "
                f"across {len(candidates)} economy/economies."
            )
            return val, note

        # Fallback: same drive_size across all economies, any fuel
        mask2 = (
            pool["Variable"].eq("Fuel Economy")
            & pool["Branch Path"].str.contains(
                re.escape(vehicle_type) + r"\\" + re.escape(attempt_drive) + r"\\",
                regex=True,
            )
        )
        candidates2 = pool.loc[mask2, "Value"].dropna()
        candidates2 = candidates2[candidates2 > 0]
        if not candidates2.empty:
            val = float(candidates2.median())
            proxy_note = f" (proxy from {attempt_drive})" if attempt_drive != drive_size else ""
            note = (
                f"Derived: median Fuel Economy for {vehicle_type} {attempt_drive} (any fuel){proxy_note} "
                f"across {len(candidates2)} value(s) — no {fuel!r} cross-economy data available."
            )
            return val, note

    return None, ""


def main(dry_run: bool = False) -> None:
    print(f"Loading generated Module 1 outputs from:\n  {MODULE1_OUTPUT_DIR}\n")
    pool = _load_all_outputs()
    print(f"Loaded {len(pool)} Mileage/Fuel Economy rows across all economies.\n")

    gaps = _load_gaps(pool)
    if gaps.empty:
        print("No gaps found — all excluded branches already have Mileage and Fuel Economy values.")
        return
    print(f"Found {len(gaps)} gaps to fill.\n")

    rows = []
    unresolved = []

    for _, gap in gaps.iterrows():
        var = gap["Variable"]
        if var == "Mileage":
            val, note = _derive_mileage(gap, pool)
            units = MILEAGE_UNITS
        else:
            val, note = _derive_fuel_economy(gap, pool)
            units = FUEL_ECONOMY_UNITS

        if val is None:
            unresolved.append(dict(gap))
            continue

        # Economy in manually_filled_rows uses underscore format e.g. "01_AUS"
        econ_code = gap["Economy"]  # already underscore-stripped from exclusions
        # Re-insert underscore: "01AUS" → "01_AUS"
        econ_formatted = re.sub(r"^(\d{2})(.*)", lambda m: m.group(1) + "_" + m.group(2), econ_code)

        rows.append({
            "Economy": econ_formatted,
            "Branch Path": gap["Branch Path"],
            "Variable": var,
            "Scenario": SCENARIO,
            "Year": YEAR,
            "Value": round(val, 6),
            "Units": units,
            "notes": note,
            "DO_NOT_USE": "",
            "share_decreased_from": "",
        })

    result = pd.DataFrame(rows)
    print(f"Derived {len(result)} rows.")
    if unresolved:
        print(f"WARNING: {len(unresolved)} gaps could not be resolved:")
        for u in unresolved:
            print(f"  {u}")

    print("\nSample output:")
    print(result.head(10).to_string(index=False))

    if not dry_run:
        result.to_csv(OUTPUT_CSV, index=False)
        print(f"\nSaved to: {OUTPUT_CSV}")
        print("Review the output, then append to manually_entered_missing_rows.csv.")
    else:
        print("\n[Dry run — output not saved]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print only, do not write output file")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
