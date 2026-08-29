from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from core.missing_value_estimation import (
    KEY_COLUMNS,
    REVIEW_COLUMNS,
    apply_estimation_proposals,
    estimate_missing_values,
    normalise_estimation_pool,
)
from core.missing_value_review_html import build_proposal_comparison_html
from scripts.estimate_missing_module1_values import generate_review_package


def _row(economy, branch, variable, value, *, year=2022):
    return {
        "Economy": economy,
        "Scenario": "Current Accounts",
        "Branch Path": branch,
        "Variable": variable,
        "Year": year,
        "Value": value,
        "Scale": "Thousands" if variable == "Mileage" else "",
        "Units": "Kilometer" if variable == "Mileage" else "MJ/100 km",
    }


def _pool():
    mileage_electric = r"Demand\Passenger road\LPVs\PHEV small\Electricity"
    mileage_gasoline = r"Demand\Passenger road\LPVs\PHEV small\Gasoline"
    fuel_economy_electric = r"Demand\Passenger road\LPVs\BEV small\Electricity"
    fuel_economy_ice = r"Demand\Passenger road\LPVs\ICE small\Gasoline"
    fuel_economy_hev = r"Demand\Passenger road\LPVs\HEV small\Gasoline"
    rows = [
        _row("01AAA", mileage_electric, "Mileage", 0),
        _row("01AAA", mileage_gasoline, "Mileage", 10),
        _row("01AAA", fuel_economy_electric, "Fuel Economy", 0),
        _row("01AAA", fuel_economy_ice, "Fuel Economy", 200),
        _row("01AAA", fuel_economy_hev, "Fuel Economy", 200),
    ]
    for economy, value in [
        ("02BBB", 100), ("03CCC", 120), ("04DDD", 140),
        ("05EEE", 160), ("06FFF", 180), ("07GGG", 220),
    ]:
        mileage = value / 10
        rows.extend([
            _row(economy, mileage_electric, "Mileage", mileage),
            _row(economy, mileage_gasoline, "Mileage", mileage),
            _row(economy, fuel_economy_electric, "Fuel Economy", value),
            _row(economy, fuel_economy_ice, "Fuel Economy", value),
            _row(economy, fuel_economy_hev, "Fuel Economy", value),
        ])
    return pd.DataFrame(rows)


def test_fractional_source_year_is_rejected_not_truncated():
    with pytest.raises(ValueError, match="integer year"):
        normalise_estimation_pool(
            pd.DataFrame([_row(
                "01AAA", r"Demand\Passenger road\LPVs\BEV small\Electricity",
                "Mileage", 1, year=2022.5,
            )]),
            base_year=2022,
        )


def test_normalisation_is_idempotent_for_loaded_staging_pools():
    first = normalise_estimation_pool(_pool(), base_year=2022)
    second = normalise_estimation_pool(first, base_year=2022)

    assert second.columns.is_unique
    assert len(second) == len(first)


def test_cross_validated_proposals_fill_every_invalid_key_with_auditable_values():
    result = estimate_missing_values(
        _pool(), base_year=2022, min_peer_economies=2, min_adjustment_rows=1,
    )

    assert len(result.proposals) == 2
    assert result.proposals["Proposed Value"].gt(0).all()
    assert result.proposals["Proposal ID"].is_unique
    assert set(result.proposals["Source Classification"]) == {"model_assumption"}
    assert set(result.proposals["Base Year Treatment"]) == {"transformed"}
    assert set(result.proposals["Source"]) == {"Cross-validated Module 1 missing-value estimate"}
    mileage = result.proposals[result.proposals["Variable"].eq("Mileage")].iloc[0]
    assert mileage["Strategy"] == "mileage_hierarchy"
    assert mileage["Estimation Method"] == "same_economy_exact_drive_median"
    assert mileage["Proposed Value"] == 10
    fuel_economy = result.proposals[result.proposals["Variable"].eq("Fuel Economy")].iloc[0]
    assert fuel_economy["Strategy"] == "economy_adjusted_peer_median"
    assert fuel_economy["Economy Adjustment Factor"] > 1
    assert not result.evidence.empty
    mileage_evidence = result.evidence[
        result.evidence["Proposal ID"].eq(mileage["Proposal ID"])
    ]
    assert "estimate_input" in set(mileage_evidence["Role"])
    assert "exact_branch_peer_context" in set(mileage_evidence["Role"])
    assert set(result.cross_validation_summary["Variable"]) == {"Mileage", "Fuel Economy"}


def test_apply_proposals_changes_only_exact_non_positive_keys():
    source = _pool()
    result = estimate_missing_values(
        source, base_year=2022, min_peer_economies=2, min_adjustment_rows=1,
    )

    applied = apply_estimation_proposals(source, result.proposals)

    before = source.set_index(KEY_COLUMNS)["Value"]
    after = applied.set_index(KEY_COLUMNS)["Value"]
    changed = after[after.ne(before)]
    assert len(changed) == 2
    assert changed.gt(0).all()
    assert source["Value"].eq(0).sum() == 2


def test_apply_proposals_rejects_replacement_of_existing_positive_value():
    source = _pool()
    proposal = {
        **source[source["Value"].gt(0)].iloc[0][KEY_COLUMNS].to_dict(),
        "Proposed Value": 99,
    }
    with pytest.raises(ValueError, match="only a non-positive value"):
        apply_estimation_proposals(source, pd.DataFrame([proposal]))


def test_apply_proposals_rejects_absent_keys_and_fractional_years():
    source = _pool()
    result = estimate_missing_values(
        source, base_year=2022, min_peer_economies=2, min_adjustment_rows=1,
    )
    absent = result.proposals.iloc[[0]].copy()
    absent["Branch Path"] = r"Demand\Passenger road\LPVs\missing\Electricity"
    with pytest.raises(ValueError, match="absent from the canonical package"):
        apply_estimation_proposals(source, absent)

    fractional = result.proposals.iloc[[0]].copy()
    fractional["Year"] = 2022.5
    with pytest.raises(ValueError, match="integer year"):
        apply_estimation_proposals(source, fractional)


def test_estimation_fails_when_required_peer_evidence_is_unavailable():
    too_small = _pool()[_pool()["Economy"].isin(["01AAA", "02BBB"])]
    with pytest.raises(ValueError, match="no eligible strategy"):
        estimate_missing_values(too_small, base_year=2022, min_peer_economies=3)


def test_review_package_is_complete_checksummed_and_never_overwritten(tmp_path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    for economy, group in _pool().groupby("Economy"):
        group.to_csv(static_dir / f"{economy}.csv", index=False)
    output_dir = tmp_path / "review"

    summary = generate_review_package(
        static_dir=static_dir,
        base_year=2022,
        output_dir=output_dir,
    )

    manifest = json.loads((output_dir / "estimation_manifest.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "review_only_no_promotion"
    assert manifest["schema_version"] == 1
    assert manifest["estimator"] == "masked_known_value_cross_validation"
    assert manifest["strictly_positive_variables"] == ["Fuel Economy", "Mileage"]
    reviewer = pd.read_csv(output_dir / "proposed_missing_values.csv")
    audit = pd.read_csv(output_dir / "proposal_audit.csv")
    assert list(reviewer.columns) == REVIEW_COLUMNS
    assert len(audit.columns) > len(reviewer.columns)
    assert audit["Proposal ID"].tolist() == reviewer["Proposal ID"].tolist()
    assert reviewer["Reviewer Decision"].isna().all()
    assert reviewer["Reviewer Note"].isna().all()
    text_cells = reviewer.astype("string").fillna("").stack()
    assert not text_cells.str.startswith(("=", "+", "-", "@")).any()
    comparison_html = (output_dir / "proposal_comparison.html").read_text(encoding="utf-8")
    assert "Proposal comparison scatterplots" in comparison_html
    assert 'id="economy-nav"' in comparison_html
    assert 'data-proposal-overview="all-proposals"' in comparison_html
    assert "renderEconomySection" in comparison_html
    assert 'id="economy-select"' not in comparison_html
    assert 'id="proposal-select"' not in comparison_html
    assert "#1565c0" in comparison_html
    assert "#e53935" in comparison_html
    assert "km/vehicle/year" in comparison_html
    assert 'scale.factor*proposal["Proposed Value"]' in comparison_html
    assert audit.iloc[0]["Proposal ID"] in comparison_html
    assert manifest["proposal_row_count"] == 2
    for artifact in manifest["artifacts"].values():
        path = output_dir / artifact["filename"]
        assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="must not already exist"):
        generate_review_package(static_dir=static_dir, base_year=2022, output_dir=output_dir)


def test_comparison_html_escapes_embedded_script_content():
    result = estimate_missing_values(
        _pool(), base_year=2022, min_peer_economies=2, min_adjustment_rows=1,
    )
    proposals = result.proposals.copy()
    proposals.loc[proposals.index[0], "Comment"] = "safe </script><script>alert(1)</script>"

    html = build_proposal_comparison_html(proposals, result.evidence)

    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>" in html


def test_checked_in_missing_value_estimates_are_complete_reviewed_last_resort_source():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "data" / "road_model" / "manually_filled_rows"
        / "cross_validated_missing_value_estimates_2022.csv"
    )
    rows = pd.read_csv(source_path)

    assert len(rows) == 188
    assert rows[["Economy", "Scenario", "Branch Path", "Variable", "Year"]].duplicated().sum() == 0
    assert set(rows["Economy"]) == {"07INA", "08JPN", "10MAS", "11MEX", "12NZ", "13PNG", "14PE", "18CT"}
    assert set(rows["Variable"]) == {"Fuel Economy", "Mileage"}
    assert set(rows["Year"]) == {2022}
    assert set(rows["Source Data Year"]) == {2022}
    assert set(rows["Source Classification"]) == {"model_assumption"}
    assert set(rows["Base Year Treatment"]) == {"transformed"}
    assert rows["Value"].gt(0).all()
    assert rows["Comment"].str.contains("Cross-validation median absolute percentage error").all()
    assert rows["Comment"].str.contains("Replace when better economy-specific evidence").all()
    assert rows["DO_NOT_USE"].isna().all()
