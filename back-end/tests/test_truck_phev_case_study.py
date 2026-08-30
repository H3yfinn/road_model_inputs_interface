from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.road_module1_defaults import (
    MODULE1_INPUT_COLUMNS,
    EconomyInfo,
    overlay_phev_utilisation_rates,
)


def test_truck_specific_phev_utilisation_is_emitted_from_source(tmp_path: Path):
    source_path = tmp_path / "phev_rates.csv"
    pd.DataFrame([
        {
            "project_code": "20_USA",
            "economy": "United States",
            "vehicle_type": "LPVs",
            "data_year": 2024,
            "phev_utilisation_rate": 0.42,
            "lower_rate": 0.34,
            "upper_rate": 0.50,
            "evidence_grade": "A",
            "estimation_status": "synthetic_estimate",
        },
        {
            "project_code": "20_USA",
            "economy": "United States",
            "vehicle_type": "LCVs",
            "data_year": 2024,
            "phev_utilisation_rate": 0.37,
            "lower_rate": 0.29,
            "upper_rate": 0.45,
            "evidence_grade": "A",
            "estimation_status": "synthetic_estimate",
        },
        {
            "project_code": "20_USA",
            "economy": "United States",
            "vehicle_type": "Trucks",
            "data_year": 2024,
            "phev_utilisation_rate": 0.31,
            "lower_rate": 0.21,
            "upper_rate": 0.41,
            "evidence_grade": "D",
            "estimation_status": "case_study_proxy",
        },
    ]).to_csv(source_path, index=False)
    empty_defaults = pd.DataFrame(columns=MODULE1_INPUT_COLUMNS)

    overlaid, report = overlay_phev_utilisation_rates(
        default_filled_df=empty_defaults,
        economy=EconomyInfo("20USA", "United States", 0.0),
        source_path=source_path,
    )

    values = overlaid.set_index("Branch Path")["2022"]
    assert values["Demand\\Passenger road\\PHEV"] == 0.42
    assert values["Demand\\Freight road\\PHEV"] == 0.37
    assert values["Demand\\Freight road\\Trucks\\PHEV"] == 0.31
    assert set(report["status"]) == {"applied"}
