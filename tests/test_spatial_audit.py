from pathlib import Path
import csv

import pytest

from metamapper.inspection_types import DatasetInspection, ExtentInfo, LayerInfo, SpatialReferenceInfo
from metamapper.prefill import build_prefill_document


def test_mixed_crs_extents_are_transformed_before_union():
    pytest.importorskip('pyproj')
    layers = [
        LayerInfo('MapUnitPolys', 'vector', feature_count=1,
                  spatial_reference=SpatialReferenceInfo(epsg=26910),
                  extent=ExtentInfo(west=500000, east=580000, south=4261300, north=4317000)),
        LayerInfo('gravity_gradients', 'vector', feature_count=1,
                  spatial_reference=SpatialReferenceInfo(epsg=4326),
                  extent=ExtentInfo(west=-123.01, east=-121.98, south=38.49, north=39.01)),
        LayerInfo('CSAMapUnitPolys', 'vector', feature_count=1,
                  spatial_reference=SpatialReferenceInfo(epsg=26910),
                  extent=ExtentInfo(west=0, east=100000, south=-8000, north=1000)),
        LayerInfo('CMUPolys', 'vector', feature_count=1,
                  spatial_reference=SpatialReferenceInfo(epsg=26910),
                  extent=ExtentInfo(west=544000, east=570000, south=4325000, north=4330000)),
        LayerInfo('Empty', 'vector', feature_count=0,
                  spatial_reference=SpatialReferenceInfo(epsg=26910),
                  extent=ExtentInfo(west=0, east=0, south=0, north=0)),
    ]
    inspection = DatasetInspection('test.gdb','test','test','FileGDB',0,None,
                                   layer_names=[l.name for l in layers],layer_details=layers)
    document = build_prefill_document(inspection)
    bounds = document['spatial_domain']['bounding_coordinates']
    assert bounds['west'] == pytest.approx(-123.01)
    assert bounds['east'] == pytest.approx(-121.98)
    assert bounds['south'] == pytest.approx(38.49)
    assert bounds['north'] == pytest.approx(39.01)
    assert document['spatial_reference']['type'] == 'utm'


def test_boundary_audit_retains_original_ids_and_separates_diagrams(tmp_path: Path):
    geopandas = pytest.importorskip('geopandas')
    pyogrio = pytest.importorskip('pyogrio')
    from shapely.geometry import Point
    from metamapper.spatial_audit import audit_bounds
    path = tmp_path/'example.gpkg'
    data = geopandas.GeoDataFrame({'MapUnitPolys_ID':['inside','outside','missing']},
                                 geometry=[Point(-122.5,38.75), Point(-123.02,38.75), None], crs=4269)
    pyogrio.write_dataframe(data,path,layer='MapUnitPolys')
    diagram = geopandas.GeoDataFrame({'label':['diagram']},geometry=[Point(0,0)],crs=26910)
    pyogrio.write_dataframe(diagram,path,layer='CSAMapUnitPolys')
    summary = audit_bounds(path,(-123,38.5,-122,39),tmp_path/'audit')
    rows = list(csv.DictReader((tmp_path/'audit/outside_features.csv').open()))
    assert len(rows) == 1
    assert rows[0]['objectid'] == '2'
    assert rows[0]['wholly_outside'] == 'True'
    assert float(rows[0]['max_vertex_distance_m']) > 1000
    assert 'outside' in rows[0]['identifiers']
    assert summary['layers'][0]['null_or_empty_count'] == 1
    assert summary['layers'][1]['audit_status'] == 'non-geographic diagram'


def test_missing_crs_never_emits_projected_meters_as_longitude():
    layer = LayerInfo('Unknown','vector',feature_count=1,extent=ExtentInfo(500000,600000,4200000,4300000))
    inspection = DatasetInspection('x','x','test','FileGDB',0,None,layer_info=layer)
    bounds = build_prefill_document(inspection)['spatial_domain']['bounding_coordinates']
    assert all(str(value).startswith('TODO:') for value in bounds.values())
