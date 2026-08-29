from pathlib import Path

import pytest

from core.esto_vintage_registry import load_esto_vintage_registry


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "registry.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_checked_in_registry_maps_three_supported_vintages():
    records = load_esto_vintage_registry()
    assert [(item.esto_vintage, item.base_year, item.is_preliminary) for item in records] == [
        (2024, 2022, False),
        (2025, 2023, False),
        (2026, 2024, True),
    ]


@pytest.mark.parametrize(
    "row, message",
    [
        ("2024.5,2022,False,v_test", "four-digit integer"),
        ("2024,2021,False,v_test", "must map ESTO vintage"),
        ("2024,2022,maybe,v_test", "must be True or False"),
        ("2024,2022,False,../escape", "package_version"),
    ],
)
def test_registry_rejects_malformed_rows(tmp_path, row, message):
    path = _write(
        tmp_path,
        "esto_vintage,base_year,is_preliminary,package_version\n" + row + "\n",
    )
    with pytest.raises(ValueError, match=message):
        load_esto_vintage_registry(path)


def test_registry_rejects_duplicate_package_versions(tmp_path):
    path = _write(
        tmp_path,
        "esto_vintage,base_year,is_preliminary,package_version\n"
        "2024,2022,False,v_same\n"
        "2025,2023,False,v_same\n",
    )
    with pytest.raises(ValueError, match="duplicate package_version"):
        load_esto_vintage_registry(path)
