from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from metamapper.config import MetadataConfig


def load_metadata_config(path: str | Path, validate_required: bool = True) -> MetadataConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Metadata YAML must contain a top-level mapping: {config_path}")
    if validate_required:
        return MetadataConfig.from_dict(data)
    return MetadataConfig(data=data)


def load_yaml_document(path: str | Path) -> dict[str, Any]:
    """Load a generic YAML document without metadata-specific validation."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML document must contain a top-level mapping: {config_path}")
    return data


def write_yaml_document(path: str | Path, document: dict[str, Any]) -> Path:
    """Write a generic YAML document to disk."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=False, default_flow_style=False)
    return output_path
