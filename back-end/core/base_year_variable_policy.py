"""Canonical Module 1 variable families for base-year resolution.

The registry is deliberately variable-level rather than row-level.  Branch Path
is not needed by the current maintained contract.  This module only classifies
variables; it does not connect resolution to package generation.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.base_year_candidate_resolver import POLICIES_BY_ID


CANONICAL_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "road_model"
    / "config"
    / "road_module1_static_contract.csv"
)

EXACT_YEAR_REQUIRED = "exact_year_required"
SEED_ELIGIBLE = "seed_eligible"
DERIVED = "derived"
REQUIRED_POLICY_FAMILY_IDS = frozenset({EXACT_YEAR_REQUIRED, SEED_ELIGIBLE, DERIVED})


@dataclass(frozen=True)
class VariablePolicyFamily:
    """One documented family of exact canonical Module 1 variable names."""

    family_id: str
    description: str
    variables: tuple[str, ...]
    resolver_policy_id: str | None


VARIABLE_POLICY_FAMILIES = (
    VariablePolicyFamily(
        family_id=EXACT_YEAR_REQUIRED,
        description=(
            "Energy-balance reconciliation controls that must come from the requested base year; "
            "earlier or future seeds are not allowed."
        ),
        variables=(
            "Reconciliation Bound Lower Efficiency",
            "Reconciliation Bound Lower Mileage",
            "Reconciliation Bound Upper Efficiency",
            "Reconciliation Bound Upper Mileage",
            "Reconciliation Weight Efficiency",
            "Reconciliation Weight Mileage",
            "Reconciliation Weight Stock",
        ),
        resolver_policy_id="energy_balance_exact_year",
    ),
    VariablePolicyFamily(
        family_id=SEED_ELIGIBLE,
        description=(
            "Original researcher or source inputs that may use the requested year, the latest "
            "eligible earlier year, or only when neither exists the earliest eligible future year."
        ),
        variables=(
            "Freight GDP Elasticity Adjustment",
            "Fuel Economy",
            "Mileage",
            "Passenger Saturation Reached",
            "Passenger Stock Growth Rate Adjustment",
            "Passenger Vehicle Saturation",
            "PHEV Electric Driving Share",
            "Sales Share",
            "Stock",
            "Survival Rate",
            "Turnover Rate Bound Lower",
            "Turnover Rate Bound Upper",
            "Vehicle Equivalent Weight",
            "Vehicle Equivalent Weight Lower Bound",
            "Vehicle Equivalent Weight Upper Bound",
            "Vintage Profile Share",
        ),
        resolver_policy_id="seed_eligible",
    ),
    VariablePolicyFamily(
        family_id=DERIVED,
        description=(
            "Values recalculated from already resolved inputs and therefore never independently shifted."
        ),
        variables=("Stock Share",),
        resolver_policy_id=None,
    ),
)


def _required_exact_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string.")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace: {value!r}.")
    return value


def validate_policy_registry(
    families: Sequence[VariablePolicyFamily] = VARIABLE_POLICY_FAMILIES,
) -> dict[str, VariablePolicyFamily]:
    """Validate definitions and return an exact-name variable lookup."""
    if isinstance(families, (str, bytes)) or not isinstance(families, Sequence) or not families:
        raise ValueError("Policy registry must be a non-empty sequence of VariablePolicyFamily definitions.")

    family_ids: set[str] = set()
    variable_lookup: dict[str, VariablePolicyFamily] = {}
    for family in families:
        if not isinstance(family, VariablePolicyFamily):
            raise ValueError("Every policy definition must be a VariablePolicyFamily.")
        family_id = _required_exact_text(family.family_id, "family_id")
        _required_exact_text(family.description, f"description for {family_id!r}")
        if family_id not in REQUIRED_POLICY_FAMILY_IDS:
            raise ValueError(f"Unknown variable policy family {family_id!r}.")
        if family_id in family_ids:
            raise ValueError(f"Duplicate variable policy family definition {family_id!r}.")
        family_ids.add(family_id)
        if isinstance(family.variables, (str, bytes)) or not isinstance(family.variables, tuple) or not family.variables:
            raise ValueError(f"Policy family {family_id!r} must define a non-empty tuple of variables.")

        if family_id == DERIVED:
            if family.resolver_policy_id is not None:
                raise ValueError("The derived family must not name a resolver policy.")
        else:
            resolver_policy_id = _required_exact_text(
                family.resolver_policy_id, f"resolver_policy_id for {family_id!r}"
            )
            if resolver_policy_id not in POLICIES_BY_ID:
                raise ValueError(
                    f"Policy family {family_id!r} names unknown resolver policy {resolver_policy_id!r}."
                )

        seen_within_family: set[str] = set()
        for raw_variable in family.variables:
            variable = _required_exact_text(raw_variable, f"variable in {family_id!r}")
            if variable in seen_within_family:
                raise ValueError(f"Duplicate variable assignment in {family_id!r}: {variable!r}.")
            seen_within_family.add(variable)
            if variable in variable_lookup:
                other_family = variable_lookup[variable].family_id
                raise ValueError(
                    f"Conflicting variable assignment for {variable!r}: {other_family!r} and {family_id!r}."
                )
            variable_lookup[variable] = family

    missing_families = sorted(REQUIRED_POLICY_FAMILY_IDS - family_ids)
    if missing_families:
        raise ValueError(f"Policy registry is missing required families: {missing_families}.")
    return variable_lookup


def policy_family_for_variable(
    variable: str,
    families: Sequence[VariablePolicyFamily] = VARIABLE_POLICY_FAMILIES,
) -> VariablePolicyFamily:
    """Return the family for one exact canonical Variable value."""
    canonical_variable = _required_exact_text(variable, "variable")
    lookup = validate_policy_registry(families)
    try:
        return lookup[canonical_variable]
    except KeyError as exc:
        case_matches = sorted(name for name in lookup if name.casefold() == canonical_variable.casefold())
        hint = f" Use exact canonical spelling {case_matches[0]!r}." if len(case_matches) == 1 else ""
        raise ValueError(f"Unknown canonical Module 1 variable {canonical_variable!r}.{hint}") from exc


def inventory_canonical_variables(contract_path: Path = CANONICAL_CONTRACT_PATH) -> tuple[str, ...]:
    """Read the maintained static contract and return deterministic variable names."""
    with Path(contract_path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "Variable" not in reader.fieldnames:
            raise ValueError(f"Canonical contract {contract_path} is missing the 'Variable' column.")
        variables = {
            _required_exact_text(row.get("Variable"), f"Variable in canonical contract {contract_path}")
            for row in reader
        }
    if not variables:
        raise ValueError(f"Canonical contract {contract_path} contains no variables.")
    return tuple(sorted(variables))


def validate_contract_policy_coverage(
    contract_path: Path = CANONICAL_CONTRACT_PATH,
    families: Sequence[VariablePolicyFamily] = VARIABLE_POLICY_FAMILIES,
) -> tuple[tuple[str, str], ...]:
    """Require every maintained variable to have exactly one current policy family."""
    canonical_variables = inventory_canonical_variables(contract_path)
    lookup = validate_policy_registry(families)
    unknown = sorted(set(canonical_variables) - set(lookup))
    stale = sorted(set(lookup) - set(canonical_variables))
    if unknown or stale:
        details: list[str] = []
        if unknown:
            details.append(f"unclassified canonical variables: {unknown}")
        if stale:
            details.append(f"policy variables absent from canonical contract: {stale}")
        raise ValueError("Module 1 variable-policy coverage failed; " + "; ".join(details) + ".")
    return tuple((variable, lookup[variable].family_id) for variable in canonical_variables)
