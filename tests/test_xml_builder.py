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
