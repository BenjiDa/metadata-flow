from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metamapper.config import find_missing_required_fields, get_path, set_path


LONG_FORM_FIELDS = {
    "description.abstract",
    "description.purpose",
    "constraints.use_limitations",
    "data_quality.attribute_accuracy",
    "data_quality.logical_consistency",
    "data_quality.completeness",
}


@dataclass(frozen=True, slots=True)
class FieldPrompt:
    path: str
    prompt: str
    help_text: str
    multiline: bool = False
    list_mode: bool = False
    short_form: bool = True


FIELD_PROMPTS: dict[str, FieldPrompt] = {
    "citation.originators": FieldPrompt(
        path="citation.originators",
        prompt="Originator(s)",
        help_text="Enter one or more originators, separated by commas.",
        list_mode=True,
    ),
    "citation.publication_date": FieldPrompt(
        path="citation.publication_date",
        prompt="Publication date",
        help_text="Examples: 2026 or 20260513 depending on the record.",
    ),
    "citation.publication_status.progress": FieldPrompt(
        path="citation.publication_status.progress",
        prompt="Publication progress",
        help_text="Common values: Complete, In work.",
    ),
    "citation.publication_status.update": FieldPrompt(
        path="citation.publication_status.update",
        prompt="Update frequency",
        help_text="Common values: None planned, Unknown, As needed.",
    ),
    "citation.publication_info.publisher": FieldPrompt(
        path="citation.publication_info.publisher",
        prompt="Publisher",
        help_text="Examples: U.S. Geological Survey, ScienceBase.",
    ),
    "description.abstract": FieldPrompt(
        path="description.abstract",
        prompt="Abstract",
        help_text="Enter a short abstract. Finish multiline input with a single '.' on its own line.",
        multiline=True,
        short_form=False,
    ),
    "description.purpose": FieldPrompt(
        path="description.purpose",
        prompt="Purpose",
        help_text="Describe why the dataset exists. Finish multiline input with a single '.' on its own line.",
        multiline=True,
        short_form=False,
    ),
    "time_period.current": FieldPrompt(
        path="time_period.current",
        prompt="Currentness reference",
        help_text="Common values: publication date, observed, ground condition.",
    ),
    "constraints.use_limitations": FieldPrompt(
        path="constraints.use_limitations",
        prompt="Use limitations",
        help_text="State use constraints or scale/resolution cautions. Finish multiline input with '.' on its own line.",
        multiline=True,
        short_form=False,
    ),
    "data_quality.attribute_accuracy": FieldPrompt(
        path="data_quality.attribute_accuracy",
        prompt="Attribute accuracy",
        help_text="Describe attribute accuracy and limitations. Finish multiline input with '.' on its own line.",
        multiline=True,
        short_form=False,
    ),
    "data_quality.logical_consistency": FieldPrompt(
        path="data_quality.logical_consistency",
        prompt="Logical consistency",
        help_text="Describe logical consistency checks. Finish multiline input with '.' on its own line.",
        multiline=True,
        short_form=False,
    ),
    "data_quality.completeness": FieldPrompt(
        path="data_quality.completeness",
        prompt="Completeness",
        help_text="Describe dataset completeness and omissions. Finish multiline input with '.' on its own line.",
        multiline=True,
        short_form=False,
    ),
}


def get_missing_field_prompts(
    document: dict[str, Any],
    only_missing: bool = True,
    include_long_form: bool = False,
) -> list[FieldPrompt]:
    """Return the completion prompts relevant for a metadata document."""

    prompt_paths = list(FIELD_PROMPTS)
    if only_missing:
        missing = set(find_missing_required_fields(document))
        prompt_paths = [path for path in prompt_paths if path in missing]
    prompts = [FIELD_PROMPTS[path] for path in prompt_paths]
    if not include_long_form:
        prompts = [prompt for prompt in prompts if prompt.short_form]
    return prompts


def parse_user_value(prompt: FieldPrompt, raw_value: str) -> Any:
    """Convert raw user input into YAML-friendly values."""

    if prompt.list_mode:
        values = [item.strip() for item in raw_value.split(",") if item.strip()]
        return values
    return raw_value.strip()


def update_document_value(document: dict[str, Any], path: str, value: Any) -> None:
    """Apply a completed value to the metadata document."""

    set_path(document, path, value)


def current_display_value(document: dict[str, Any], path: str) -> str:
    """Render the current field value for CLI display."""

    value = get_path(document, path)
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def is_placeholder_display(value: str) -> bool:
    """Return True when a displayed value is just a placeholder/TODO."""

    stripped = value.strip()
    return stripped.startswith("TODO:") or stripped.startswith("todo:")
