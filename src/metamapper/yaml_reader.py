from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from metamapper.config import MetadataConfig


def load_metadata_config(path: str | Path) -> MetadataConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Metadata YAML must contain a top-level mapping: {config_path}")
    return MetadataConfig.from_dict(data)


def load_yaml_document(path: str | Path) -> dict[str, Any]:
    """Load a generic YAML document without metadata-specific validation."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML document must contain a top-level mapping: {config_path}")
    return data
