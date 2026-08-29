from __future__ import annotations

import json

import pandas as pd
import pytest

from core.base_year_package_generation import CANONICAL_LONG_COLUMNS
from core.esto_vintage_registry import EstoVintage
from core import road_module1_defaults as defaults
from scripts import stage_road_module1_vintage_release as script


def _rows(economy: str, base_year: int) -> pd.DataFrame:
    common = {
        "Economy": economy,
        "Branch Path": r"Demand\Passenger road\LPVs",
        "Variable": "Mileage",
        "Value": 10.0,
        "Scale": "Thousands",
        "Units": "km",
        "Source": "test",
        "Comment": "test",
        "Input Status": "default",
        "Shown In Interface": True,
        "Source Data Year": base_year,
        "Source Classification": "native_observation",
        "Base Year Treatment": "native",
        "Derivation Method": "direct_observation",
    }
    return pd.DataFrame([
        {**common, "Scenario": "Current Accounts", "Year": base_year},
        {**common, "Scenario": "Reference", "Year": base_year + 1},
        {**common, "Scenario": "Target", "Year": base_year + 1},
    ], columns=CANONICAL_LONG_COLUMNS)


def test_destinations_reject_protected_existing_and_nested_paths(tmp_path):
    with pytest.raises(ValueError, match="protected path"):
        script._validate_destinations(
            script.REPO_ROOT / "back-end" / "outputs" / "unsafe", tmp_path / "static"
        )
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="must not already exist"):
        script._validate_destinations(existing, tmp_path / "static")
    with pytest.raises(ValueError, match="non-nested"):
        script._validate_destinations(tmp_path / "release", tmp_path / "release" / "static")


def test_complete_package_rejects_fractional_year_and_invalid_value(tmp_path):
    path = tmp_path / "package.csv"
    rows = _rows("20USA", 2022)
    rows["Year"] = rows["Year"].astype(float)
    rows.loc[0, "Year"] = 2022.5
    rows.to_csv(path, index=False)
    with pytest.raises(ValueError, match="fractional year"):
        script._validate_complete_package(path, "20USA", 2022)

    rows = _rows("20USA", 2022)
    rows.loc[0, "Value"] = 0
    rows.to_csv(path, index=False)
    with pytest.raises(ValueError, match="invalid values"):
        script._validate_complete_package(path, "20USA", 2022)


def _wide_row(value: float, source_name: str) -> pd.DataFrame:
    row = {column: pd.NA for column in defaults.MODULE1_INPUT_COLUMNS}
    row.update({
        "Branch Path": r"Demand\Freight road\Trucks\FCEV heavy\Hydrogen",
        "Variable": "Mileage",
        "Scenario": "Current Accounts",
        "Region": "New Zealand",
        "Scale": "",
        "Units": "Kilometer",
        "Per...": "",
        "2022": value,
        "source_type": "manual_missing_rows",
        "source_name": source_name,
        "notes": "Reviewed estimate.",
    })
    return pd.DataFrame([row], columns=defaults.MODULE1_INPUT_COLUMNS)


def test_transport_overlay_cannot_replace_valid_fallback_with_invalid_value(monkeypatch, tmp_path):
    target = _wide_row(19_102.5, "reviewed_estimate.csv")
    workbook = _wide_row(0.0, "ignored.xlsx")
    workbook["Scenario"] = "Current Accounts"
    workbook["Region"] = "New Zealand"
    resolved = tmp_path / "transport.xlsx"
    monkeypatch.setattr(
        defaults,
        "load_transport_leap_export_defaults",
        lambda **kwargs: (workbook, resolved),
    )

    result, report = defaults.overlay_transport_leap_export_values(
        target, defaults.get_economy_info("12NZ")
    )

    assert result.loc[0, "2022"] == 19_102.5
    assert result.loc[0, "source_name"] == "reviewed_estimate.csv"
    assert report.loc[0, "status"] == "skipped_invalid_value"
    assert "Mileage must be greater than 0" in report.loc[0, "details"]


def test_transport_overlay_still_applies_valid_value(monkeypatch, tmp_path):
    target = _wide_row(19_102.5, "reviewed_estimate.csv")
    workbook = _wide_row(22_000.0, "ignored.xlsx")
    workbook["Scenario"] = "Current Accounts"
    workbook["Region"] = "New Zealand"
    resolved = tmp_path / "transport.xlsx"
    monkeypatch.setattr(
        defaults,
        "load_transport_leap_export_defaults",
        lambda **kwargs: (workbook, resolved),
    )

    result, report = defaults.overlay_transport_leap_export_values(
        target, defaults.get_economy_info("12NZ")
    )

    assert result.loc[0, "2022"] == 22_000.0
    assert result.loc[0, "source_name"] == resolved.name
    assert report.loc[0, "status"] == "applied"


def test_stage_release_builds_all_registered_versions(tmp_path, monkeypatch):
    records = [
        EstoVintage(2024, 2022, False, True, "v2024"),
        EstoVintage(2025, 2023, False, False, "v2025"),
    ]
    monkeypatch.setattr(script, "load_esto_vintage_registry", lambda: records)
    monkeypatch.setattr(
        script, "get_economy_info", lambda economy: type("Economy", (), {"name": economy})()
    )
    monkeypatch.setattr(
        script.static_builder,
        "_load_configured_scenario_labels",
        lambda: ["Current Accounts", "Reference", "Target"],
    )

    def fake_source_bundle(work_root):
        source = work_root / script.CURRENT_SOURCE_PACKAGE_VERSION
        source.mkdir(parents=True)
        _rows("20USA", 2022).to_csv(source / "20USA.csv", index=False)
        return source

    def fake_package(**kwargs):
        destination = kwargs["output_dir"]
        destination.mkdir(parents=True)
        complete = destination / (
            f"{kwargs['economy']}_{kwargs['requested_base_year']}_complete_package.csv"
        )
        _rows(kwargs["economy"], kwargs["requested_base_year"]).to_csv(complete, index=False)
        manifest = destination / "resolution_manifest.json"
        manifest.write_text(json.dumps({"ok": True}), encoding="utf-8")
        return {"complete_package_csv": complete, "manifest_json": manifest}

    monkeypatch.setattr(script, "_build_source_fallback_bundle", fake_source_bundle)
    monkeypatch.setattr(script, "generate_checked_in_source_review_package", fake_package)
    output = tmp_path / "backend"
    static = tmp_path / "static"
    summary = script.stage_vintage_release(output_root=output, static_root=static)

    assert summary["version_count"] == 2
    assert summary["economy_count_per_version"] == 1
    assert (output / "v2024" / "20USA" / "road_module1_values_20USA.csv").exists()
    assert (output / "v2025" / "road_module1_manifest.json").exists()
    assert (static / "v2024" / "20USA.csv").exists()
    index = json.loads((static / "index.json").read_text(encoding="utf-8"))
    assert index["default_version"] == "v2024"
    assert index["default_esto_vintage"] == 2024
    assert [item["package_version"] for item in index["esto_vintages"]] == ["v2024", "v2025"]


def test_failed_release_leaves_no_final_destinations(tmp_path, monkeypatch):
    monkeypatch.setattr(
        script,
        "load_esto_vintage_registry",
        lambda: [EstoVintage(2024, 2022, False, True, "v2024")],
    )

    def fail_source_bundle(work_root):
        raise ValueError("source validation failed")

    monkeypatch.setattr(script, "_build_source_fallback_bundle", fail_source_bundle)
    output = tmp_path / "backend"
    static = tmp_path / "static"
    with pytest.raises(ValueError, match="source validation failed"):
        script.stage_vintage_release(output_root=output, static_root=static)
    assert not output.exists()
    assert not static.exists()
    assert not list(tmp_path.glob(".*.building.*"))


def test_main_reports_safe_failure(tmp_path, capsys):
    existing = tmp_path / "existing"
    existing.mkdir()
    exit_code = script.main([
        "--output-root", str(existing),
        "--static-root", str(tmp_path / "static"),
    ])
    assert exit_code == 2
    assert "must not already exist" in capsys.readouterr().err
