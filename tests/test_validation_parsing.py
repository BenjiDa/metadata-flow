from pathlib import Path

from metamapper.validators import parse_validation_output


def test_parse_example_validation_output_counts_warnings() -> None:
    result = parse_validation_output(Path("examples/validation_outputs/sim3514.gdb-ValidationErrors.html"))
    assert result.passed is True
    assert result.error_count == 0
    assert result.warning_count == 5


def test_parse_validation_output_with_multiple_warning_sections() -> None:
    result = parse_validation_output(Path("examples/validation_outputs/Geysers_GeMS_geodatabase.gdb-ValidationErrors.html"))
    assert result.error_count == 0
    assert result.warning_count == 2
    assert any("NAD_1927_UTM_Zone_10N" in message.message for message in result.validation_messages)
