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
        "    place: Reston, Virginia\n"
        "    publisher: 'TODO: provide publisher or publishing organization'\n"
        "description:\n"
        "  abstract: Existing placeholder\n"
        "  purpose: Existing placeholder\n"
        "time_period:\n"
        "  begin_date: 20200101\n"
        "  end_date: 20260513\n"
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
        "point_of_contact:\n"
        "  person: Jane Doe\n"
        "  organization: U.S. Geological Survey\n"
        "  position: Geologist\n"
        "  address: 1 Main St\n"
        "  city: Reston\n"
        "  state: VA\n"
        "  postal: 20192\n"
        "  country: USA\n"
        "  phone: 555-111-2222\n"
        "  email: jane@example.com\n"
        "distribution:\n"
        "  distributor:\n"
        "    person: Jane Doe\n"
        "    organization: U.S. Geological Survey\n"
        "    position: Geologist\n"
        "    address: 1 Main St\n"
        "    city: Reston\n"
        "    state: VA\n"
        "    postal: 20192\n"
        "    country: USA\n"
        "    phone: 555-111-2222\n"
        "    email: jane@example.com\n"
        "metadata:\n"
        "  date: '20260513'\n"
        "  contact:\n"
        "    person: Jane Doe\n"
        "    organization: U.S. Geological Survey\n"
        "    position: Geologist\n"
        "    address: 1 Main St\n"
        "    city: Reston\n"
        "    state: VA\n"
        "    postal: 20192\n"
        "    country: USA\n"
        "    phone: 555-111-2222\n"
        "    email: jane@example.com\n"
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
        "    place: Reston, Virginia\n"
        "    publisher: 'TODO: provide publisher or publishing organization'\n"
        "description:\n"
        "  abstract: 'TODO: user must provide abstract'\n"
        "  purpose: 'TODO: user must provide purpose'\n"
        "time_period:\n"
        "  begin_date: 20200101\n"
        "  end_date: 20260513\n"
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
        "point_of_contact:\n"
        "  person: Jane Doe\n"
        "  organization: U.S. Geological Survey\n"
        "  position: Geologist\n"
        "  address: 1 Main St\n"
        "  city: Reston\n"
        "  state: VA\n"
        "  postal: 20192\n"
        "  country: USA\n"
        "  phone: 555-111-2222\n"
        "  email: jane@example.com\n"
        "distribution:\n"
        "  distributor:\n"
        "    person: Jane Doe\n"
        "    organization: U.S. Geological Survey\n"
        "    position: Geologist\n"
        "    address: 1 Main St\n"
        "    city: Reston\n"
        "    state: VA\n"
        "    postal: 20192\n"
        "    country: USA\n"
        "    phone: 555-111-2222\n"
        "    email: jane@example.com\n"
        "metadata:\n"
        "  date: '20260513'\n"
        "  contact:\n"
        "    person: Jane Doe\n"
        "    organization: U.S. Geological Survey\n"
        "    position: Geologist\n"
        "    address: 1 Main St\n"
        "    city: Reston\n"
        "    state: VA\n"
        "    postal: 20192\n"
        "    country: USA\n"
        "    phone: 555-111-2222\n"
        "    email: jane@example.com\n"
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


def test_fill_command_propagates_dataset_contact_to_distribution_and_metadata(tmp_path: Path) -> None:
    yaml_path = tmp_path / "prefill.yml"
    yaml_path.write_text(
        "citation:\n"
        "  title: Example\n"
        "  originators:\n"
        "    - Jane Doe\n"
        "  publication_date: '20260513'\n"
        "  publication_status:\n"
        "    progress: Complete\n"
        "    update: None planned\n"
        "  publication_info:\n"
        "    publisher: U.S. Geological Survey\n"
        "description:\n"
        "  abstract: Example abstract\n"
        "  purpose: Example purpose\n"
        "time_period:\n"
        "  begin_date: 20200101\n"
        "  end_date: 20260513\n"
        "  current: publication date\n"
        "spatial_domain:\n"
        "  bounding_coordinates:\n"
        "    west: -1\n"
        "    east: 1\n"
        "    north: 1\n"
        "    south: -1\n"
        "data_quality:\n"
        "  attribute_accuracy: Done\n"
        "  logical_consistency: Done\n"
        "  completeness: Done\n"
        "spatial_reference:\n"
        "  type: geographic\n"
        "point_of_contact:\n"
        "  person: 'TODO: provide metadata contact'\n"
        "  organization: 'TODO: provide organization'\n"
        "  position: 'TODO: provide position or role'\n"
        "  address: 'TODO: provide mailing address'\n"
        "  city: 'TODO: provide city'\n"
        "  state: 'TODO: provide state or province'\n"
        "  postal: 'TODO: provide postal code'\n"
        "  country: 'TODO: provide country'\n"
        "  phone: 'TODO: provide phone number'\n"
        "  email: 'TODO: provide email address'\n"
        "distribution:\n"
        "  distributor:\n"
        "    person: 'TODO: provide distribution contact'\n"
        "    organization: 'TODO: provide distributor organization'\n"
        "metadata:\n"
        "  date: '20260513'\n"
        "  contact:\n"
        "    person: 'TODO: provide metadata contact'\n"
        "    organization: 'TODO: provide metadata contact organization'\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["fill", str(yaml_path)],
        input=(
            "Jane Doe\n"
            "U.S. Geological Survey\n"
            "Geologist\n"
            "1 Main St\n"
            "Reston\n"
            "VA\n"
            "20192\n"
            "USA\n"
            "555-111-2222\n"
            "jane@example.com\n"
        ),
    )

    assert result.exit_code == 0
    updated = yaml_path.read_text(encoding="utf-8")
    assert "person: Jane Doe" in updated
    assert "organization: U.S. Geological Survey" in updated
    assert "jane@example.com" in updated


def test_build_command_allows_placeholder_required_fields(tmp_path: Path) -> None:
    yaml_path = tmp_path / "prefill.yml"
    xml_path = tmp_path / "metadata.xml"
    yaml_path.write_text(
        "citation:\n"
        "  title: Example\n"
        "  originators:\n"
        "    - 'TODO: add originator/author name'\n"
        "  publication_date: 'TODO: set publication or release date'\n"
        "  publication_status:\n"
        "    progress: 'TODO: set publication status progress'\n"
        "    update: 'TODO: set update frequency or maintenance plan'\n"
        "  geoform: vector digital data\n"
        "  publication_info:\n"
        "    publisher: 'TODO: provide publisher or publishing organization'\n"
        "description:\n"
        "  abstract: 'TODO: user must provide abstract'\n"
        "  purpose: 'TODO: user must provide purpose'\n"
        "time_period:\n"
        "  current: 'TODO: set currentness reference'\n"
        "spatial_domain:\n"
        "  bounding_coordinates:\n"
        "    west: -1\n"
        "    east: 1\n"
        "    north: 1\n"
        "    south: -1\n"
        "data_quality:\n"
        "  attribute_accuracy: 'TODO: describe attribute accuracy'\n"
        "  logical_consistency: 'TODO: describe logical consistency'\n"
        "  completeness: 'TODO: describe completeness'\n"
        "spatial_reference:\n"
        "  type: geographic\n"
        "  geographic:\n"
        "    unit: Decimal degrees\n"
        "  geodetic: {}\n"
        "constraints:\n"
        "  use_limitations: 'TODO: describe use constraints'\n"
        "metadata:\n"
        "  date: '20260527'\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(yaml_path), "--out", str(xml_path)])

    assert result.exit_code == 0
    assert "WARNING: Building XML with missing or placeholder required metadata fields:" in result.stdout
    assert "Metadata XML written to" in result.stdout
    assert xml_path.exists()
