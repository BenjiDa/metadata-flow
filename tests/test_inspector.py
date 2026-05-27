from pathlib import Path

import importlib.util
import pytest
import sys
from types import SimpleNamespace

from metamapper.config import MissingRequiredFieldsError
from metamapper.inspection_backends import ArcPyBackend, InspectionError, OpenSourceBackend
from metamapper.inspection_types import DatasetInspection, ExtentInfo, FieldInfo, LayerInfo, RasterInfo, SpatialReferenceInfo
from metamapper.inspector import DatasetInspector
from metamapper.prefill import build_prefill_document, write_prefill_yaml
from metamapper.yaml_reader import load_metadata_config, load_yaml_document


class FakeBackend:
    name = "fake-backend"

    def is_available(self) -> bool:
        return True

    def supports(self, path: Path) -> bool:
        return path.exists()

    def list_layers(self, path: Path) -> list[str]:
        return ["MapUnitPolys", "ContactsAndFaults"]

    def inspect(self, path: Path, layer: str | None = None) -> DatasetInspection:
        selected_layer = layer or "MapUnitPolys"
        return DatasetInspection(
            dataset_path=str(path.resolve()),
            dataset_name=selected_layer,
            backend_name=self.name,
            data_format="OpenFileGDB",
            file_size_bytes=2048,
            modified_date="2026-05-13T10:00:00",
            layer_names=["MapUnitPolys", "ContactsAndFaults"],
            selected_layer=selected_layer,
            layer_info=LayerInfo(
                name=selected_layer,
                data_kind="vector",
                geometry_type="Polygon",
                feature_count=42,
                fields=[
                    FieldInfo(name="MapUnit", field_type="string", alias="Map Unit", length=16, nullable=False),
                    FieldInfo(name="Label", field_type="string", length=24, nullable=True),
                ],
                spatial_reference=SpatialReferenceInfo(
                    name="NAD83 / UTM zone 10N",
                    epsg=26910,
                    wkt="PROJCS[...]",
                ),
                extent=ExtentInfo(west=-122.5, east=-122.2, south=38.6, north=39.0),
            ),
        )


def test_dataset_inspector_uses_matching_backend(tmp_path: Path) -> None:
    dataset_path = tmp_path / "example.gdb"
    dataset_path.mkdir()
    inspector = DatasetInspector(backends=[FakeBackend()])

    result = inspector.inspect(dataset_path, layer="MapUnitPolys")

    assert result.backend_name == "fake-backend"
    assert result.selected_layer == "MapUnitPolys"
    assert result.layer_info is not None
    assert result.layer_info.feature_count == 42


def test_dataset_inspector_raises_for_missing_dataset(tmp_path: Path) -> None:
    inspector = DatasetInspector(backends=[FakeBackend()])

    with pytest.raises(InspectionError):
        inspector.inspect(tmp_path / "missing.gdb")


def test_prefill_yaml_contains_auto_populated_and_todo_sections(tmp_path: Path) -> None:
    dataset_path = tmp_path / "example.gdb"
    dataset_path.mkdir()
    inspection = FakeBackend().inspect(dataset_path, layer="MapUnitPolys")

    document = build_prefill_document(inspection)
    output_path = write_prefill_yaml(document, tmp_path / "prefill.yaml")
    loaded = load_yaml_document(output_path)

    assert loaded["inspection"]["backend"] == "fake-backend"
    assert loaded["inspection"]["auto_populated"]["selected_layer"] == "MapUnitPolys"
    assert loaded["description"]["abstract"].startswith("TODO:")
    assert "USER INPUT NEEDED" in loaded["description"]["abstract"]
    assert loaded["entity_attribute_information"]["entities"][0]["attributes"][0]["alias"] == "Map Unit"
    assert "TODO:" not in loaded["entity_attribute_information"]["entities"][0]["attributes"][0]["definition"]
    assert "TODO:" not in loaded["entity_attribute_information"]["entities"][0]["attributes"][0]["definition_source"]
    assert loaded["spatial_domain"]["bounding_coordinates"]["west"] < -120
    assert loaded["spatial_reference"]["type"] == "utm"
    assert loaded["spatial_reference"]["utm"]["zone"] == "10"
    assert loaded["spatial_reference"]["utm"]["central_meridian"] == ""
    assert loaded["distribution"]["distributor"]["person"] == loaded["point_of_contact"]["person"]
    assert loaded["metadata"]["contact"]["person"] == loaded["point_of_contact"]["person"]


def test_gems_entity_attribute_document_omits_standard_gems_fields() -> None:
    inspection = DatasetInspection(
        dataset_path="/tmp/example.gdb",
        dataset_name="example",
        backend_name="fake-backend",
        data_format="OpenFileGDB",
        file_size_bytes=2048,
        modified_date="2026-05-13T10:00:00",
        layer_names=["MapUnitPolys"],
        selected_layer="MapUnitPolys",
        layer_info=LayerInfo(
            name="MapUnitPolys",
            data_kind="vector",
            geometry_type="Polygon",
            feature_count=42,
            fields=[
                FieldInfo(name="OBJECTID", field_type="OID"),
                FieldInfo(name="MapUnit", field_type="string"),
                FieldInfo(name="DataSourceID", field_type="string"),
                FieldInfo(name="ReviewerNotes", field_type="string"),
            ],
            spatial_reference=SpatialReferenceInfo(name="NAD83 / UTM zone 10N", epsg=26910, wkt="PROJCS[...]"),
            extent=ExtentInfo(west=-122.5, east=-122.2, south=38.6, north=39.0),
        ),
        layer_details=[],
    )

    document = build_prefill_document(inspection)
    entity = document["entity_attribute_information"]["entities"][0]

    assert document["entity_attribute_information"]["overview"]["description"].startswith("This geodatabase appears to follow GeMS")
    assert entity["definition_source"] == "GeMS"
    assert entity["omitted_standard_fields"] == ["MapUnit", "DataSourceID"]
    assert entity["omitted_esri_fields"] == ["OBJECTID"]
    assert [attribute["label"] for attribute in entity["attributes"]] == ["ReviewerNotes"]


def test_inspect_prefill_requires_manual_completion_before_build(tmp_path: Path) -> None:
    dataset_path = tmp_path / "example.gdb"
    dataset_path.mkdir()
    inspection = FakeBackend().inspect(dataset_path, layer="MapUnitPolys")
    output_path = write_prefill_yaml(build_prefill_document(inspection), tmp_path / "prefill.yaml")

    with pytest.raises(MissingRequiredFieldsError) as exc:
        load_metadata_config(output_path)

    assert "description.abstract" in str(exc.value)
    assert "citation.originators" in str(exc.value)


def test_prefill_document_for_raster_includes_raster_info(tmp_path: Path) -> None:
    inspection = DatasetInspection(
        dataset_path=str((tmp_path / "thermal.tif").resolve()),
        dataset_name="thermal",
        backend_name="fake-backend",
        data_format="GTiff",
        file_size_bytes=100,
        modified_date="2026-05-13T11:00:00",
        layer_names=["thermal"],
        selected_layer="thermal",
        layer_info=LayerInfo(
            name="thermal",
            data_kind="raster",
            spatial_reference=SpatialReferenceInfo(name="WGS 84", epsg=4326, wkt="GEOGCS[...]"),
            extent=ExtentInfo(west=-122.44, east=-122.42, south=39.03, north=39.04),
            raster=RasterInfo(width=100, height=200, band_count=1, cell_size_x=1.0, cell_size_y=1.0, nodata_values=[-9999]),
        ),
    )

    document = build_prefill_document(inspection)

    entity = document["entity_attribute_information"]["entities"][0]
    assert document["citation"]["geoform"] == "raster digital data"
    assert document["spatial_data_organization"]["direct_spatial_reference_method"] == "Raster"
    assert entity["raster"]["band_count"] == 1
    assert "USER INPUT NEEDED" in document["description"]["purpose"]
    assert "USER INPUT NEEDED" in document["data_quality"]["attribute_accuracy"]


@pytest.mark.skipif(importlib.util.find_spec("pyogrio") is None, reason="pyogrio not installed")
def test_open_source_backend_reads_sample_shapefile() -> None:
    backend = OpenSourceBackend()

    result = backend.inspect(Path("examples/sample_data/GeMS_shapefiles/ContactsAndFaults.shp"))

    assert result.backend_name == "open-source"
    assert result.layer_info is not None
    assert result.layer_info.name == "ContactsAndFaults"
    assert result.layer_info.feature_count == 2005
    assert [field.name for field in result.layer_info.fields] == ["OBJECTID", "Type", "Concealed", "Symbol", "Label"]
    assert result.layer_info.spatial_reference is not None
    assert result.layer_info.spatial_reference.epsg == 26910


@pytest.mark.skipif(importlib.util.find_spec("pyogrio") is None, reason="pyogrio not installed")
def test_open_source_backend_reads_sample_geodatabase() -> None:
    backend = OpenSourceBackend()

    result = backend.inspect(Path("examples/sample_data/sim3514.gdb"), layer="MapUnitPolys")

    assert result.layer_info is not None
    assert result.data_format == "OpenFileGDB"
    assert "MapUnitPolys" in result.layer_names
    assert len(result.layer_details) >= 10
    map_unit_polys = next(layer for layer in result.layer_details if layer.name == "MapUnitPolys")
    assert map_unit_polys.feature_count == 1089
    assert any(field.name == "MapUnit" for field in map_unit_polys.fields)


def test_arcpy_backend_lists_nested_feature_dataset_layers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset_path = tmp_path / "example.gdb"
    dataset_path.mkdir()

    fake_arcpy = SimpleNamespace(
        env=SimpleNamespace(workspace=None),
        ListFeatureClasses=lambda feature_dataset=None: ["MapUnitPolys"] if feature_dataset == "GeologicMap" else [],
        ListDatasets=lambda feature_type=None: ["GeologicMap"] if feature_type == "feature" else [],
        ListTables=lambda: [],
        ListRasters=lambda: [],
    )
    monkeypatch.setitem(sys.modules, "arcpy", fake_arcpy)

    backend = ArcPyBackend()

    assert backend.list_layers(dataset_path) == ["GeologicMap/MapUnitPolys"]


def test_arcpy_backend_inspects_layer_inside_feature_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset_path = tmp_path / "example.gdb"
    dataset_path.mkdir()

    described_targets: list[str] = []

    class FakeField:
        def __init__(self, name: str, field_type: str) -> None:
            self.name = name
            self.type = field_type
            self.aliasName = name
            self.length = 0
            self.isNullable = True

    class FakeSpatialReference:
        name = "NAD83 / UTM zone 10N"
        factoryCode = 26910
        datumName = "D_North_American_1983"
        linearUnitName = "Meter"
        angularUnitName = None

        def exportToString(self) -> str:
            return "PROJCS[...]"

    class FakeDescribe:
        dataType = "FeatureClass"
        shapeType = "Polygon"
        bandCount = None
        extent = SimpleNamespace(XMin=1.0, XMax=2.0, YMin=3.0, YMax=4.0)
        spatialReference = FakeSpatialReference()

    def describe(target: str) -> FakeDescribe:
        described_targets.append(target)
        return FakeDescribe()

    fake_arcpy = SimpleNamespace(
        env=SimpleNamespace(workspace=None),
        ListFeatureClasses=lambda feature_dataset=None: ["MapUnitPolys"] if feature_dataset == "GeologicMap" else [],
        ListDatasets=lambda feature_type=None: ["GeologicMap"] if feature_type == "feature" else [],
        ListTables=lambda: [],
        ListRasters=lambda: [],
        Describe=describe,
        ListFields=lambda target: [FakeField("MapUnit", "String")],
        management=SimpleNamespace(GetCount=lambda target: ["42"]),
    )
    monkeypatch.setitem(sys.modules, "arcpy", fake_arcpy)

    backend = ArcPyBackend()
    result = backend.inspect(dataset_path, layer="MapUnitPolys")

    assert result.selected_layer == "GeologicMap/MapUnitPolys"
    assert described_targets == [str(dataset_path / "GeologicMap/MapUnitPolys")]


def test_arcpy_backend_inspects_all_layers_inside_feature_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset_path = tmp_path / "example.gdb"
    dataset_path.mkdir()

    class FakeField:
        def __init__(self, name: str, field_type: str) -> None:
            self.name = name
            self.type = field_type
            self.aliasName = name
            self.length = 0
            self.isNullable = True

    class FakeSpatialReference:
        name = "NAD83 / UTM zone 10N"
        factoryCode = 26910
        datumName = "D_North_American_1983"
        linearUnitName = "Meter"
        angularUnitName = None

        def exportToString(self) -> str:
            return "PROJCS[...]"

    class FakeDescribe:
        dataType = "FeatureClass"
        shapeType = "Polygon"
        bandCount = None
        extent = SimpleNamespace(XMin=1.0, XMax=2.0, YMin=3.0, YMax=4.0)
        spatialReference = FakeSpatialReference()

    fake_arcpy = SimpleNamespace(
        env=SimpleNamespace(workspace=None),
        ListFeatureClasses=lambda feature_dataset=None: ["MapUnitPolys", "ContactsAndFaults"] if feature_dataset == "GeologicMap" else [],
        ListDatasets=lambda feature_type=None: ["GeologicMap"] if feature_type == "feature" else [],
        ListTables=lambda: [],
        ListRasters=lambda: [],
        Describe=lambda target: FakeDescribe(),
        ListFields=lambda target: [FakeField("MapUnit", "String")],
        management=SimpleNamespace(GetCount=lambda target: ["42"]),
    )
    monkeypatch.setitem(sys.modules, "arcpy", fake_arcpy)

    backend = ArcPyBackend()
    result = backend.inspect(dataset_path, all_layers=True)

    assert result.dataset_name == "example"
    assert result.selected_layer is None
    assert result.layer_info is None
    assert result.layer_names == ["GeologicMap/MapUnitPolys", "GeologicMap/ContactsAndFaults"]
    assert [layer.name for layer in result.layer_details] == ["GeologicMap/MapUnitPolys", "GeologicMap/ContactsAndFaults"]


def test_prefill_document_for_all_layers_uses_all_entities(tmp_path: Path) -> None:
    dataset_path = tmp_path / "example.gdb"
    dataset_path.mkdir()
    inspection = DatasetInspection(
        dataset_path=str(dataset_path.resolve()),
        dataset_name="example",
        backend_name="fake-backend",
        data_format="OpenFileGDB",
        file_size_bytes=2048,
        modified_date="2026-05-13T10:00:00",
        layer_names=["MapUnitPolys", "ContactsAndFaults"],
        selected_layer=None,
        layer_info=None,
        layer_details=[
            LayerInfo(
                name="MapUnitPolys",
                data_kind="vector",
                geometry_type="Polygon",
                feature_count=42,
                fields=[FieldInfo(name="MapUnit", field_type="string")],
                spatial_reference=SpatialReferenceInfo(name="NAD83 / UTM zone 10N", epsg=26910, wkt="PROJCS[...]"),
                extent=ExtentInfo(west=-122.5, east=-122.2, south=38.6, north=39.0),
            ),
            LayerInfo(
                name="ContactsAndFaults",
                data_kind="vector",
                geometry_type="Line",
                feature_count=88,
                fields=[FieldInfo(name="Type", field_type="string")],
                spatial_reference=SpatialReferenceInfo(name="NAD83 / UTM zone 10N", epsg=26910, wkt="PROJCS[...]"),
                extent=ExtentInfo(west=-122.4, east=-122.1, south=38.5, north=39.1),
            ),
        ],
    )

    document = build_prefill_document(inspection)

    assert document["dataset"]["selected_layer"] is None
    assert document["citation"]["title"] == "example"
    assert len(document["entity_attribute_information"]["entities"]) == 2
    assert document["entity_attribute_information"]["entities"][0]["name"] == "MapUnitPolys"
    assert document["entity_attribute_information"]["entities"][1]["name"] == "ContactsAndFaults"
