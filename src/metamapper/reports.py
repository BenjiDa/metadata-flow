from __future__ import annotations

from pathlib import Path

from metamapper.validators import ValidationResult, result_to_json


def write_validation_report(result: ValidationResult, report_path: str | Path, summary_path: str | Path) -> tuple[Path, Path]:
    report_path = Path(report_path)
    summary_path = Path(summary_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"passed: {result.passed}",
        f"errors: {result.error_count}",
        f"warnings: {result.warning_count}",
    ]
    if result.missing_required_fields:
        lines.append("missing_required_fields:")
        lines.extend(f"- {field}" for field in result.missing_required_fields)
    if result.validation_messages:
        lines.append("messages:")
        for message in result.validation_messages:
            section = f" [{message.section}]" if message.section else ""
            lines.append(f"- {message.severity.upper()}{section}: {message.message}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary_path.write_text(result_to_json(result) + "\n", encoding="utf-8")
    return report_path, summary_path
