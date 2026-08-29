from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from core.base_year_package_generation import (
    CANONICAL_LONG_COLUMNS,
    generate_resolved_base_year_package,
)
from core.researcher_submission_review import normalise_module1_rows


ECONOMY = "20USA"
SCENARIO = "Current Accounts"
YEAR = 2024


def fallback_row(branch: str, variable: str, value: float, **overrides):
    row = {
        "Economy": ECONOMY,
        "Scenario": SCENARIO,
        "Branch Path": branch,
        "Variable": variable,
        "Year": YEAR,
        "Value": value,
        "Scale": "%" if variable == "Stock Share" else "",
        "Units": "Share" if variable == "Stock Share" else "units",
        "Source": "checked-in static fallback",
        "Comment": "Authoritative unchanged fallback.",
        "Input Status": "default",
        "Shown In Interface": True,
        "Source Data Year": "",
        "Source Classification": "legacy_unknown",
        "Base Year Treatment": "legacy_unrecorded",
        "Derivation Method": "legacy_unrecorded",
    }
    row.update(overrides)
    return row


def candidate(candidate_id: str, fallback: dict, source_year: int, value: float, **overrides):
    payload = dict(fallback)
    payload.update(
        {
            "Year": source_year,
            "Value": value,
            "Source": f"source {candidate_id}",
            "Comment": f"Original candidate {candidate_id}.",
            "Source Data Year": source_year,
            "Source Classification": "native_observation",
        }
    )
    row = {
        "candidate_origin": "original",
        "candidate_id": candidate_id,
        "row_key": tuple(fallback[column] for column in ["Economy", "Scenario", "Branch Path", "Variable"]),
        "source_id": f"package:{candidate_id}",
        "source_data_year": source_year,
        "source_classification": "native_observation",
        "quality_tier": "default",
        "source_priority_id": "default",
        "payload": payload,
    }
    row.update(overrides)
    return row


def build_fixture():
    rows = [
        fallback_row("Demand\\Passenger road\\Motorcycles", "Stock", 10),
        fallback_row("Demand\\Passenger road\\LPVs", "Stock", 30),
        fallback_row(
            "Demand\\Passenger road\\Motorcycles", "Stock Share", 25,
            **{"Derivation Method": "stock_share_from_stock"},
        ),
        fallback_row(
            "Demand\\Passenger road\\LPVs", "Stock Share", 75,
            **{"Derivation Method": "stock_share_from_stock"},
        ),
        fallback_row("Demand\\Passenger road\\Motorcycles\\ICE", "Mileage", 1),
        fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 2),
        fallback_row("Demand\\Passenger road\\LPVs\\BEV", "Mileage", 3),
    ]
    by_key = {(row["Branch Path"], row["Variable"]): row for row in rows}
    candidates = [
        candidate("stock-exact", by_key[("Demand\\Passenger road\\Motorcycles", "Stock")], 2024, 20),
        candidate("stock-earlier", by_key[("Demand\\Passenger road\\LPVs", "Stock")], 2023, 20),
        candidate("mileage-exact", by_key[("Demand\\Passenger road\\Motorcycles\\ICE", "Mileage")], 2024, 11),
        candidate("mileage-earlier", by_key[("Demand\\Passenger road\\LPVs\\ICE", "Mileage")], 2022, 22),
        candidate("mileage-future", by_key[("Demand\\Passenger road\\LPVs\\BEV", "Mileage")], 2026, 33),
    ]
    return rows, candidates


def generate(tmp_path, rows, candidates, **overrides):
    args = {
        "fallback_rows": rows,
        "candidates": candidates,
        "economy": ECONOMY,
        "requested_base_year": YEAR,
        "source_package": "synthetic-original-candidates-v1",
        "package_version": "v_test_resolved",
        "output_dir": tmp_path,
        "generation_time": "2026-08-28T00:00:00+00:00",
    }
    args.update(overrides)
    return generate_resolved_base_year_package(**args)


def test_opt_in_generation_selects_exact_earlier_future_and_derives_stock_share(tmp_path):
    rows, candidates = build_fixture()
    paths = generate(tmp_path, rows, candidates)
    resolved = pd.read_csv(paths["resolved_csv"])
    audit = pd.read_csv(paths["audit_csv"])

    mileage = resolved[resolved["Variable"].eq("Mileage")].set_index("Branch Path")
    assert mileage.loc["Demand\\Passenger road\\Motorcycles\\ICE", "Value"] == 11
    assert mileage.loc["Demand\\Passenger road\\LPVs\\ICE", "Value"] == 22
    assert mileage.loc["Demand\\Passenger road\\LPVs\\BEV", "Value"] == 33
    assert mileage.loc["Demand\\Passenger road\\Motorcycles\\ICE", "Base Year Treatment"] == "native"
    assert mileage.loc["Demand\\Passenger road\\LPVs\\ICE", "Base Year Treatment"] == "carried_forward"
    assert mileage.loc["Demand\\Passenger road\\LPVs\\BEV", "Base Year Treatment"] == "carried_backward"
    assert set(resolved["Year"]) == {YEAR}

    shares = resolved[resolved["Variable"].eq("Stock Share")].set_index("Branch Path")
    assert shares["Value"].to_dict() == {
        "Demand\\Passenger road\\LPVs": 50.0,
        "Demand\\Passenger road\\Motorcycles": 50.0,
    }
    assert set(shares["Derivation Method"]) == {"stock_share_from_stock"}
    assert set(shares["Base Year Treatment"]) == {"transformed"}
    assert set(audit[audit["Variable"].eq("Stock Share")]["status"]) == {"derived"}
    assert not any(candidate_row["row_key"][-1] == "Stock Share" for candidate_row in candidates)
    normalised = normalise_module1_rows(resolved, legacy_values_are_internal=False)
    assert len(normalised) == len(resolved)


def test_future_candidate_uses_canonical_future_year_seed_term(tmp_path):
    row = fallback_row("Demand\\Passenger road\\LPVs\\BEV", "Mileage", 3)
    paths = generate(tmp_path, [row], [candidate("future", row, 2026, 33)])
    resolved = pd.read_csv(paths["resolved_csv"])
    assert resolved.loc[0, "Derivation Method"] == "future_year_seed"


def test_stock_share_without_explicit_stock_derivation_preserves_fallback(tmp_path):
    rows = [
        fallback_row("Demand\\Passenger road\\LPVs", "Stock", 30),
        fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Stock Share", 100),
    ]

    paths = generate(tmp_path, rows, [])
    resolved = pd.read_csv(paths["resolved_csv"])
    audit = pd.read_csv(paths["audit_csv"])

    share = resolved[resolved["Variable"].eq("Stock Share")].iloc[0]
    share_audit = audit[audit["Variable"].eq("Stock Share")].iloc[0]
    assert share["Value"] == 100
    assert share["Derivation Method"] == "legacy_unrecorded"
    assert share_audit["status"] == "fallback"
    assert share_audit["selection_reason"] == "stock_share_has_no_explicit_stock_derivation"


@pytest.mark.parametrize(
    "variable",
    ["Mileage Correction Factor", "Fuel Economy Correction Factor"],
)
def test_generated_correction_factors_are_preserved_without_resolution(tmp_path, variable):
    row = fallback_row(
        "Demand\\Passenger road\\LPVs\\ICE",
        variable,
        1.05,
        **{
            "Source": "generated_default_correction_factor",
            "Source Classification": "model_assumption",
            "Base Year Treatment": "transformed",
            "Derivation Method": "generated_default_correction_factor",
        },
    )
    paths = generate(tmp_path, [row], [])
    resolved = pd.read_csv(paths["resolved_csv"])
    audit = pd.read_csv(paths["audit_csv"])

    assert resolved.loc[0, "Value"] == 1.05
    assert audit.loc[0, "status"] == "derived"
    assert audit.loc[0, "selection_reason"] == "generated_derived_control_preserved"
    assert pd.isna(audit.loc[0, "resolver_policy_id"])


def test_explicit_stock_share_derivation_requires_stock_basis(tmp_path):
    row = fallback_row(
        "Demand\\Passenger road\\LPVs", "Stock Share", 100,
        **{"Derivation Method": "stock_share_from_stock"},
    )

    with pytest.raises(ValueError, match="has no Stock row"):
        generate(tmp_path, [row], [])


def test_no_candidates_preserves_authoritative_fallback_row_and_does_not_mutate_input(tmp_path):
    row = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 123.5)
    original = dict(row)
    paths = generate(tmp_path, [row], [])

    resolved = pd.read_csv(paths["resolved_csv"]).iloc[0].to_dict()
    for column in CANONICAL_LONG_COLUMNS:
        expected = original[column]
        actual = resolved[column]
        if expected == "":
            assert pd.isna(actual)
        else:
            assert actual == expected
    assert row == original
    assert pd.read_csv(paths["audit_csv"]).loc[0, "status"] == "fallback"


def test_sparse_policy_override_is_recorded_and_can_require_exact_year(tmp_path):
    row = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 9)
    paths = generate(
        tmp_path,
        [row],
        [candidate("older", row, 2023, 99)],
        variable_policy_overrides={"Mileage": "energy_balance_exact_year"},
    )
    resolved = pd.read_csv(paths["resolved_csv"])
    audit = pd.read_csv(paths["audit_csv"])
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))

    assert resolved.loc[0, "Value"] == 9
    assert audit.loc[0, "status"] == "fallback"
    assert bool(audit.loc[0, "policy_override_applied"])
    assert audit.loc[0, "resolver_policy_id"] == "energy_balance_exact_year"
    assert "policy_requires_exact_year" in audit.loc[0, "rejections"]
    assert manifest["resolution"]["variable_policy_overrides"] == {"Mileage": "energy_balance_exact_year"}


def test_sparse_manual_candidate_override_can_choose_eligible_older_value_over_exact_year(tmp_path):
    row = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 9)
    candidates = [
        candidate("exact", row, 2024, 44),
        candidate("reviewer-selected-older", row, 2022, 22),
    ]
    manual_override = {
        "row_key": [ECONOMY, SCENARIO, row["Branch Path"], row["Variable"]],
        "requested_base_year": YEAR,
        "source_package": "synthetic-original-candidates-v1",
        "candidate_id": "reviewer-selected-older",
        "reason": "The 2022 survey is more representative for this vehicle branch.",
        "reviewer": "model-manager",
    }

    paths = generate(
        tmp_path,
        [row],
        candidates,
        candidate_selection_overrides=[manual_override],
    )
    resolved = pd.read_csv(paths["resolved_csv"])
    audit = pd.read_csv(paths["audit_csv"])
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))

    assert resolved.loc[0, "Value"] == 22
    assert resolved.loc[0, "Source Data Year"] == 2022
    assert resolved.loc[0, "Base Year Treatment"] == "carried_forward"
    assert audit.loc[0, "selection_reason"] == "manual_candidate_override"
    assert bool(audit.loc[0, "manual_candidate_override_applied"])
    assert audit.loc[0, "automatic_candidate_id"] == "exact"
    assert audit.loc[0, "manual_override_reason"] == manual_override["reason"]
    assert manifest["resolution"]["candidate_selection_overrides"] == [manual_override]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda override: override.update(candidate_id="missing"), "exactly one candidate"),
        (lambda override: override.update(reason=""), "manual override reason"),
        (lambda override: override.update(requested_base_year=2023), "must match the generated package"),
        (lambda override: override.update(source_package="wrong"), "must match the generated package"),
    ],
)
def test_malformed_manual_candidate_overrides_are_rejected(tmp_path, mutate, message):
    row = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 9)
    item = candidate("selected", row, 2022, 22)
    override = {
        "row_key": [ECONOMY, SCENARIO, row["Branch Path"], row["Variable"]],
        "requested_base_year": YEAR,
        "source_package": "synthetic-original-candidates-v1",
        "candidate_id": "selected",
        "reason": "Reviewed source choice.",
    }
    mutate(override)
    with pytest.raises(ValueError, match=message):
        generate(tmp_path, [row], [item], candidate_selection_overrides=[override])


def test_manual_candidate_override_cannot_target_derived_stock_share(tmp_path):
    row = fallback_row(
        "Demand\\Passenger road\\LPVs", "Stock Share", 100,
        **{"Derivation Method": "stock_share_from_stock"},
    )
    override = {
        "row_key": [ECONOMY, SCENARIO, row["Branch Path"], row["Variable"]],
        "requested_base_year": YEAR,
        "source_package": "synthetic-original-candidates-v1",
        "candidate_id": "share",
        "reason": "Invalid direct derived override.",
    }
    with pytest.raises(ValueError, match="cannot have a manual candidate override"):
        generate(tmp_path, [row], [], candidate_selection_overrides=[override])


def test_manifest_has_identity_summary_rejections_and_verified_checksums(tmp_path):
    row = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 9)
    legacy = candidate("legacy", row, 2024, 99, source_classification="legacy_unknown")
    legacy["payload"]["Source Classification"] = "legacy_unknown"
    paths = generate(tmp_path, [row], [legacy])
    manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
    resolution = manifest["resolution"]

    assert manifest["generation_time"] == "2026-08-28T00:00:00+00:00"
    assert resolution["economy"] == ECONOMY
    assert resolution["requested_base_year"] == YEAR
    assert resolution["source_package"] == "synthetic-original-candidates-v1"
    assert resolution["strategy"] == "prefer_earlier"
    assert resolution["summary_counts"] == {
        "candidate_count": 1,
        "derived": 0,
        "fallback": 1,
        "rejected_candidate_decisions": 1,
        "resolved": 0,
        "total_rows": 1,
    }
    assert resolution["rejection_reason_counts"] == {"ineligible_source_classification": 1}
    assert resolution["output_sha256"] == hashlib.sha256(paths["resolved_csv"].read_bytes()).hexdigest()
    assert resolution["audit_sha256"] == hashlib.sha256(paths["audit_csv"].read_bytes()).hexdigest()


def test_resolution_and_audit_are_deterministic_and_generation_time_is_isolated(tmp_path):
    rows, candidates = build_fixture()
    first = generate(tmp_path / "first", rows, candidates, generation_time="2026-08-28T00:00:00+00:00")
    second = generate(
        tmp_path / "second", rows, list(reversed(candidates)), generation_time="2026-08-29T00:00:00+00:00"
    )
    assert first["resolved_csv"].read_bytes() == second["resolved_csv"].read_bytes()
    assert first["audit_csv"].read_bytes() == second["audit_csv"].read_bytes()
    first_manifest = json.loads(first["manifest_json"].read_text(encoding="utf-8"))
    second_manifest = json.loads(second["manifest_json"].read_text(encoding="utf-8"))
    assert first_manifest["generation_time"] != second_manifest["generation_time"]
    assert first_manifest["resolution"] == second_manifest["resolution"]


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda item: item.update(candidate_origin="generated"), "shifted/generated"),
        (lambda item: item.update(candidate_origin="shifted"), "shifted/generated"),
        (lambda item: item["payload"].update(Value="not numeric"), "finite numeric"),
        (lambda item: item["payload"].update(**{"Source Data Year": 2020}), "must match"),
        (lambda item: item["payload"].update(Year=2023), "shifted/generated"),
        (lambda item: item["payload"].update(**{"Source Classification": "projection"}), "must match"),
        (lambda item: item["payload"].pop("Comment"), "missing canonical columns"),
        (lambda item: item.update(row_key=(ECONOMY, SCENARIO, "missing", "Mileage")), "absent from"),
    ],
)
def test_malformed_or_recycled_candidates_are_rejected(tmp_path, mutate, message):
    row = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 9)
    item = candidate("candidate", row, 2024, 99)
    mutate(item)
    with pytest.raises(ValueError, match=message):
        generate(tmp_path, [row], [item])


def test_stock_share_candidate_is_rejected_instead_of_independently_resolved(tmp_path):
    row = fallback_row("Demand\\Passenger road\\LPVs", "Stock Share", 100)
    with pytest.raises(ValueError, match="derived from resolved Stock"):
        generate(tmp_path, [row], [candidate("share", row, 2024, 100)])


def test_unmapped_candidate_cannot_self_declare_verified_9th_lineage(tmp_path):
    row = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 9)
    item = candidate(
        "forged-lineage",
        row,
        2022,
        99,
        source_classification="legacy_unknown",
        source_lineage="verified_9th_outlook",
    )
    item["payload"]["Source Classification"] = "legacy_unknown"
    with pytest.raises(ValueError, match="does not match the explicit source/package lineage mapping"):
        generate(tmp_path, [row], [item])


def test_candidate_identity_must_be_unique_across_the_package(tmp_path):
    first = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 9)
    second = fallback_row("Demand\\Passenger road\\LPVs\\BEV", "Mileage", 10)
    with pytest.raises(ValueError, match="Duplicate candidate identity across package"):
        generate(tmp_path, [first, second], [candidate("same", first, 2024, 90), candidate("same", second, 2024, 100)])


def test_unknown_strategy_and_protected_output_paths_are_rejected(tmp_path):
    row = fallback_row("Demand\\Passenger road\\LPVs\\ICE", "Mileage", 9)
    with pytest.raises(ValueError, match="supports only"):
        generate(tmp_path, [row], [], strategy="closest_available")
    with pytest.raises(ValueError, match="protected path"):
        generate(
            tmp_path,
            [row],
            [],
            output_dir="front-end/road-module1-static/test-do-not-write",
        )
