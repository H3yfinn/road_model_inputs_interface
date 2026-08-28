"""Pure, deterministic base-year candidate selection and provenance contract.

This module intentionally accepts records only.  It does not discover files,
read generated packages, or decide which production variables use a policy.
Callers must supply that variable-to-policy mapping explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping, Sequence


VALID_SOURCE_CLASSIFICATIONS = frozenset(
    {
        "native_observation",
        "projection",
        "structural_assumption",
        "model_assumption",
        "legacy_unknown",
    }
)
VALID_SOURCE_LINEAGES = frozenset({"verified_9th_outlook"})


@dataclass(frozen=True)
class ResolverPolicy:
    """Explicit eligibility and deterministic tie-break configuration."""

    policy_id: str
    allow_seed_years: bool
    eligible_classifications: frozenset[str]
    quality_tier_priority: Mapping[str, int]
    source_priority: Mapping[str, int]
    eligible_source_lineages: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Candidate:
    """One original source candidate; shifted/generated rows are not candidates."""

    candidate_id: str
    row_key: tuple[str, ...]
    source_id: str
    source_data_year: int
    source_classification: str
    quality_tier: str
    source_priority_id: str
    payload: Mapping[str, Any]
    source_lineage: str = ""


@dataclass(frozen=True)
class CandidateRejection:
    candidate_id: str
    row_key: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CandidateResolution:
    requested_base_year: int
    policy_id: str
    selected: Candidate | None
    selected_source_data_year: int | None
    year_distance: int | None
    direction: str | None
    base_year_treatment: str | None
    selection_reason: str
    rejections: tuple[CandidateRejection, ...]

    @property
    def outcome(self) -> str:
        return "selected" if self.selected is not None else self.selection_reason


EXACT_YEAR_ENERGY_BALANCE_POLICY = ResolverPolicy(
    policy_id="energy_balance_exact_year",
    allow_seed_years=False,
    eligible_classifications=frozenset({"native_observation"}),
    quality_tier_priority={"default": 0},
    source_priority={"default": 0},
)

SEED_ELIGIBLE_POLICY = ResolverPolicy(
    policy_id="seed_eligible",
    allow_seed_years=True,
    eligible_classifications=frozenset({"native_observation"}),
    quality_tier_priority={"default": 0},
    source_priority={"default": 0},
    eligible_source_lineages=frozenset({"verified_9th_outlook"}),
)

POLICIES_BY_ID = {
    EXACT_YEAR_ENERGY_BALANCE_POLICY.policy_id: EXACT_YEAR_ENERGY_BALANCE_POLICY,
    SEED_ELIGIBLE_POLICY.policy_id: SEED_ELIGIBLE_POLICY,
}


def _validate_year(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer year, not a boolean.")
    if isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[+-]?\d+", text):
            raise ValueError(f"{field_name} must be an integer year, got {value!r}.")
        year = int(text)
    else:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer year, got {value!r}.") from exc
        if not math.isfinite(numeric) or not numeric.is_integer():
            raise ValueError(f"{field_name} must be an integer year, got {value!r}.")
        year = int(numeric)
    if not 1900 <= year <= 2100:
        raise ValueError(f"{field_name} {year} is outside the supported range 1900–2100.")
    return year


def _required_text(value: object, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


def _normalise_candidate(value: Candidate | Mapping[str, Any]) -> Candidate:
    if isinstance(value, Candidate):
        candidate = value
    elif isinstance(value, Mapping):
        try:
            candidate = Candidate(
                candidate_id=value["candidate_id"],
                row_key=value["row_key"],
                source_id=value["source_id"],
                source_data_year=value["source_data_year"],
                source_classification=value["source_classification"],
                quality_tier=value["quality_tier"],
                source_priority_id=value["source_priority_id"],
                payload=value.get("payload", {}),
                source_lineage=value.get("source_lineage", ""),
            )
        except KeyError as exc:
            raise ValueError(f"Candidate is missing required field {exc.args[0]!r}.") from exc
    else:
        raise ValueError("Each candidate must be a Candidate or mapping.")

    if isinstance(candidate.row_key, str):
        raise ValueError("row_key must be a sequence of key values, not a string.")
    try:
        row_key = tuple(_required_text(part, "row_key value") for part in candidate.row_key)
    except TypeError as exc:
        raise ValueError("row_key must be a sequence of key values.") from exc
    if not row_key:
        raise ValueError("row_key is required.")
    classification = _required_text(candidate.source_classification, "source_classification")
    if classification not in VALID_SOURCE_CLASSIFICATIONS:
        raise ValueError(f"Unsupported source_classification {classification!r}.")
    if not isinstance(candidate.payload, Mapping):
        raise ValueError("payload must be a mapping.")
    lineage = str(candidate.source_lineage or "").strip()
    if lineage and lineage not in VALID_SOURCE_LINEAGES:
        raise ValueError(f"Unsupported source_lineage {lineage!r}.")
    return Candidate(
        candidate_id=_required_text(candidate.candidate_id, "candidate_id"),
        row_key=row_key,
        source_id=_required_text(candidate.source_id, "source_id"),
        source_data_year=_validate_year(candidate.source_data_year, "source_data_year"),
        source_classification=classification,
        quality_tier=_required_text(candidate.quality_tier, "quality_tier"),
        source_priority_id=_required_text(candidate.source_priority_id, "source_priority_id"),
        payload=dict(candidate.payload),
        source_lineage=lineage,
    )


def _validate_policy(policy: ResolverPolicy | str) -> ResolverPolicy:
    if isinstance(policy, str):
        try:
            policy = POLICIES_BY_ID[policy]
        except KeyError as exc:
            raise ValueError(f"Unknown base-year resolver policy {policy!r}.") from exc
    if not isinstance(policy, ResolverPolicy):
        raise ValueError("policy must be a ResolverPolicy or registered policy identifier.")
    _required_text(policy.policy_id, "policy_id")
    if not isinstance(policy.allow_seed_years, bool):
        raise ValueError("allow_seed_years must be boolean.")
    if not policy.eligible_classifications <= VALID_SOURCE_CLASSIFICATIONS:
        raise ValueError("Policy has unsupported eligible source classifications.")
    if not policy.eligible_source_lineages <= VALID_SOURCE_LINEAGES:
        raise ValueError("Policy has unsupported eligible source lineages.")
    if not policy.quality_tier_priority or not policy.source_priority:
        raise ValueError("Policy must supply explicit quality-tier and source priorities.")
    for priorities, label in (
        (policy.quality_tier_priority, "quality_tier_priority"),
        (policy.source_priority, "source_priority"),
    ):
        for key, priority in priorities.items():
            _required_text(key, label)
            if isinstance(priority, bool) or not isinstance(priority, int):
                raise ValueError(f"{label} values must be integers.")
    return policy


def _direction_and_treatment(candidate: Candidate, requested_year: int) -> tuple[str, str, str]:
    if candidate.source_data_year < requested_year:
        return "earlier", "carried_forward", "latest_eligible_earlier_observation"
    if candidate.source_data_year > requested_year:
        return "future", "carried_backward", "earliest_eligible_future_observation"
    if candidate.source_classification == "native_observation":
        return "exact", "native", "exact_year_native_observation"
    return "exact", "transformed", "exact_year_non_native_candidate"


def resolve_base_year_candidates(
    candidates: Sequence[Candidate | Mapping[str, Any]],
    requested_base_year: int,
    policy: ResolverPolicy | str,
) -> CandidateResolution:
    """Select a source candidate without mutating inputs or reading any files.

    Direction and source-data year are deliberately ranked before quality/source
    priority: an eligible earlier observation always beats future data, even when
    the future value is closer.  The last tie-breaker is candidate_id, so input
    ordering and filesystem enumeration cannot affect the answer.
    """
    requested_year = _validate_year(requested_base_year, "requested_base_year")
    resolver_policy = _validate_policy(policy)
    normalised = tuple(_normalise_candidate(value) for value in candidates)
    seen_ids: set[str] = set()
    duplicates: set[str] = set()
    for candidate in normalised:
        if candidate.candidate_id in seen_ids:
            duplicates.add(candidate.candidate_id)
        seen_ids.add(candidate.candidate_id)
    if duplicates:
        raise ValueError(f"Duplicate candidate identities: {sorted(duplicates)}")
    row_keys = {candidate.row_key for candidate in normalised}
    if len(row_keys) > 1:
        raise ValueError(f"All candidates must have the same canonical row_key: {sorted(row_keys)!r}")

    rejected: list[CandidateRejection] = []
    eligible: list[Candidate] = []
    for candidate in normalised:
        reasons: list[str] = []
        classification_eligible = candidate.source_classification in resolver_policy.eligible_classifications
        lineage_eligible = candidate.source_lineage in resolver_policy.eligible_source_lineages
        if not classification_eligible and not lineage_eligible:
            reasons.append("ineligible_source_classification")
        if not resolver_policy.allow_seed_years and candidate.source_data_year != requested_year:
            reasons.append("policy_requires_exact_year")
        if candidate.quality_tier not in resolver_policy.quality_tier_priority:
            reasons.append("unconfigured_quality_tier")
        if candidate.source_priority_id not in resolver_policy.source_priority:
            reasons.append("unconfigured_source_priority")
        if reasons:
            rejected.append(CandidateRejection(candidate.candidate_id, candidate.row_key, tuple(reasons)))
        else:
            eligible.append(candidate)

    if not eligible:
        reason = "no_candidates" if not normalised else "no_eligible_candidates"
        return CandidateResolution(
            requested_year,
            resolver_policy.policy_id,
            None,
            None,
            None,
            None,
            None,
            reason,
            tuple(sorted(rejected, key=lambda item: item.candidate_id)),
        )

    def rank(candidate: Candidate) -> tuple[int, int, int, int, str]:
        direction, _, _ = _direction_and_treatment(candidate, requested_year)
        direction_rank = {"exact": 0, "earlier": 1, "future": 2}[direction]
        year_rank = -candidate.source_data_year if direction != "future" else candidate.source_data_year
        return (
            direction_rank,
            year_rank,
            resolver_policy.quality_tier_priority[candidate.quality_tier],
            resolver_policy.source_priority[candidate.source_priority_id],
            candidate.candidate_id,
        )

    selected = min(eligible, key=rank)

    def selection_rejection_reason(candidate: Candidate) -> str:
        selected_direction, _, _ = _direction_and_treatment(selected, requested_year)
        candidate_direction, _, _ = _direction_and_treatment(candidate, requested_year)
        if selected_direction != candidate_direction:
            if selected_direction == "exact":
                return "exact_year_preferred"
            return "eligible_earlier_data_preferred_over_future"
        if selected_direction == "earlier" and selected.source_data_year > candidate.source_data_year:
            return "newer_eligible_earlier_year_preferred"
        if selected_direction == "future" and selected.source_data_year < candidate.source_data_year:
            return "earlier_eligible_future_year_preferred"
        selected_quality = resolver_policy.quality_tier_priority[selected.quality_tier]
        candidate_quality = resolver_policy.quality_tier_priority[candidate.quality_tier]
        if selected_quality < candidate_quality:
            return "higher_configured_quality_tier_preferred"
        selected_source = resolver_policy.source_priority[selected.source_priority_id]
        candidate_source = resolver_policy.source_priority[candidate.source_priority_id]
        if selected_source < candidate_source:
            return "higher_configured_source_priority_preferred"
        return "stable_candidate_id_tie_break_preferred"

    for candidate in eligible:
        if candidate.candidate_id != selected.candidate_id:
            rejected.append(CandidateRejection(candidate.candidate_id, candidate.row_key, (selection_rejection_reason(candidate),)))
    direction, treatment, reason = _direction_and_treatment(selected, requested_year)
    return CandidateResolution(
        requested_year,
        resolver_policy.policy_id,
        selected,
        selected.source_data_year,
        abs(selected.source_data_year - requested_year),
        direction,
        treatment,
        reason,
        tuple(sorted(rejected, key=lambda item: item.candidate_id)),
    )
