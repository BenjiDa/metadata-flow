from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metamapper.config import get_path, set_path


LONG_FORM_FIELDS = {
    "description.abstract",
    "description.purpose",
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
    "time_period.single_date": FieldPrompt(
        path="time_period.single_date",
        prompt="Single date",
        help_text="Use for one observation or acquisition date. Example: 20260527.",
    ),
    "time_period.begin_date": FieldPrompt(
        path="time_period.begin_date",
        prompt="Begin date",
        help_text="Use for a date range. Example: 20240101.",
    ),
    "time_period.end_date": FieldPrompt(
        path="time_period.end_date",
        prompt="End date",
        help_text="Use for a date range. Example: 20260527.",
    ),
    "point_of_contact.person": FieldPrompt(
        path="point_of_contact.person",
        prompt="Dataset contact person",
        help_text="Primary point of contact name for the dataset.",
    ),
    "point_of_contact.organization": FieldPrompt(
        path="point_of_contact.organization",
        prompt="Dataset contact organization",
        help_text="Organization for the dataset point of contact.",
    ),
    "point_of_contact.position": FieldPrompt(
        path="point_of_contact.position",
        prompt="Dataset contact position",
        help_text="Job title or role.",
    ),
    "point_of_contact.address": FieldPrompt(
        path="point_of_contact.address",
        prompt="Dataset contact address",
        help_text="Street or mailing address.",
    ),
    "point_of_contact.city": FieldPrompt(
        path="point_of_contact.city",
        prompt="Dataset contact city",
        help_text="City for the point of contact.",
    ),
    "point_of_contact.state": FieldPrompt(
        path="point_of_contact.state",
        prompt="Dataset contact state",
        help_text="State or province.",
    ),
    "point_of_contact.postal": FieldPrompt(
        path="point_of_contact.postal",
        prompt="Dataset contact postal code",
        help_text="Postal or ZIP code.",
    ),
    "point_of_contact.country": FieldPrompt(
        path="point_of_contact.country",
        prompt="Dataset contact country",
        help_text="Country name.",
    ),
    "point_of_contact.phone": FieldPrompt(
        path="point_of_contact.phone",
        prompt="Dataset contact phone",
        help_text="Phone number.",
    ),
    "point_of_contact.email": FieldPrompt(
        path="point_of_contact.email",
        prompt="Dataset contact email",
        help_text="Email address.",
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
        prompt_paths = [path for path in prompt_paths if _needs_prompt(document, path)]
    prompts = [FIELD_PROMPTS[path] for path in prompt_paths]
    if not include_long_form:
        prompts = [prompt for prompt in prompts if prompt.short_form]
    return prompts


def _needs_prompt(document: dict[str, Any], path: str) -> bool:
    value = get_path(document, path)
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or is_placeholder_display(stripped)
    if isinstance(value, list):
        return not value or all(isinstance(item, str) and is_placeholder_display(item) for item in value)
    return False


def parse_user_value(prompt: FieldPrompt, raw_value: str) -> Any:
    """Convert raw user input into YAML-friendly values."""

    if prompt.list_mode:
        values = [item.strip() for item in raw_value.split(",") if item.strip()]
        return values
    return raw_value.strip()


def update_document_value(document: dict[str, Any], path: str, value: Any) -> None:
    """Apply a completed value to the metadata document."""

    set_path(document, path, value)


def propagate_shared_contacts(document: dict[str, Any]) -> None:
    """Copy dataset contact details into distribution and metadata contacts when those are blank."""

    source_paths = (
        "person",
        "organization",
        "position",
        "address_type",
        "address",
        "city",
        "state",
        "postal",
        "country",
        "phone",
        "email",
    )
    point_of_contact = get_path(document, "point_of_contact", {})
    if not isinstance(point_of_contact, dict):
        return

    for target_root in ("distribution.distributor", "metadata.contact"):
        for field_name in source_paths:
            source_value = point_of_contact.get(field_name)
            if _is_copyable_contact_value(source_value):
                target_path = f"{target_root}.{field_name}"
                target_value = get_path(document, target_path)
                if _is_blank_or_placeholder(target_value):
                    set_path(document, target_path, source_value)


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


def _is_blank_or_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or is_placeholder_display(stripped)
    if isinstance(value, list):
        return not value or all(_is_blank_or_placeholder(item) for item in value)
    return False


def _is_copyable_contact_value(value: Any) -> bool:
    if isinstance(value, str):
        stripped = value.strip()
        return bool(stripped) and not is_placeholder_display(stripped)
    if isinstance(value, list):
        return any(_is_copyable_contact_value(item) for item in value)
    return value is not None
