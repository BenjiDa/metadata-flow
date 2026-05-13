from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class MissingRequiredFieldsError(ValueError):
    """Raised when required YAML fields are missing."""

    def __init__(self, missing_fields: list[str]):
        self.missing_fields = sorted(missing_fields)
        message = "Missing required metadata fields:\n- " + "\n- ".join(self.missing_fields)
        super().__init__(message)


REQUIRED_YAML_FIELDS = [
    "citation.title",
    "citation.originators",
    "citation.publication_date",
    "citation.publication_status.progress",
    "citation.publication_status.update",
    "citation.publication_info.publisher",
    "description.abstract",
    "description.purpose",
    "time_period.current",
    "spatial_domain.bounding_coordinates.west",
    "spatial_domain.bounding_coordinates.east",
    "spatial_domain.bounding_coordinates.north",
    "spatial_domain.bounding_coordinates.south",
    "data_quality.attribute_accuracy",
    "data_quality.logical_consistency",
    "data_quality.completeness",
    "spatial_reference.type",
    "metadata.date",
    "constraints.use_limitations",
]

PLACEHOLDER_PREFIXES = ("TODO:", "todo:")


def _is_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().startswith(PLACEHOLDER_PREFIXES)
    if isinstance(value, list):
        return bool(value) and all(_is_placeholder(item) for item in value)
    return False


@dataclass(slots=True)
class MetadataConfig:
    data: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetadataConfig":
        config = cls(data=data)
        config.validate_required_fields()
        return config

    def get(self, path: str, default: Any = None) -> Any:
        value: Any = self.data
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def validate_required_fields(self) -> None:
        missing: list[str] = []
        for path in REQUIRED_YAML_FIELDS:
            value = self.get(path)
            if value is None:
                missing.append(path)
                continue
            if isinstance(value, str) and not value.strip():
                missing.append(path)
                continue
            if _is_placeholder(value):
                missing.append(path)
                continue
            if isinstance(value, list) and not value:
                missing.append(path)
        if missing:
            raise MissingRequiredFieldsError(missing)
