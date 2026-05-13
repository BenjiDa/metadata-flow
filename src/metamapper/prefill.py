from __future__ import annotations

from datetime import datetime
import math
import os
from pathlib import Path
import re
from typing import Any

import yaml

from metamapper.inspection_types import DatasetInspection, LayerInfo


TODO_ABSTRACT = "TODO: user must provide abstract"
TODO_PURPOSE = "TODO: user must provide purpose"
TODO_SUPPL = "TODO: describe geologic interpretation, processing notes, and supplemental information"
TODO_LINEAGE = "TODO: describe lineage and processing steps"
TODO_ATTR_DEF = "TODO: define this attribute beyond the raw field name and type"
TODO_USE_LIMIT = "TODO: describe use constraints and data limitations"
TODO_PUB_DATE = "TODO: set publication or release date"
TODO_ORIGINATOR = "TODO: add originator/author name"
TODO_PROGRESS = "TODO: set publication status progress"
TODO_UPDATE = "TODO: set update frequency or maintenance plan"
TODO_PUBLISHER = "TODO: provide publisher or publishing organization"
TODO_CONTACT = "TODO: provide metadata contact"
TODO_DISTRIBUTION = "TODO: provide distribution liability statement"
TODO_CURRENTNESS = "TODO: set currentness reference, for example 'publication date' or 'observed'"


def build_prefill_document(inspection: DatasetInspection) -> dict[str, Any]:
    """Build an editable YAML-ready document from an inspection result."""

    layer_info = _preferred_layer_info(inspection)
    coordinates = _bounding_coordinates(layer_info)
    spatial_reference = _spatial_reference_document(layer_info)
    entity_info = _entity_attribute_document(inspection)
    direct_method = "Raster" if layer_info and layer_info.data_kind == "raster" else "Vector"
    geoform = _infer_geoform(inspection, layer_info)

    doc: dict[str, Any] = {
        "inspection": {
            "generated_at": datetime.now().date().isoformat(),
            "backend": inspection.backend_name,
            "auto_populated": inspection.to_dict(),
            "user_required_fields": [
                "citation.originators",
                "citation.publication_date",
                "citation.publication_status.progress",
                "citation.publication_status.update",
                "citation.publication_info.publisher",
                "description.abstract",
                "description.purpose",
                "description.supplemental_information",
                "time_period.current",
                "data_quality.attribute_accuracy",
                "data_quality.logical_consistency",
                "data_quality.completeness",
                "data_quality.lineage.process_steps",
                "constraints.use_limitations",
                "point_of_contact",
                "distribution.liability",
            ],
        },
        "citation": {
            "title": inspection.dataset_name.replace("_", " "),
            "originators": [TODO_ORIGINATOR],
            "publication_date": TODO_PUB_DATE,
            "publication_status": {
                "progress": TODO_PROGRESS,
                "update": TODO_UPDATE,
            },
            "geoform": geoform,
            "publication_info": {
                "place": "TODO: provide publication place",
                "publisher": TODO_PUBLISHER,
            },
            "online_links": [],
        },
        "description": {
            "abstract": TODO_ABSTRACT,
            "purpose": TODO_PURPOSE,
            "supplemental_information": TODO_SUPPL,
        },
        "time_period": {
            "current": TODO_CURRENTNESS,
        },
        "spatial_domain": {
            "bounding_coordinates": coordinates,
        },
        "keywords": {
            "theme_keywords": [
                {
                    "thesaurus": "None",
                    "keywords": [
                        inspection.data_format,
                        inspection.dataset_name,
                    ],
                }
            ],
            "place_keywords": {
                "thesaurus": "None",
                "keywords": [],
            },
            "general_keywords": [],
        },
        "constraints": {
            "access_constraints": "None.",
            "use_limitations": TODO_USE_LIMIT,
        },
        "point_of_contact": {
            "person": TODO_CONTACT,
            "organization": "TODO: provide organization",
            "position": "TODO: provide position or role",
            "address_type": "mailing",
            "address": "TODO: provide mailing address",
            "city": "TODO: provide city",
            "state": "TODO: provide state or province",
            "postal": "TODO: provide postal code",
            "country": "TODO: provide country",
            "phone": "TODO: provide phone number",
            "email": "TODO: provide email address",
        },
        "data_quality": {
            "attribute_accuracy": "TODO: describe attribute accuracy and limitations",
            "logical_consistency": "TODO: describe logical consistency checks",
            "completeness": "TODO: describe dataset completeness",
            "lineage": {
                "process_steps": [
                    {
                        "description": TODO_LINEAGE,
                        "date": datetime.now().strftime("%Y"),
                    }
                ]
            },
        },
        "spatial_reference": spatial_reference,
        "spatial_data_organization": {
            "direct_spatial_reference_method": direct_method,
        },
        "entity_attribute_information": entity_info,
        "distribution": {
            "distributor": {
                "organization": "TODO: provide distributor organization",
                "person": "TODO: provide distributor contact",
                "address_type": "mailing",
                "address": "TODO: provide distributor address",
                "city": "TODO: provide city",
                "state": "TODO: provide state or province",
                "postal": "TODO: provide postal code",
                "country": "TODO: provide country",
                "phone": "TODO: provide phone number",
                "email": "TODO: provide email address",
            },
            "liability": TODO_DISTRIBUTION,
            "online_resource": "",
            "fees": "None.",
        },
        "metadata": {
            "date": datetime.now().strftime("%Y%m%d"),
            "contact": {
                "person": "TODO: provide metadata contact",
                "organization": "TODO: provide metadata contact organization",
                "address_type": "mailing",
                "address": "TODO: provide mailing address",
                "city": "TODO: provide city",
                "state": "TODO: provide state or province",
                "postal": "TODO: provide postal code",
                "phone": "TODO: provide phone number",
                "email": "TODO: provide email address",
            },
            "standard_name": "FGDC Content Standard for Digital Geospatial Metadata",
            "standard_version": "FGDC-STD-001-1998",
        },
        "validation": {
            "external_command": None,
            "report_path": None,
        },
    }

    if layer_info and layer_info.data_kind == "vector":
        doc["time_period"]["begin_date"] = "TODO: set begin date if applicable"
        doc["time_period"]["end_date"] = "TODO: set end date if applicable"
    else:
        doc["time_period"]["single_date"] = "TODO: set observation or acquisition date"

    if inspection.warnings:
        doc["inspection"]["warnings"] = list(inspection.warnings)

    if inspection.layer_names:
        doc["dataset"] = {
            "name": inspection.dataset_name,
            "path": inspection.dataset_path,
            "format": inspection.data_format,
            "layers": inspection.layer_names,
            "selected_layer": inspection.selected_layer,
            "file_size_bytes": inspection.file_size_bytes,
            "modified_date": inspection.modified_date,
        }

    return doc


def write_prefill_yaml(document: dict[str, Any], output_path: str | Path) -> Path:
    """Write the prefill document as editable YAML."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=False, default_flow_style=False)
    return path


def _infer_geoform(inspection: DatasetInspection, layer_info: LayerInfo | None) -> str:
    if layer_info and layer_info.data_kind == "raster":
        return "raster digital data"
    if inspection.data_format.lower() in {"csv", "xlsx", "xls"}:
        return "spreadsheet"
    return "vector digital data"


def _bounding_coordinates(layer_info: LayerInfo | None) -> dict[str, float | str | None]:
    if not layer_info or not layer_info.extent:
        return {
            "west": "TODO: provide west bounding coordinate",
            "east": "TODO: provide east bounding coordinate",
            "north": "TODO: provide north bounding coordinate",
            "south": "TODO: provide south bounding coordinate",
        }

    transformed = _transform_extent_to_geographic(layer_info)
    if transformed is not None:
        return transformed
    return {
        "west": layer_info.extent.west,
        "east": layer_info.extent.east,
        "north": layer_info.extent.north,
        "south": layer_info.extent.south,
    }


def _spatial_reference_document(layer_info: LayerInfo | None) -> dict[str, Any]:
    spatial_reference = layer_info.spatial_reference if layer_info else None
    is_utm = _looks_like_utm(spatial_reference.name if spatial_reference else None, spatial_reference.epsg if spatial_reference else None)
    data: dict[str, Any]
    if is_utm:
        data = {
            "type": "utm",
            "utm": {
                "zone": _infer_utm_zone(spatial_reference.name if spatial_reference else None, spatial_reference.epsg if spatial_reference else None),
                "scale_factor": "0.9996",
                "central_meridian": "TODO: confirm central meridian",
                "latitude_projection_origin": "0.0",
                "false_easting": "500000.0",
                "false_northing": "0.0",
                "x_resolution": "TODO: confirm x resolution",
                "y_resolution": "TODO: confirm y resolution",
                "unit": spatial_reference.unit if spatial_reference and spatial_reference.unit else "meters",
            },
            "geodetic": {
                "datum": spatial_reference.name if spatial_reference and spatial_reference.name else "TODO: provide geodetic datum",
                "ellipsoid": "TODO: provide ellipsoid",
                "semi_major_axis": "TODO: provide semi-major axis",
                "denominator_of_flattening": "TODO: provide denominator of flattening",
            },
        }
    else:
        data = {
            "type": "geographic",
            "geographic": {
                "latitude_resolution": "TODO: confirm latitude resolution",
                "longitude_resolution": "TODO: confirm longitude resolution",
                "unit": spatial_reference.unit if spatial_reference and spatial_reference.unit else "Decimal degrees",
            },
            "geodetic": {
                "datum": spatial_reference.name if spatial_reference and spatial_reference.name else "TODO: provide geodetic datum",
                "ellipsoid": "TODO: provide ellipsoid",
                "semi_major_axis": "TODO: provide semi-major axis",
                "denominator_of_flattening": "TODO: provide denominator of flattening",
            },
        }

    if spatial_reference:
        data["source_wkt"] = spatial_reference.wkt
        data["epsg"] = spatial_reference.epsg
        if spatial_reference.datum:
            data["geodetic"]["datum"] = spatial_reference.datum

    if not is_utm and layer_info and layer_info.raster and layer_info.raster.cell_size_x is not None:
        data["geographic"]["longitude_resolution"] = str(layer_info.raster.cell_size_x)
    if not is_utm and layer_info and layer_info.raster and layer_info.raster.cell_size_y is not None:
        data["geographic"]["latitude_resolution"] = str(layer_info.raster.cell_size_y)
    return data


def _entity_attribute_document(inspection: DatasetInspection) -> dict[str, Any]:
    layer_infos = inspection.layer_details or ([inspection.layer_info] if inspection.layer_info else [])
    if not layer_infos:
        return {"entities": []}

    entities: list[dict[str, Any]] = []
    for layer_info in layer_infos:
        entity: dict[str, Any] = {
            "name": layer_info.name,
            "description": f"Auto-generated draft entity description for {layer_info.name}.",
            "definition_source": "MetaMapper inspection",
            "data_kind": layer_info.data_kind,
            "geometry_type": layer_info.geometry_type,
            "feature_count": layer_info.feature_count,
            "attributes": [],
        }

        for field in layer_info.fields:
            attribute: dict[str, Any] = {
                "label": field.name,
                "definition": TODO_ATTR_DEF,
                "definition_source": "TODO: provide attribute definition source",
                "unrepresentable_domain": f"Raw field type: {field.field_type}",
            }
            if field.alias:
                attribute["alias"] = field.alias
            if field.length is not None:
                attribute["length"] = field.length
            if field.nullable is not None:
                attribute["nullable"] = field.nullable
            entity["attributes"].append(attribute)

        if layer_info.spatial_reference:
            entity["spatial_reference"] = layer_info.spatial_reference.to_dict()
        if layer_info.extent:
            entity["extent"] = layer_info.extent.to_dict()
        if layer_info.raster:
            entity["raster"] = layer_info.raster.to_dict()
        entities.append(entity)

    return {"entities": entities}


def _looks_like_utm(name: str | None, epsg: int | None) -> bool:
    if name and "utm" in name.lower():
        return True
    if epsg is None:
        return False
    return 26700 < epsg < 32761


def _infer_utm_zone(name: str | None, epsg: int | None) -> str:
    if name:
        match = re.search(r"zone\s+(\d+)", name, re.IGNORECASE)
        if match:
            return match.group(1)
    if epsg is not None:
        if 32601 <= epsg <= 32660:
            return str(epsg - 32600)
        if 32701 <= epsg <= 32760:
            return str(epsg - 32700)
        if 26901 <= epsg <= 26923:
            return str(epsg - 26900)
    return "TODO: confirm UTM zone"


def _transform_extent_to_geographic(layer_info: LayerInfo) -> dict[str, float] | None:
    if layer_info.extent is None or layer_info.spatial_reference is None:
        return None
    crs_hint = (
        f"EPSG:{layer_info.spatial_reference.epsg}"
        if layer_info.spatial_reference.epsg is not None
        else layer_info.spatial_reference.wkt or layer_info.spatial_reference.name
    )
    if crs_hint is None:
        return None
    try:
        from pyproj import Transformer

        os.environ.setdefault("PROJ_NETWORK", "OFF")

        west, south, east, north = _transform_bounds_with_fallback(
            crs_hint,
            layer_info.extent.west,
            layer_info.extent.south,
            layer_info.extent.east,
            layer_info.extent.north,
        )
        values = [west, east, north, south]
        if not all(math.isfinite(value) for value in values):
            return None
        return {
            "west": float(west),
            "east": float(east),
            "north": float(north),
            "south": float(south),
        }
    except Exception:
        return None


def _preferred_layer_info(inspection: DatasetInspection) -> LayerInfo | None:
    if inspection.layer_info is not None:
        return inspection.layer_info
    if not inspection.layer_details:
        return None

    layers_with_extent = [layer for layer in inspection.layer_details if layer.extent is not None]
    if not layers_with_extent:
        return inspection.layer_details[0]

    first = layers_with_extent[0]
    west = min(layer.extent.west for layer in layers_with_extent if layer.extent is not None)
    east = max(layer.extent.east for layer in layers_with_extent if layer.extent is not None)
    south = min(layer.extent.south for layer in layers_with_extent if layer.extent is not None)
    north = max(layer.extent.north for layer in layers_with_extent if layer.extent is not None)

    return LayerInfo(
        name=inspection.dataset_name,
        data_kind=first.data_kind,
        geometry_type=first.geometry_type,
        feature_count=sum(layer.feature_count or 0 for layer in layers_with_extent),
        fields=[],
        spatial_reference=first.spatial_reference,
        extent=type(first.extent)(west=west, east=east, south=south, north=north) if first.extent else None,
        raster=first.raster,
    )


def _transform_bounds_with_fallback(
    source_crs: str,
    west: float,
    south: float,
    east: float,
    north: float,
) -> tuple[float, float, float, float]:
    from pyproj import Transformer

    candidate_targets = ["EPSG:4326", "EPSG:4269"]
    for target_crs in candidate_targets:
        transformer = Transformer.from_crs(
            source_crs,
            target_crs,
            always_xy=True,
            allow_ballpark=True,
            only_best=False,
        )
        west_ll, south_ll = transformer.transform(west, south)
        east_ll, north_ll = transformer.transform(east, north)
        values = [west_ll, south_ll, east_ll, north_ll]
        if all(math.isfinite(value) for value in values):
            return west_ll, south_ll, east_ll, north_ll
    raise ValueError(f"Could not transform extent from {source_crs} to a geographic CRS.")
