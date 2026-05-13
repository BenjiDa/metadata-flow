from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from metamapper.completion import (
    current_display_value,
    get_missing_field_prompts,
    is_placeholder_display,
    parse_user_value,
    update_document_value,
)
from metamapper.config import MissingRequiredFieldsError, find_missing_required_fields
from metamapper.inspection_backends import InspectionError
from metamapper.inspector import DatasetInspector
from metamapper.prefill import build_prefill_document, write_prefill_yaml
from metamapper.reports import write_validation_report
from metamapper.validators import run_validation
from metamapper.xml_builder import build_metadata_xml, write_metadata_xml
from metamapper.yaml_reader import load_metadata_config, load_yaml_document, write_yaml_document

app = typer.Typer(help="Build and validate FGDC/USGS-style geologic metadata XML from YAML.")
console = Console()
inspector = DatasetInspector()


def _render_validation_summary(result_path: Path, report_path: Path, summary_path: Path, passed: bool, error_count: int, warning_count: int) -> None:
    table = Table(title="Validation Summary")
    table.add_column("Output")
    table.add_column("Value")
    table.add_row("XML", str(result_path))
    table.add_row("Report", str(report_path))
    table.add_row("Summary JSON", str(summary_path))
    table.add_row("Passed", str(passed))
    table.add_row("Errors", str(error_count))
    table.add_row("Warnings", str(warning_count))
    console.print(table)


@app.command()
def build(
    config_path: Path,
    out: Path = typer.Option(Path("outputs/metadata.xml"), "--out", "-o", help="Path for generated XML."),
) -> None:
    """Build metadata XML from a YAML file."""
    try:
        config = load_metadata_config(config_path)
    except MissingRequiredFieldsError as exc:
        console.print(f"ERROR: {exc}")
        raise typer.Exit(code=1) from exc
    tree = build_metadata_xml(config)
    output_path = write_metadata_xml(tree, out)
    console.print(f"Metadata XML written to {output_path}")


@app.command()
def layers(dataset_path: Path) -> None:
    """List available layers for a dataset container."""
    try:
        layer_names = inspector.list_layers(dataset_path)
    except InspectionError as exc:
        console.print(f"ERROR: {exc}")
        raise typer.Exit(code=1) from exc

    if not layer_names:
        console.print("No layers discovered.")
        raise typer.Exit(code=0)

    table = Table(title=f"Layers: {dataset_path}")
    table.add_column("Layer")
    for layer_name in layer_names:
        table.add_row(layer_name)
    console.print(table)


@app.command()
def inspect(
    dataset_path: Path,
    layer: str | None = typer.Option(None, help="Layer name for multi-layer datasets such as File Geodatabases."),
    out: Path = typer.Option(Path("outputs/prefill.yaml"), "--out", "-o", help="Path for generated YAML prefill."),
) -> None:
    """Inspect a dataset and generate an editable metadata YAML draft."""
    try:
        inspection = inspector.inspect(dataset_path, layer=layer)
    except InspectionError as exc:
        console.print(f"ERROR: {exc}")
        raise typer.Exit(code=1) from exc

    document = build_prefill_document(inspection)
    output_path = write_prefill_yaml(document, out)
    console.print(f"Metadata prefill written to {output_path}")
    console.print(f"Inspection backend: {inspection.backend_name}")
    if inspection.warnings:
        for warning in inspection.warnings:
            console.print(f"WARNING: {warning}")


@app.command()
def missing(yaml_path: Path) -> None:
    """List unresolved required metadata fields in a YAML file."""
    document = load_yaml_document(yaml_path)
    missing_fields = find_missing_required_fields(document)
    if not missing_fields:
        console.print("No required metadata fields are missing.")
        raise typer.Exit(code=0)

    table = Table(title=f"Missing Required Fields: {yaml_path}")
    table.add_column("Field")
    for field in missing_fields:
        table.add_row(field)
    console.print(table)
    raise typer.Exit(code=1)


@app.command()
def fill(
    yaml_path: Path,
    out: Path | None = typer.Option(None, "--out", "-o", help="Optional alternate output YAML path."),
    only_missing: bool = typer.Option(True, help="Only prompt for currently missing required fields."),
    include_long_form: bool = typer.Option(
        False,
        help="Also prompt for longer narrative fields such as abstract, purpose, and data-quality text.",
    ),
) -> None:
    """Interactively fill required metadata fields in a YAML document."""
    document = load_yaml_document(yaml_path)
    prompts = get_missing_field_prompts(
        document,
        only_missing=only_missing,
        include_long_form=include_long_form,
    )

    if not prompts:
        console.print("No prompted fields need completion.")
        output_path = write_yaml_document(out or yaml_path, document)
        console.print(f"YAML written to {output_path}")
        raise typer.Exit(code=0)

    console.print(f"Filling {len(prompts)} quick metadata field(s).")
    if not include_long_form:
        console.print("Long narrative fields will stay in the YAML for manual editing.")

    for prompt in prompts:
        current_value = current_display_value(document, prompt.path)
        prompt_label = prompt.prompt
        if prompt.list_mode:
            prompt_label += " (comma-separated)"
        if prompt.help_text:
            prompt_label += f" [{prompt.help_text}]"

        if prompt.multiline:
            lines = _prompt_multiline()
            if lines:
                update_document_value(document, prompt.path, "\n".join(lines).strip())
            continue

        show_default = bool(current_value) and not is_placeholder_display(current_value)
        response = typer.prompt(
            prompt_label,
            default=current_value if show_default else "",
            show_default=show_default,
        )
        if response.strip():
            update_document_value(document, prompt.path, parse_user_value(prompt, response))

    output_path = write_yaml_document(out or yaml_path, document)
    remaining = find_missing_required_fields(document)
    console.print(f"YAML written to {output_path}")
    if remaining:
        console.print("Still missing required fields:")
        for field in remaining:
            console.print(f"- {field}")
        if not include_long_form:
            console.print("Tip: edit the YAML directly for the longer narrative fields, or rerun with `--include-long-form`.")
        raise typer.Exit(code=1)
    console.print("Prompted fields completed.")


@app.command()
def validate(
    xml_path: Path,
    external_command: str | None = typer.Option(None, help="Optional external validation command."),
    validator_output: Path | None = typer.Option(None, help="Optional validator report to parse."),
    report_output: Path = typer.Option(Path("outputs/validation_report.txt"), help="Text validation report path."),
    summary_output: Path = typer.Option(Path("outputs/validation_summary.json"), help="JSON validation summary path."),
) -> None:
    """Validate an XML metadata file."""
    result = run_validation(xml_path, external_command=external_command, validator_output_path=validator_output)
    report_path, summary_path = write_validation_report(result, report_output, summary_output)
    _render_validation_summary(xml_path, report_path, summary_path, result.passed, result.error_count, result.warning_count)

    if result.validation_messages:
        for message in result.validation_messages:
            label = message.severity.upper()
            location = f" [{message.section}]" if message.section else ""
            console.print(f"{label}{location}: {message.message}")

    if result.passed:
        console.print("Metadata validation passed.")
    raise typer.Exit(code=0 if result.passed else 1)


@app.command("build-validate")
def build_validate(
    config_path: Path,
    out: Path = typer.Option(Path("outputs/metadata.xml"), "--out", "-o", help="Path for generated XML."),
    report_output: Path = typer.Option(Path("outputs/validation_report.txt"), help="Text validation report path."),
    summary_output: Path = typer.Option(Path("outputs/validation_summary.json"), help="JSON validation summary path."),
) -> None:
    """Build XML from YAML and validate it."""
    try:
        config = load_metadata_config(config_path)
    except MissingRequiredFieldsError as exc:
        console.print(f"ERROR: {exc}")
        raise typer.Exit(code=1) from exc
    tree = build_metadata_xml(config)
    output_path = write_metadata_xml(tree, out)
    validation_config = config.get("validation", {}) or {}
    result = run_validation(
        output_path,
        external_command=validation_config.get("external_command"),
        validator_output_path=validation_config.get("report_path"),
    )
    report_path, summary_path = write_validation_report(result, report_output, summary_output)
    _render_validation_summary(output_path, report_path, summary_path, result.passed, result.error_count, result.warning_count)

    if result.validation_messages:
        for message in result.validation_messages:
            label = message.severity.upper()
            location = f" [{message.section}]" if message.section else ""
            console.print(f"{label}{location}: {message.message}")

    if result.passed:
        console.print("Metadata validation passed.")
    raise typer.Exit(code=0 if result.passed else 1)


def _prompt_multiline() -> list[str]:
    """Prompt for multiline text, ending on a single '.' line or blank first line to skip."""

    console.print("Enter text, finish with a single '.' on its own line, or press Enter immediately to skip.")
    lines: list[str] = []
    while True:
        line = typer.prompt("", prompt_suffix="", show_default=False, default="")
        if not lines and not line:
            return []
        if line.strip() == ".":
            break
        lines.append(line)
    return lines


if __name__ == "__main__":
    app()
