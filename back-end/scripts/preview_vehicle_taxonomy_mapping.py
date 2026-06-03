from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass(frozen=True)
class MappingRule:
    source_branch_pattern: str
    transport_type: str
    vehicle_type: str
    size: str
    priority: int
    active: bool
    mapping_note: str


@dataclass(frozen=True)
class MappingResult:
    source_branch_path: str
    matched: bool
    match_mode: str
    transport_type: str
    vehicle_type: str
    size: str
    matched_pattern: str
    priority: int
    mapping_note: str


def _match_mode(pattern: str) -> str:
    if pattern == "*":
        return "fallback"
    if any(ch in pattern for ch in "*?[]"):
        return "wildcard"
    return "exact"


def _is_match(pattern: str, branch: str) -> bool:
    mode = _match_mode(pattern)
    if mode == "exact":
        return pattern == branch
    if mode == "wildcard":
        return fnmatch(branch, pattern)
    return True


def map_branch(branch: str, rules: list[MappingRule]) -> MappingResult:
    active_rules = [r for r in rules if r.active]
    exact_rules = sorted([r for r in active_rules if _match_mode(r.source_branch_pattern) == "exact"], key=lambda r: r.priority)
    wildcard_rules = sorted([r for r in active_rules if _match_mode(r.source_branch_pattern) == "wildcard"], key=lambda r: r.priority)
    fallback_rules = sorted([r for r in active_rules if _match_mode(r.source_branch_pattern) == "fallback"], key=lambda r: r.priority)

    for mode, pool in (("exact", exact_rules), ("wildcard", wildcard_rules), ("fallback", fallback_rules)):
        matches = [r for r in pool if _is_match(r.source_branch_pattern, branch)]
        if not matches:
            continue
        winner = matches[0]
        return MappingResult(
            source_branch_path=branch,
            matched=True,
            match_mode=mode,
            transport_type=winner.transport_type,
            vehicle_type=winner.vehicle_type,
            size=winner.size,
            matched_pattern=winner.source_branch_pattern,
            priority=winner.priority,
            mapping_note=winner.mapping_note,
        )

    return MappingResult(
        source_branch_path=branch,
        matched=False,
        match_mode="none",
        transport_type="",
        vehicle_type="",
        size="",
        matched_pattern="",
        priority=-1,
        mapping_note="",
    )


def preview() -> None:
    rules = [
        MappingRule(
            source_branch_pattern="Demand\\Passenger road\\LPVs\\ICE small\\Motor gasoline",
            transport_type="passenger",
            vehicle_type="passenger_car",
            size="small",
            priority=10,
            active=True,
            mapping_note="Exact override for LPV ICE small gasoline branch.",
        ),
        MappingRule(
            source_branch_pattern="Demand\\Passenger road\\LPVs\\ICE *\\Motor gasoline",
            transport_type="passenger",
            vehicle_type="passenger_car",
            size="derived_from_branch",
            priority=20,
            active=True,
            mapping_note="LPV ICE gasoline wildcard.",
        ),
        MappingRule(
            source_branch_pattern="Demand\\Passenger road\\LPVs\\*\\Gas and diesel oil",
            transport_type="passenger",
            vehicle_type="suv_light_truck",
            size="derived_from_branch",
            priority=30,
            active=True,
            mapping_note="LPV diesel branches default to SUV/light-truck class.",
        ),
        MappingRule(
            source_branch_pattern="Demand\\Freight road\\Trucks\\*",
            transport_type="freight",
            vehicle_type="heavy_truck",
            size="na",
            priority=40,
            active=True,
            mapping_note="Freight truck wildcard.",
        ),
        MappingRule(
            source_branch_pattern="*",
            transport_type="passenger",
            vehicle_type="passenger_car",
            size="na",
            priority=999,
            active=True,
            mapping_note="Explicit fallback for preview only.",
        ),
    ]

    branches = [
        "Demand\\Passenger road\\LPVs\\ICE small\\Motor gasoline",
        "Demand\\Passenger road\\LPVs\\ICE medium\\Motor gasoline",
        "Demand\\Passenger road\\LPVs\\ICE large\\Gas and diesel oil",
        "Demand\\Freight road\\Trucks\\ICE heavy\\Gas and diesel oil",
        "Demand\\Passenger road\\Buses\\ICE\\Motor gasoline",
    ]

    results = [map_branch(branch, rules) for branch in branches]

    print("Vehicle taxonomy mapping preview")
    print("=" * 80)
    print("Matching order: exact -> wildcard -> fallback")
    print("-" * 80)
    header = f"{'source_branch_path':62} | {'mode':8} | {'vehicle_type':20} | {'pattern'}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r.source_branch_path[:62]:62} | {r.match_mode:8} | {r.vehicle_type[:20]:20} | {r.matched_pattern}"
        )

    unmatched = [r for r in results if not r.matched]
    print("-" * 80)
    print(f"Total branches: {len(results)}")
    print(f"Matched: {len(results) - len(unmatched)}")
    print(f"Unmatched: {len(unmatched)}")
    if unmatched:
        print("Unmatched branches:")
        for r in unmatched:
            print(f"  - {r.source_branch_path}")


if __name__ == "__main__":
    preview()
