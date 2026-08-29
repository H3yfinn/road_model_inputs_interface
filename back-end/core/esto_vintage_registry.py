"""Strict registry for the ESTO vintage choices exposed by Module 1."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "road_model"
    / "config"
    / "esto_vintage_registry.csv"
)
REGISTRY_COLUMNS = (
    "esto_vintage", "base_year", "is_preliminary", "is_default", "package_version",
)
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class EstoVintage:
    esto_vintage: int
    base_year: int
    is_preliminary: bool
    is_default: bool
    package_version: str

    @property
    def label(self) -> str:
        suffix = " (Preliminary)" if self.is_preliminary else ""
        return f"ESTO {self.esto_vintage} — Base year {self.base_year}{suffix}"


def _strict_year(value: str, field: str, row_number: int) -> int:
    text = str(value).strip()
    if not re.fullmatch(r"\d{4}", text):
        raise ValueError(f"{field} on registry row {row_number} must be a four-digit integer year.")
    return int(text)


def _strict_bool(value: str, field: str, row_number: int) -> bool:
    text = str(value).strip().lower()
    if text not in {"true", "false"}:
        raise ValueError(f"{field} on registry row {row_number} must be True or False.")
    return text == "true"


def load_esto_vintage_registry(path: Path = REGISTRY_PATH) -> list[EstoVintage]:
    """Load and validate the complete ESTO-vintage-to-package mapping."""
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != REGISTRY_COLUMNS:
            raise ValueError(
                f"ESTO vintage registry columns must be exactly {list(REGISTRY_COLUMNS)}."
            )
        records = []
        for row_number, row in enumerate(reader, start=2):
            vintage = _strict_year(row["esto_vintage"], "esto_vintage", row_number)
            base_year = _strict_year(row["base_year"], "base_year", row_number)
            if base_year != vintage - 2:
                raise ValueError(
                    f"Registry row {row_number} must map ESTO vintage {vintage} to base year {vintage - 2}."
                )
            package_version = str(row["package_version"]).strip()
            if not _VERSION_PATTERN.fullmatch(package_version):
                raise ValueError(f"package_version on registry row {row_number} is invalid.")
            records.append(
                EstoVintage(
                    esto_vintage=vintage,
                    base_year=base_year,
                    is_preliminary=_strict_bool(row["is_preliminary"], "is_preliminary", row_number),
                    is_default=_strict_bool(row["is_default"], "is_default", row_number),
                    package_version=package_version,
                )
            )

    if not records:
        raise ValueError("ESTO vintage registry must contain at least one row.")
    for field in ("esto_vintage", "base_year", "package_version"):
        values = [getattr(record, field) for record in records]
        if len(values) != len(set(values)):
            raise ValueError(f"ESTO vintage registry contains duplicate {field} values.")
    defaults = [record for record in records if record.is_default]
    if len(defaults) != 1:
        raise ValueError("ESTO vintage registry must contain exactly one default vintage.")
    return sorted(records, key=lambda record: record.esto_vintage)


def build_available_vintage_index(
    records: list[EstoVintage], available_versions: set[str],
) -> tuple[list[dict[str, object]], int | None]:
    """Return publishable vintage metadata without permitting default drift."""
    default_record = next(record for record in records if record.is_default)
    available = [
        {
            "esto_vintage": record.esto_vintage,
            "base_year": record.base_year,
            "is_preliminary": record.is_preliminary,
            "package_version": record.package_version,
            "label": record.label,
        }
        for record in records
        if record.package_version in available_versions
    ]
    if available and default_record.package_version not in available_versions:
        raise ValueError(
            "Vintage packages are present but the configured default package is missing: "
            f"{default_record.package_version}."
        )
    return available, default_record.esto_vintage if available else None
