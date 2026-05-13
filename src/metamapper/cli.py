from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from metamapper.reports import write_validation_report
from metamapper.validators import run_validation
from metamapper.xml_builder import build_metadata_xml, write_metadata_xml
from metamapper.yaml_reader import load_metadata_config

app = typer.Typer(help="Build and validate FGDC/USGS-style geologic metadata XML from YAML.")
console = Console()


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
    output: Path = typer.Option(Path("outputs/metadata.xml"), help="Path for generated XML."),
) -> None:
    """Build metadata XML from a YAML file."""
    config = load_metadata_config(config_path)
    tree = build_metadata_xml(config)
    output_path = write_metadata_xml(tree, output)
    console.print(f"Metadata XML written to {output_path}")


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
    output: Path = typer.Option(Path("outputs/metadata.xml"), help="Path for generated XML."),
    report_output: Path = typer.Option(Path("outputs/validation_report.txt"), help="Text validation report path."),
    summary_output: Path = typer.Option(Path("outputs/validation_summary.json"), help="JSON validation summary path."),
) -> None:
    """Build XML from YAML and validate it."""
    config = load_metadata_config(config_path)
    tree = build_metadata_xml(config)
    output_path = write_metadata_xml(tree, output)
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


if __name__ == "__main__":
    app()
