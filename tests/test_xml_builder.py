from pathlib import Path

from lxml import etree

from metamapper.xml_builder import build_metadata_xml, write_metadata_xml
from metamapper.yaml_reader import load_metadata_config


def test_build_xml_successfully(tmp_path: Path) -> None:
    config = load_metadata_config(Path("configs/example_metadata.yml"))
    tree = build_metadata_xml(config)
    output_path = write_metadata_xml(tree, tmp_path / "metadata.xml")

    assert output_path.exists()

    parsed = etree.parse(str(output_path))
    assert parsed.xpath("/metadata/idinfo/citation/citeinfo/title/text()")
    assert parsed.xpath("/metadata/idinfo/descript/abstract/text()")
    assert parsed.xpath("/metadata/dataqual/lineage/procstep")
    assert parsed.xpath("/metadata/spref/horizsys/geodetic/horizdn/text()")
    assert parsed.xpath("/metadata/metainfo/metd/text()")


def test_build_xml_writes_eainfo_overview_and_skips_empty_detailed(tmp_path: Path) -> None:
    config = load_metadata_config(Path("configs/example_metadata.yml"), validate_required=False)
    config.data["entity_attribute_information"] = {
        "overview": {
            "description": "GeMS overview text.",
            "citation": "GeMS standard.",
        },
        "entities": [
            {
                "name": "MapUnitPolys",
                "description": "Polygons that record map units.",
                "definition_source": "GeMS",
                "attributes": [],
            },
            {
                "name": "CustomLayer",
                "description": "Custom layer.",
                "definition_source": "Producer Defined",
                "attributes": [
                    {
                        "label": "ReviewerNotes",
                        "definition": "Custom notes field.",
                        "definition_source": "Source dataset field schema for layer CustomLayer.",
                        "unrepresentable_domain": "Raw field type: string",
                    }
                ],
            },
        ],
    }

    tree = build_metadata_xml(config)
    output_path = write_metadata_xml(tree, tmp_path / "metadata.xml")
    parsed = etree.parse(str(output_path))

    assert parsed.xpath("/metadata/eainfo/overview/eaover/text()") == ["GeMS overview text."]
    assert parsed.xpath("/metadata/eainfo/overview/eadetcit/text()") == ["GeMS standard."]
    assert parsed.xpath("count(/metadata/eainfo/detailed)") == 1.0
    assert parsed.xpath("/metadata/eainfo/detailed/enttyp/enttypl/text()") == ["CustomLayer"]
