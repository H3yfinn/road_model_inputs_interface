from __future__ import annotations

from dataclasses import replace

import pytest

from core.base_year_variable_policy import (
    CANONICAL_CONTRACT_PATH,
    DERIVED,
    EXACT_YEAR_REQUIRED,
    SEED_ELIGIBLE,
    VARIABLE_POLICY_FAMILIES,
    VariablePolicyFamily,
    inventory_canonical_variables,
    policy_family_for_variable,
    validate_contract_policy_coverage,
    validate_policy_registry,
)


def test_current_canonical_contract_has_exactly_one_policy_per_variable():
    inventory = inventory_canonical_variables(CANONICAL_CONTRACT_PATH)
    coverage = validate_contract_policy_coverage(CANONICAL_CONTRACT_PATH)

    assert len(inventory) == 24
    assert tuple(variable for variable, _ in coverage) == inventory
    assert coverage == tuple(sorted(coverage))


@pytest.mark.parametrize(
    "variable, expected_family",
    [
        ("Reconciliation Weight Stock", EXACT_YEAR_REQUIRED),
        ("Stock", SEED_ELIGIBLE),
        ("Mileage", SEED_ELIGIBLE),
        ("Fuel Economy", SEED_ELIGIBLE),
        ("Survival Rate", SEED_ELIGIBLE),
        ("Vintage Profile Share", SEED_ELIGIBLE),
        ("Sales Share", SEED_ELIGIBLE),
        ("PHEV Electric Driving Share", SEED_ELIGIBLE),
        ("Stock Share", DERIVED),
    ],
)
def test_representative_variables_use_expected_policy_family(variable, expected_family):
    assert policy_family_for_variable(variable).family_id == expected_family


@pytest.mark.parametrize("variable", ["", "   ", None])
def test_blank_variables_are_rejected(variable):
    with pytest.raises(ValueError, match="variable must be a non-blank string"):
        policy_family_for_variable(variable)


@pytest.mark.parametrize("variable", ["stock", "STOCK", "Stock ", " Stock"])
def test_variable_lookup_requires_exact_canonical_case_and_whitespace(variable):
    with pytest.raises(ValueError, match="canonical|whitespace"):
        policy_family_for_variable(variable)


def test_unknown_variable_is_rejected_clearly():
    with pytest.raises(ValueError, match="Unknown canonical Module 1 variable 'Invented Input'"):
        policy_family_for_variable("Invented Input")


def test_duplicate_and_conflicting_assignments_are_rejected():
    exact, seed, derived = VARIABLE_POLICY_FAMILIES
    with pytest.raises(ValueError, match="Duplicate variable assignment"):
        validate_policy_registry((replace(exact, variables=("Stock", "Stock")), seed, derived))
    with pytest.raises(ValueError, match="Conflicting variable assignment"):
        validate_policy_registry((replace(exact, variables=("Stock",)), seed, derived))


@pytest.mark.parametrize(
    "families, message",
    [
        ((), "non-empty sequence"),
        (("not-a-policy",), "VariablePolicyFamily"),
        (
            (
                replace(VARIABLE_POLICY_FAMILIES[0], description=""),
                *VARIABLE_POLICY_FAMILIES[1:],
            ),
            "description",
        ),
        (
            (
                replace(VARIABLE_POLICY_FAMILIES[0], resolver_policy_id="invented"),
                *VARIABLE_POLICY_FAMILIES[1:],
            ),
            "unknown resolver policy",
        ),
        (
            (
                *VARIABLE_POLICY_FAMILIES[:-1],
                replace(VARIABLE_POLICY_FAMILIES[-1], resolver_policy_id="seed_eligible"),
            ),
            "derived family",
        ),
    ],
)
def test_malformed_policy_definitions_are_rejected(families, message):
    with pytest.raises(ValueError, match=message):
        validate_policy_registry(families)


def test_inventory_output_is_deterministic_and_sorted(tmp_path):
    contract = tmp_path / "contract.csv"
    contract.write_text("Branch Path,Variable\nB,Stock\nA,Mileage\nC,Stock\n", encoding="utf-8")

    assert inventory_canonical_variables(contract) == ("Mileage", "Stock")
    assert inventory_canonical_variables(contract) == inventory_canonical_variables(contract)


def test_new_contract_variable_fails_coverage_until_deliberately_classified(tmp_path):
    contract = tmp_path / "contract.csv"
    contract.write_text(
        "Branch Path,Variable\nA,Stock\nB,New Canonical Variable\nC,Stock Share\n",
        encoding="utf-8",
    )
    small_registry = (
        VariablePolicyFamily(EXACT_YEAR_REQUIRED, "Exact.", ("Stock",), "energy_balance_exact_year"),
        VariablePolicyFamily(SEED_ELIGIBLE, "Seed.", ("New Canonical Variable",), "seed_eligible"),
        VariablePolicyFamily(DERIVED, "Derived.", ("Stock Share",), None),
    )

    with pytest.raises(ValueError, match="unclassified canonical variables.*New Canonical Variable"):
        validate_contract_policy_coverage(contract)
    assert validate_contract_policy_coverage(contract, small_registry) == (
        ("New Canonical Variable", SEED_ELIGIBLE),
        ("Stock", EXACT_YEAR_REQUIRED),
        ("Stock Share", DERIVED),
    )
