from __future__ import annotations

from dataclasses import replace

import pytest

from core.base_year_candidate_resolver import (
    EXACT_YEAR_ENERGY_BALANCE_POLICY,
    SEED_ELIGIBLE_POLICY,
    ResolverPolicy,
    resolve_base_year_candidates,
)


def candidate(candidate_id: str, year: int, **overrides):
    value = {
        "candidate_id": candidate_id,
        "row_key": ("Demand\\Passenger road\\LPVs", "Stock", "Current Accounts"),
        "source_id": f"source:{candidate_id}",
        "source_data_year": year,
        "source_classification": "native_observation",
        "quality_tier": "default",
        "source_priority_id": "default",
        "payload": {"value": candidate_id},
    }
    value.update(overrides)
    return value


def test_exact_year_native_candidate_wins_and_reports_audit_fields():
    result = resolve_base_year_candidates(
        [candidate("old", 2021), candidate("native", 2022), candidate("future", 2023)], 2022, "seed_eligible"
    )
    assert result.selected.candidate_id == "native"
    assert (result.selected_source_data_year, result.year_distance, result.direction) == (2022, 0, "exact")
    assert result.base_year_treatment == "native"
    assert result.selection_reason == "exact_year_native_observation"
    assert {item.candidate_id: item.reasons for item in result.rejections} == {
        "old": ("exact_year_preferred",),
        "future": ("exact_year_preferred",),
    }


def test_latest_earlier_candidate_is_selected_and_carried_forward():
    result = resolve_base_year_candidates([candidate("old", 2019), candidate("latest", 2021)], 2022, "seed_eligible")
    assert result.selected.candidate_id == "latest"
    assert result.base_year_treatment == "carried_forward"
    assert result.selection_reason == "latest_eligible_earlier_observation"


def test_earliest_future_candidate_is_used_only_without_earlier_candidate():
    result = resolve_base_year_candidates([candidate("later", 2024), candidate("first", 2023)], 2022, "seed_eligible")
    assert result.selected.candidate_id == "first"
    assert result.direction == "future"
    assert result.base_year_treatment == "carried_backward"


def test_earlier_candidate_beats_closer_future_candidate():
    result = resolve_base_year_candidates([candidate("past", 2010), candidate("future", 2023)], 2022, "seed_eligible")
    assert result.selected.candidate_id == "past"


def test_ties_use_configured_quality_source_then_stable_candidate_identity():
    policy = ResolverPolicy(
        "test_priority", True, frozenset({"native_observation"}), {"high": 0, "low": 1}, {"first": 0, "second": 1}
    )
    rows = [
        candidate("z", 2021, quality_tier="low", source_priority_id="second"),
        candidate("b", 2021, quality_tier="high", source_priority_id="first"),
        candidate("a", 2021, quality_tier="high", source_priority_id="first"),
    ]
    assert resolve_base_year_candidates(rows, 2022, policy).selected.candidate_id == "a"


@pytest.mark.parametrize(
    "rows, expected_reason",
    [
        ([candidate("winner", 2021), candidate("loser", 2020)], "newer_eligible_earlier_year_preferred"),
        ([candidate("winner", 2021), candidate("loser", 2023)], "eligible_earlier_data_preferred_over_future"),
        ([candidate("winner", 2023), candidate("loser", 2024)], "earlier_eligible_future_year_preferred"),
        (
            [candidate("winner", 2021, quality_tier="high"), candidate("loser", 2021, quality_tier="low")],
            "higher_configured_quality_tier_preferred",
        ),
        (
            [candidate("winner", 2021, source_priority_id="first"), candidate("loser", 2021, source_priority_id="second")],
            "higher_configured_source_priority_preferred",
        ),
        ([candidate("a", 2021), candidate("z", 2021)], "stable_candidate_id_tie_break_preferred"),
    ],
)
def test_selected_candidate_records_the_first_losing_rank_dimension(rows, expected_reason):
    policy = ResolverPolicy(
        "rank_reasons",
        True,
        frozenset({"native_observation"}),
        {"default": 0, "high": 0, "low": 1},
        {"default": 0, "first": 0, "second": 1},
    )
    result = resolve_base_year_candidates(rows, 2022, policy)
    assert result.rejections[-1].reasons == (expected_reason,)


def test_exact_year_projection_is_not_relabelled_native():
    policy = replace(SEED_ELIGIBLE_POLICY, policy_id="projection_allowed", eligible_classifications=frozenset({"projection"}))
    result = resolve_base_year_candidates([candidate("projection", 2022, source_classification="projection")], 2022, policy)
    assert result.selected.source_classification == "projection"
    assert result.base_year_treatment == "transformed"
    assert result.selection_reason == "exact_year_non_native_candidate"


def test_legacy_unknown_is_conservatively_ineligible():
    result = resolve_base_year_candidates([candidate("legacy", 2022, source_classification="legacy_unknown")], 2022, "seed_eligible")
    assert result.selected is None
    assert result.outcome == "no_eligible_candidates"
    assert result.rejections[0].reasons == ("ineligible_source_classification",)


def test_exact_year_only_policy_rejects_seed_years():
    result = resolve_base_year_candidates([candidate("old", 2021)], 2022, EXACT_YEAR_ENERGY_BALANCE_POLICY)
    assert result.selected is None
    assert set(result.rejections[0].reasons) == {"policy_requires_exact_year"}


def test_no_candidates_and_duplicate_identities_are_explicit():
    assert resolve_base_year_candidates([], 2022, "seed_eligible").outcome == "no_candidates"
    with pytest.raises(ValueError, match="Duplicate candidate identities"):
        resolve_base_year_candidates([candidate("same", 2021), candidate("same", 2022)], 2022, "seed_eligible")


def test_mixed_row_keys_are_rejected_independent_of_input_order():
    rows = [candidate("a", 2021), candidate("b", 2022, row_key=("other", "Stock", "Current Accounts"))]
    for ordered_rows in (rows, list(reversed(rows))):
        with pytest.raises(ValueError, match="same canonical row_key"):
            resolve_base_year_candidates(ordered_rows, 2022, "seed_eligible")


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"source_data_year": "not-a-year"}, "source_data_year"),
        ({"candidate_id": ""}, "candidate_id is required"),
        ({"row_key": ()}, "row_key is required"),
        ({"row_key": None}, "row_key must be a sequence"),
        ({"source_classification": "invented"}, "Unsupported source_classification"),
    ],
)
def test_invalid_candidate_contracts_are_rejected(overrides, message):
    row = candidate("bad", 2022)
    row.update(overrides)
    with pytest.raises(ValueError, match=message):
        resolve_base_year_candidates([row], 2022, "seed_eligible")
    with pytest.raises(ValueError, match="Unknown base-year resolver policy"):
        resolve_base_year_candidates([], 2022, "invented_policy")
    with pytest.raises(ValueError, match="requested_base_year"):
        resolve_base_year_candidates([], "not-a-year", "seed_eligible")


@pytest.mark.parametrize("invalid_year", [2022.9, float("nan"), float("inf"), float("-inf"), True, "2022.9", "NaN"])
def test_fractional_nonfinite_boolean_and_malformed_years_are_rejected(invalid_year):
    with pytest.raises(ValueError, match="integer year"):
        resolve_base_year_candidates([candidate("bad", invalid_year)], 2022, "seed_eligible")
    with pytest.raises(ValueError, match="integer year"):
        resolve_base_year_candidates([], invalid_year, "seed_eligible")


def test_integer_year_values_and_canonical_integer_strings_are_accepted():
    assert resolve_base_year_candidates([candidate("string-year", "2022")], "2022", "seed_eligible").selected_source_data_year == 2022


def test_result_is_input_order_independent():
    rows = [candidate("b", 2021), candidate("a", 2021), candidate("future", 2023)]
    forward = resolve_base_year_candidates(rows, 2022, "seed_eligible")
    reverse = resolve_base_year_candidates(list(reversed(rows)), 2022, "seed_eligible")
    assert forward.selected.candidate_id == reverse.selected.candidate_id == "a"
    assert forward.rejections == reverse.rejections


def test_no_eligible_audit_is_input_order_independent():
    rows = [
        candidate("z", 2022, source_classification="legacy_unknown"),
        candidate("a", 2021, source_classification="legacy_unknown"),
    ]
    forward = resolve_base_year_candidates(rows, 2022, "seed_eligible")
    reverse = resolve_base_year_candidates(list(reversed(rows)), 2022, "seed_eligible")
    assert forward.selected is None
    assert forward.rejections == reverse.rejections


def test_duplicate_validation_scales_to_large_synthetic_candidate_collections():
    rows = [candidate(f"candidate-{index:05d}", 2021) for index in range(5_000)]
    result = resolve_base_year_candidates(rows, 2022, "seed_eligible")
    assert result.selected.candidate_id == "candidate-00000"
    assert len(result.rejections) == 4_999


def test_reversible_resolutions_always_start_from_original_candidates():
    originals = [candidate("2020", 2020), candidate("2022", 2022)]
    assert resolve_base_year_candidates(originals, 2021, "seed_eligible").selected.candidate_id == "2020"
    assert resolve_base_year_candidates(originals, 2020, "seed_eligible").selected.candidate_id == "2020"
    assert resolve_base_year_candidates(originals, 2021, "seed_eligible").selected.candidate_id == "2020"
    originals.append(candidate("2021_native", 2021))
    assert resolve_base_year_candidates(originals, 2021, "seed_eligible").selected.candidate_id == "2021_native"
