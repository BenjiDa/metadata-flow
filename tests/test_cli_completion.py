from pathlib import Path

from typer.testing import CliRunner

from metamapper.cli import app


runner = CliRunner()


def test_missing_command_reports_required_fields(tmp_path: Path) -> None:
    yaml_path = tmp_path / "prefill.yml"
    yaml_path.write_text(
        "citation:\n"
        "  title: Example\n"
        "  originators:\n"
        "    - 'TODO: add originator/author name'\n"
        "description:\n"
        "  abstract: 'TODO: user must provide abstract'\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["missing", str(yaml_path)])

    assert result.exit_code == 1
    assert "citation.originators" in result.stdout
    assert "description.abstract" in result.stdout


def test_fill_command_updates_easy_fields(tmp_path: Path) -> None:
    yaml_path = tmp_path / "prefill.yml"
    yaml_path.write_text(
        "citation:\n"
        "  title: Example\n"
        "  originators:\n"
        "    - 'TODO: add originator/author name'\n"
        "  publication_date: 'TODO: set publication or release date'\n"
        "  publication_status:\n"
        "    progress: 'TODO: set publication status progress'\n"
        "    update: 'TODO: set update frequency or maintenance plan'\n"
        "  publication_info:\n"
        "    publisher: 'TODO: provide publisher or publishing organization'\n"
        "description:\n"
        "  abstract: Existing placeholder\n"
        "  purpose: Existing placeholder\n"
        "time_period:\n"
        "  current: 'TODO: set currentness reference, for example publication date or observed'\n"
        "spatial_domain:\n"
        "  bounding_coordinates:\n"
        "    west: -1\n"
        "    east: 1\n"
        "    north: 1\n"
        "    south: -1\n"
        "data_quality:\n"
        "  attribute_accuracy: Existing placeholder\n"
        "  logical_consistency: Existing placeholder\n"
        "  completeness: Existing placeholder\n"
        "spatial_reference:\n"
        "  type: geographic\n"
        "metadata:\n"
        "  date: '20260513'\n"
        "constraints:\n"
        "  use_limitations: Existing placeholder\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["fill", str(yaml_path)],
        input=(
            "Jane Doe, Alex Smith\n"
            "20260513\n"
            "Complete\n"
            "None planned\n"
            "U.S. Geological Survey\n"
            "publication date\n"
        ),
    )

    assert result.exit_code == 0
    updated = yaml_path.read_text(encoding="utf-8")
    assert "Jane Doe" in updated
    assert "U.S. Geological Survey" in updated
    assert "publication date" in updated


def test_fill_command_leaves_long_form_fields_for_yaml_by_default(tmp_path: Path) -> None:
    yaml_path = tmp_path / "prefill.yml"
    yaml_path.write_text(
        "citation:\n"
        "  title: Example\n"
        "  originators:\n"
        "    - 'TODO: add originator/author name'\n"
        "  publication_date: 'TODO: set publication or release date'\n"
        "  publication_status:\n"
        "    progress: 'TODO: set publication status progress'\n"
        "    update: 'TODO: set update frequency or maintenance plan'\n"
        "  publication_info:\n"
        "    publisher: 'TODO: provide publisher or publishing organization'\n"
        "description:\n"
        "  abstract: 'TODO: user must provide abstract'\n"
        "  purpose: 'TODO: user must provide purpose'\n"
        "time_period:\n"
        "  current: 'TODO: set currentness reference, for example publication date or observed'\n"
        "spatial_domain:\n"
        "  bounding_coordinates:\n"
        "    west: -1\n"
        "    east: 1\n"
        "    north: 1\n"
        "    south: -1\n"
        "data_quality:\n"
        "  attribute_accuracy: 'TODO: describe attribute accuracy and limitations'\n"
        "  logical_consistency: 'TODO: describe logical consistency checks'\n"
        "  completeness: 'TODO: describe dataset completeness'\n"
        "spatial_reference:\n"
        "  type: geographic\n"
        "metadata:\n"
        "  date: '20260513'\n"
        "constraints:\n"
        "  use_limitations: 'TODO: describe use constraints and data limitations'\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["fill", str(yaml_path)],
        input=(
            "Jane Doe\n"
            "20260513\n"
            "Complete\n"
            "None planned\n"
            "U.S. Geological Survey\n"
            "publication date\n"
        ),
    )

    assert result.exit_code == 1
    assert "Long narrative fields will stay in the YAML for manual editing." in result.stdout
    assert "description.abstract" in result.stdout
