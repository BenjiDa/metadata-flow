"""Read-only boundary checks with original feature IDs and explicit layer roles."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path


def layer_role(name: str) -> str:
    short = name.replace("\\", "/").split("/")[-1].lower()
    if short.startswith("t_"):
        return "topology diagnostics"
    if short.startswith("csa") or short.startswith("crosssection"):
        return "cross-section diagram"
    if short.startswith("cmu"):
        return "correlation diagram"
    if "anno" in short:
        return "annotation"
    if "gradient" in short or short.startswith("contour_"):
        return "regional geophysics"
    return "map data"


def audit_bounds(dataset_path: str | Path, bounds: tuple[float, float, float, float],
                 output_dir: str | Path, tolerance_m: float = 25.0) -> dict:
    """Check every geographic geometry; never edit or clip the source.

    Bounds are west, south, east, north in EPSG:4269 (NAD83).
    Diagram coordinates are intentionally not interpreted as Earth locations.
    Tolerance only classifies severity; all strictly outside features are listed.
    """
    import numpy as np
    import pyogrio
    import shapely
    from pyproj import CRS, Transformer
    from shapely.ops import transform

    west, south, east, north = bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Expected valid west, south, east, north geographic bounds.")
    if tolerance_m < 0:
        raise ValueError("Tolerance must be nonnegative.")
    boundary = shapely.box(west, south, east, north)
    # Local azimuthal equidistant coordinates give useful metric distances.
    metric = CRS.from_proj4(f"+proj=aeqd +lat_0={(south+north)/2} +lon_0={(west+east)/2} +datum=NAD83 +units=m")
    to_metric = Transformer.from_crs(4269, metric, always_xy=True).transform
    # Densify edges so metric distances are to the quadrangle, not its corners.
    metric_boundary = transform(to_metric, shapely.segmentize(boundary, 0.001))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summaries, records, markers, geometry_issues = [], [], [], []
    to_wgs84 = Transformer.from_crs(4269, 4326, always_xy=True)
    for name, geom_type in pyogrio.list_layers(dataset_path):
        role = layer_role(str(name))
        info = pyogrio.read_info(dataset_path, layer=name)
        row = dict(layer=str(name), role=role, record_count=int(info['features']),
                   outside_count=0, beyond_tolerance_count=0, null_or_empty_count=0,
                   invalid_count=0, geographic_bounds=None)
        if geom_type is None or role in {"cross-section diagram", "correlation diagram"}:
            row['audit_status'] = 'non-geographic diagram' if geom_type else 'nonspatial table'
            summaries.append(row)
            continue
        if not info.get('crs'):
            row['audit_status'] = 'missing CRS; not transformed'
            summaries.append(row)
            continue
        frame = pyogrio.read_dataframe(dataset_path, layer=name, fid_as_index=True)
        transformer = Transformer.from_crs(frame.crs, 4269, always_xy=True)
        observed = []
        for fid, feature in frame.iterrows():
            geom = feature.geometry
            if not isinstance(geom, shapely.Geometry) or geom.is_empty:
                row['null_or_empty_count'] += 1
                geometry_issues.append(dict(layer=str(name), role=role, objectid=int(fid), issue='null or empty geometry'))
                continue
            if not geom.is_valid:
                row['invalid_count'] += 1
                geometry_issues.append(dict(layer=str(name), role=role, objectid=int(fid), issue=shapely.is_valid_reason(geom)))
            geo = transform(transformer.transform, geom)
            if not all(math.isfinite(x) for x in geo.bounds):
                raise ValueError(f"Nonfinite transformed geometry: {name}, FID {fid}")
            observed.append(geo.bounds)
            if boundary.covers(geo):
                continue
            row['outside_count'] += 1
            coords = shapely.get_coordinates(geo)
            x, y = to_metric(coords[:, 0], coords[:, 1])
            distances = shapely.distance(shapely.points(x, y), metric_boundary)
            distance = float(np.max(distances))
            severity = 'beyond tolerance' if distance > tolerance_m else 'edge tolerance'
            row['beyond_tolerance_count'] += int(distance > tolerance_m)
            wholly = geo.disjoint(boundary)
            ids = {k: str(v) for k, v in feature.items() if k.lower().endswith('_id') and v is not None}
            item = dict(layer=str(name), role=role, objectid=int(fid), classification=severity,
                        wholly_outside=wholly, max_vertex_distance_m=round(distance, 3),
                        west=geo.bounds[0], south=geo.bounds[1], east=geo.bounds[2], north=geo.bounds[3],
                        type=str(feature.get('Type', '')), map_unit=str(feature.get('MapUnit', '')),
                        identifiers=json.dumps(ids, sort_keys=True))
            records.append(item)
            # Locate the worst offending vertex, not a centroid inside a long line.
            worst = coords[int(np.argmax(distances))]
            markers.append(dict(type='Feature', geometry=dict(type='Point', coordinates=list(to_wgs84.transform(*worst[:2]))), properties=item))
        if observed:
            row['geographic_bounds'] = [min(b[0] for b in observed), min(b[1] for b in observed),
                                        max(b[2] for b in observed), max(b[3] for b in observed)]
        row['audit_status'] = 'checked'
        summaries.append(row)
    records.sort(key=lambda r: (-r['max_vertex_distance_m'], r['layer'], r['objectid']))
    summary = dict(dataset=str(Path(dataset_path).resolve()), boundary_crs='EPSG:4269',
                   bounds=dict(west=west, south=south, east=east, north=north), tolerance_m=tolerance_m,
                   distance_method='maximum distance of transformed geometry vertices to densified quadrangle boundary',
                   layers=summaries, outside_feature_count=len(records))
    (output/'boundary_audit.json').write_text(json.dumps(summary, indent=2)+'\n')
    fields = ['layer','role','objectid','classification','wholly_outside','max_vertex_distance_m',
              'west','south','east','north','type','map_unit','identifiers']
    with (output/'outside_features.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    with (output/'main_map_outside_features.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(record for record in records if record['role'] == 'map data')
    (output/'outside_feature_locations.geojson').write_text(json.dumps(dict(type='FeatureCollection', features=markers)))
    with (output/'geometry_issues.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['layer','role','objectid','issue'])
        writer.writeheader()
        writer.writerows(geometry_issues)
    return summary
