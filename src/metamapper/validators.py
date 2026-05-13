from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree, html


REQUIRED_XML_PATHS = [
    "/metadata/idinfo/citation/citeinfo/title",
    "/metadata/idinfo/citation/citeinfo/pubdate",
    "/metadata/idinfo/descript/abstract",
    "/metadata/idinfo/descript/purpose",
    "/metadata/idinfo/timeperd/current",
    "/metadata/idinfo/spdom/bounding/westbc",
    "/metadata/idinfo/spdom/bounding/eastbc",
    "/metadata/idinfo/spdom/bounding/northbc",
    "/metadata/idinfo/spdom/bounding/southbc",
    "/metadata/dataqual/attracc/attraccr",
    "/metadata/dataqual/logic",
    "/metadata/dataqual/complete",
    "/metadata/spref/horizsys/geodetic/horizdn",
    "/metadata/metainfo/metd",
    "/metadata/metainfo/metstdn",
    "/metadata/metainfo/metstdv",
]


@dataclass(slots=True)
class ValidationMessage:
    severity: str
    message: str
    section: str | None = None
    source: str | None = None


@dataclass(slots=True)
class ValidationResult:
    passed: bool
    error_count: int
    warning_count: int
    missing_required_fields: list[str] = field(default_factory=list)
    validation_messages: list[ValidationMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["validation_messages"] = [asdict(message) for message in self.validation_messages]
        return data


def parse_validation_output(path: str | Path) -> ValidationResult:
    report_path = Path(path)
    content = report_path.read_text(encoding="utf-8")
    if report_path.suffix.lower() in {".html", ".htm"}:
        return _parse_html_validation_output(content, report_path)
    return _parse_text_validation_output(content, report_path)


def _parse_html_validation_output(content: str, source: Path) -> ValidationResult:
    document = html.fromstring(content)
    messages: list[ValidationMessage] = []

    for heading in document.xpath("//h3"):
        section_title = " ".join(heading.text_content().split())
        report_div = heading.getnext()
        if report_div is None:
            continue

        current_subsection: str | None = None
        buffer: list[str] = []

        for child in report_div.iterchildren():
            if child.tag == "h4":
                current_subsection = " ".join(child.text_content().split())
                tail_text = " ".join((child.tail or "").split())
                if tail_text:
                    buffer.append(tail_text)
                continue

            if child.tag == "br":
                _flush_html_validation_message(
                    messages=messages,
                    buffer=buffer,
                    section_title=section_title,
                    current_subsection=current_subsection,
                    source=source,
                )
                continue

            child_text = " ".join(child.text_content().split())
            if child_text:
                buffer.append(child_text)
            tail_text = " ".join((child.tail or "").split())
            if tail_text:
                buffer.append(tail_text)

        _flush_html_validation_message(
            messages=messages,
            buffer=buffer,
            section_title=section_title,
            current_subsection=current_subsection,
            source=source,
        )

    error_count = sum(1 for message in messages if message.severity == "error")
    warning_count = sum(1 for message in messages if message.severity == "warning")
    return ValidationResult(
        passed=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        validation_messages=messages,
    )


def _flush_html_validation_message(
    messages: list[ValidationMessage],
    buffer: list[str],
    section_title: str,
    current_subsection: str | None,
    source: Path,
) -> None:
    message_text = " ".join(part for part in buffer if part).strip()
    buffer.clear()
    if not message_text:
        return
    severity = "error" if "error" in section_title.lower() else "warning"
    messages.append(
        ValidationMessage(
            severity=severity,
            message=message_text,
            section=current_subsection or section_title,
            source=str(source),
        )
    )


def _parse_text_validation_output(content: str, source: Path) -> ValidationResult:
    messages: list[ValidationMessage] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if "error" in lowered:
            severity = "error"
        elif "warning" in lowered:
            severity = "warning"
        else:
            continue
        messages.append(ValidationMessage(severity=severity, message=line, source=str(source)))

    error_count = sum(1 for message in messages if message.severity == "error")
    warning_count = sum(1 for message in messages if message.severity == "warning")
    return ValidationResult(
        passed=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        validation_messages=messages,
    )


def run_internal_validation(xml_path: str | Path) -> ValidationResult:
    path = Path(xml_path)
    messages: list[ValidationMessage] = []
    missing_required_fields: list[str] = []

    try:
        tree = etree.parse(str(path))
    except etree.XMLSyntaxError as exc:
        return ValidationResult(
            passed=False,
            error_count=1,
            warning_count=0,
            validation_messages=[
                ValidationMessage(severity="error", message=f"XML syntax error: {exc}", source=str(path))
            ],
        )

    root = tree.getroot()
    if root.tag != "metadata":
        messages.append(
            ValidationMessage(
                severity="error",
                message="Root element must be <metadata>.",
                section="document",
                source=str(path),
            )
        )

    for xpath in REQUIRED_XML_PATHS:
        nodes = tree.xpath(xpath)
        if not nodes:
            missing_required_fields.append(xpath)
            messages.append(
                ValidationMessage(
                    severity="error",
                    message=f"Missing required XML element: {xpath}",
                    section="structure",
                    source=str(path),
                )
            )
            continue
        if not any((node.text or "").strip() for node in nodes if hasattr(node, "text")):
            missing_required_fields.append(xpath)
            messages.append(
                ValidationMessage(
                    severity="error",
                    message=f"Required XML element is empty: {xpath}",
                    section="structure",
                    source=str(path),
                )
            )

    if not tree.xpath("/metadata/idinfo/keywords"):
        messages.append(
            ValidationMessage(
                severity="warning",
                message="No keywords section found under /metadata/idinfo.",
                section="keywords",
                source=str(path),
            )
        )

    error_count = sum(1 for message in messages if message.severity == "error")
    warning_count = sum(1 for message in messages if message.severity == "warning")
    return ValidationResult(
        passed=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        missing_required_fields=sorted(set(missing_required_fields)),
        validation_messages=messages,
    )


def run_validation(
    xml_path: str | Path,
    external_command: str | None = None,
    validator_output_path: str | Path | None = None,
) -> ValidationResult:
    internal_result = run_internal_validation(xml_path)
    if external_command is None:
        return internal_result

    xml_path = Path(xml_path)
    command = external_command.format(xml_path=xml_path, output_dir=xml_path.parent)
    completed = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        check=False,
    )

    external_result: ValidationResult | None = None
    if validator_output_path:
        report_path = Path(validator_output_path)
        if report_path.exists():
            external_result = parse_validation_output(report_path)
    elif completed.stdout or completed.stderr:
        temp_path = xml_path.parent / "_external_validation_output.txt"
        temp_path.write_text((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else ""), encoding="utf-8")
        external_result = parse_validation_output(temp_path)

    messages = list(internal_result.validation_messages)
    missing_required_fields = list(internal_result.missing_required_fields)
    error_count = internal_result.error_count
    warning_count = internal_result.warning_count

    if completed.returncode != 0:
        messages.append(
            ValidationMessage(
                severity="error",
                message=f"External validation command failed with exit code {completed.returncode}.",
                section="external-validator",
                source=command,
            )
        )
        error_count += 1

    if external_result:
        messages.extend(external_result.validation_messages)
        missing_required_fields.extend(external_result.missing_required_fields)
        error_count += external_result.error_count
        warning_count += external_result.warning_count
    else:
        stdout_text = (completed.stdout or "").strip()
        stderr_text = (completed.stderr or "").strip()
        for stream_name, text in (("stdout", stdout_text), ("stderr", stderr_text)):
            if text:
                for line in text.splitlines():
                    messages.append(
                        ValidationMessage(
                            severity="warning",
                            message=line.strip(),
                            section=f"external-validator-{stream_name}",
                            source=command,
                        )
                    )
                    warning_count += 1

    return ValidationResult(
        passed=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        missing_required_fields=sorted(set(missing_required_fields)),
        validation_messages=messages,
    )


def result_to_json(result: ValidationResult) -> str:
    return json.dumps(result.to_dict(), indent=2)
