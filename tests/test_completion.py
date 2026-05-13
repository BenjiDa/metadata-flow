from pathlib import Path

from metamapper.completion import current_display_value, get_missing_field_prompts, parse_user_value, update_document_value
from metamapper.config import find_missing_required_fields, set_path
from metamapper.yaml_reader import load_yaml_document, write_yaml_document


def test_find_missing_required_fields_detects_todo_placeholders() -> None:
    document = {
        "citation": {
            "title": "Example",
            "originators": ["TODO: add originator/author name"],
            "publication_date": "TODO: set publication or release date",
            "publication_status": {"progress": "Complete", "update": "None planned"},
            "publication_info": {"publisher": "USGS"},
        },
        "description": {"abstract": "TODO: user must provide abstract", "purpose": "Done"},
        "time_period": {"current": "publication date"},
        "spatial_domain": {"bounding_coordinates": {"west": -1, "east": 1, "north": 1, "south": -1}},
        "data_quality": {"attribute_accuracy": "Done", "logical_consistency": "Done", "completeness": "Done"},
        "spatial_reference": {"type": "geographic"},
        "metadata": {"date": "20260513"},
        "constraints": {"use_limitations": "Done"},
    }

    missing = find_missing_required_fields(document)

    assert "citation.originators" in missing
    assert "citation.publication_date" in missing
    assert "description.abstract" in missing


def test_update_document_value_sets_nested_path() -> None:
    document: dict[str, object] = {}

    update_document_value(document, "citation.publication_info.publisher", "U.S. Geological Survey")

    assert document["citation"]["publication_info"]["publisher"] == "U.S. Geological Survey"  # type: ignore[index]


def test_write_yaml_document_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "roundtrip.yml"
    document = {"citation": {"title": "Round trip"}}

    write_yaml_document(path, document)
    loaded = load_yaml_document(path)

    assert loaded["citation"]["title"] == "Round trip"


def test_get_missing_field_prompts_returns_missing_only() -> None:
    document: dict[str, object] = {}
    prompts = get_missing_field_prompts(document, only_missing=True)

    assert any(prompt.path == "citation.originators" for prompt in prompts)
    assert all(prompt.short_form for prompt in prompts)


def test_get_missing_field_prompts_can_include_long_form() -> None:
    document: dict[str, object] = {}
    prompts = get_missing_field_prompts(document, only_missing=True, include_long_form=True)

    assert any(prompt.path == "description.abstract" for prompt in prompts)
    assert any(not prompt.short_form for prompt in prompts)


def test_parse_user_value_for_list_mode() -> None:
    document: dict[str, object] = {}
    set_path(document, "citation.originators", ["TODO: add originator/author name"])
    prompts = get_missing_field_prompts(document, only_missing=False)
    originator_prompt = next(prompt for prompt in prompts if prompt.path == "citation.originators")

    parsed = parse_user_value(originator_prompt, "Jane Doe, Alex Smith")

    assert parsed == ["Jane Doe", "Alex Smith"]
    assert current_display_value({"citation": {"originators": parsed}}, "citation.originators") == "Jane Doe, Alex Smith"
