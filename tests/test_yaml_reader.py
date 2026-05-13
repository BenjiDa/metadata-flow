from pathlib import Path

import pytest

from metamapper.config import MissingRequiredFieldsError
from metamapper.yaml_reader import load_metadata_config


def test_load_example_yaml() -> None:
    config = load_metadata_config(Path("configs/example_metadata.yml"))
    assert config.get("citation.title")
    assert config.get("metadata.date") == "20260512"


def test_missing_required_yaml_fields_raise_useful_error(tmp_path: Path) -> None:
    bad_config = tmp_path / "bad.yml"
    bad_config.write_text("citation:\n  title: Missing almost everything\n", encoding="utf-8")

    with pytest.raises(MissingRequiredFieldsError) as exc:
        load_metadata_config(bad_config)

    message = str(exc.value)
    assert "citation.originators" in message
    assert "description.abstract" in message
