from __future__ import annotations

import pandas as pd
import pytest

from build_road_model_static_defaults import _validate_static_values


def _rows(variable: str, value: object) -> pd.DataFrame:
    return pd.DataFrame([{
        "Scenario": "Current Accounts",
        "Branch Path": r"Demand\Passenger road\LPVs\ICE\Gasoline",
        "Variable": variable,
        "Year": 2022,
        "Value": value,
    }])


@pytest.mark.parametrize("variable", ["Mileage", "Fuel Economy"])
def test_static_publication_rejects_zero_strictly_positive_values(variable):
    with pytest.raises(ValueError, match="invalid Module 1 values"):
        _validate_static_values(_rows(variable, 0), "20USA")


def test_static_publication_rejects_non_numeric_values():
    with pytest.raises(ValueError, match="finite number"):
        _validate_static_values(_rows("Stock", "not-a-number"), "20USA")


def test_static_publication_accepts_valid_values():
    _validate_static_values(pd.concat([
        _rows("Mileage", 12.5),
        _rows("Fuel Economy", 150.0),
        _rows("Stock", 0),
    ], ignore_index=True), "20USA")
