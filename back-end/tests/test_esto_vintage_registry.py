from pathlib import Path

import pytest

from core.esto_vintage_registry import build_available_vintage_index, load_esto_vintage_registry


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "registry.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_checked_in_registry_maps_three_supported_vintages():
    records = load_esto_vintage_registry()
    assert [(item.esto_vintage, item.base_year, item.is_preliminary, item.is_default) for item in records] == [
        (2024, 2022, False, True),
        (2025, 2023, False, False),
        (2026, 2024, True, False),
    ]


@pytest.mark.parametrize(
    "row, message",
    [
        ("2024.5,2022,False,True,v_test", "four-digit integer"),
        ("2024,2021,False,True,v_test", "must map ESTO vintage"),
        ("2024,2022,maybe,True,v_test", "must be True or False"),
        ("2024,2022,False,True,../escape", "package_version"),
    ],
)
def test_registry_rejects_malformed_rows(tmp_path, row, message):
    path = _write(
        tmp_path,
        "esto_vintage,base_year,is_preliminary,is_default,package_version\n" + row + "\n",
    )
    with pytest.raises(ValueError, match=message):
        load_esto_vintage_registry(path)


def test_registry_rejects_duplicate_package_versions(tmp_path):
    path = _write(
        tmp_path,
        "esto_vintage,base_year,is_preliminary,is_default,package_version\n"
        "2024,2022,False,True,v_same\n"
        "2025,2023,False,False,v_same\n",
    )
    with pytest.raises(ValueError, match="duplicate package_version"):
        load_esto_vintage_registry(path)


@pytest.mark.parametrize(
    "rows",
    [
        "2024,2022,False,False,v_one\n2025,2023,False,False,v_two\n",
        "2024,2022,False,True,v_one\n2025,2023,False,True,v_two\n",
    ],
)
def test_registry_requires_exactly_one_default(tmp_path, rows):
    path = _write(
        tmp_path,
        "esto_vintage,base_year,is_preliminary,is_default,package_version\n" + rows,
    )
    with pytest.raises(ValueError, match="exactly one default"):
        load_esto_vintage_registry(path)


def test_available_vintage_index_keeps_2024_as_default():
    records = load_esto_vintage_registry()
    available, default = build_available_vintage_index(
        records, {record.package_version for record in records},
    )
    assert default == 2024
    assert available[0]["label"] == "ESTO 2024 — Base year 2022"


def test_available_vintage_index_rejects_silent_default_drift():
    records = load_esto_vintage_registry()
    with pytest.raises(ValueError, match="configured default package is missing"):
        build_available_vintage_index(records, {"v2026_08_29_esto_2025"})


def test_available_vintage_index_allows_legacy_only_bundle():
    assert build_available_vintage_index(load_esto_vintage_registry(), {"v_legacy"}) == ([], None)
