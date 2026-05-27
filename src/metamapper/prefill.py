from __future__ import annotations

from datetime import datetime
from copy import deepcopy
import math
import os
from pathlib import Path
import re
from typing import Any

import yaml

from metamapper.inspection_types import DatasetInspection, LayerInfo


TODO_ABSTRACT = "TODO: USER INPUT NEEDED. REVISE THIS ABSTRACT."
TODO_PURPOSE = "TODO: USER INPUT NEEDED. REVISE THIS PURPOSE STATEMENT."
TODO_SUPPL = "TODO: USER INPUT NEEDED. ADD GEOLOGIC INTERPRETATION, PROCESSING NOTES, AND SUPPLEMENTAL INFORMATION."
TODO_LINEAGE = "TODO: USER INPUT NEEDED. DESCRIBE LINEAGE AND PROCESSING STEPS."
TODO_USE_LIMIT = "TODO: USER INPUT NEEDED. REVISE USE CONSTRAINTS AND DATA LIMITATIONS."
TODO_PUB_DATE = "TODO: set publication or release date"
TODO_ORIGINATOR = "TODO: add originator/author name"
TODO_PROGRESS = "TODO: set publication status progress"
TODO_UPDATE = "TODO: set update frequency or maintenance plan"
TODO_PUBLISHER = "TODO: provide publisher or publishing organization"
TODO_CONTACT = "TODO: provide metadata contact"
TODO_DISTRIBUTION = "TODO: provide distribution liability statement"
TODO_CURRENTNESS = "TODO: set currentness reference, for example 'publication date' or 'observed'"

ESRI_STANDARD_FIELD_DEFINITIONS: dict[str, str] = {
    "OBJECTID": "Internal feature number.",
    "FID": "Internal feature number.",
    "Shape": "Internal geometry object.",
    "Shape_Length": "Internal feature length.",
    "Shape_Area": "Internal feature area.",
    "GlobalID": "Globally unique identifier maintained by the geodatabase.",
}

GEMS_STANDARD_FIELD_DEFINITIONS: dict[str, str] = {
    "MapUnit": "Short plain-text identifier of the map unit. Foreign key to DescriptionOfMapUnits table.",
    "Type": "Classifier that specifies what kind of geologic feature is represented by a database element.",
    "IdentityConfidence": "Confidence that feature is correctly identified.",
    "ExistenceConfidence": "Confidence that feature exists.",
    "LocationConfidenceMeters": "Estimated half-width in meters of positional uncertainty envelope; position is relative to other features in database.",
    "OrientationConfidenceDegrees": "Estimated angular precision of combined azimuth and inclination measurements, in degrees.",
    "PlotAtScale": "Scale denominator at which the feature should be plotted or larger.",
    "Label": "Plain-text equivalent of the desired annotation for a feature.",
    "Symbol": "Reference to the cartographic symbol used to denote the feature.",
    "DataSourceID": "Source of data; foreign key to table DataSources.",
    "LocationSourceID": "Source of location; foreign key to table DataSources.",
    "OrientationSourceID": "Source of orientation data; foreign key to table DataSources.",
    "Notes": "Additional information specific to a particular feature or table entry.",
    "GeoMaterial": "Classifier of the material that composes the map unit.",
    "GeoMaterialConfidence": "Confidence in assignment of geomaterial classification.",
    "IsConcealed": "Flag for contacts and faults covered by overlying map unit.",
}

GEMS_ENTITY_DESCRIPTIONS: dict[str, str] = {
    "MapUnitPolys": "Polygons that record the distribution of map units on the map horizon.",
    "ContactsAndFaults": "Lines that represent contacts, faults, and shoreline boundaries that participate in map-unit topology.",
    "GeologicLines": "Lines that represent linear geologic features that do not participate in map-unit topology.",
    "MapUnitPoints": "Points that record the distribution of map units of point-like extent on the map horizon.",
    "DescriptionOfMapUnits": "Table that stores names, ages, symbols, and descriptions of map units shown on the map.",
    "DataSources": "Table that identifies sources referenced by geologic features and observations in the dataset.",
    "Glossary": "Table that defines terminology used within the geodatabase.",
    "GenericPoints": "Points that represent miscellaneous point features that do not fit other GeMS point feature classes.",
    "GenericSamples": "Sample locations and related sample identifiers.",
    "OrientationPoints": "Points that store planar and linear orientation measurements.",
    "Stations": "Observation stations used to locate map observations and supporting data.",
    "GeochronPoints": "Points that represent geochronology sample localities and ages.",
}


def _contact_template(person_placeholder: str = TODO_CONTACT, organization_placeholder: str = "TODO: provide organization") -> dict[str, str]:
    return {
        "person": person_placeholder,
        "organization": organization_placeholder,
        "position": "TODO: provide position or role",
        "address_type": "mailing",
        "address": "TODO: provide mailing address",
        "city": "TODO: provide city",
        "state": "TODO: provide state or province",
        "postal": "TODO: provide postal code",
        "country": "TODO: provide country",
        "phone": "TODO: provide phone number",
        "email": "TODO: provide email address",
    }


def _distribution_contact_template() -> dict[str, str]:
    return _contact_template(
        person_placeholder="TODO: provide distribution contact",
        organization_placeholder="TODO: provide distributor organization",
    )


def _metadata_contact_template() -> dict[str, str]:
    return _contact_template(
        person_placeholder="TODO: provide metadata contact",
        organization_placeholder="TODO: provide metadata contact organization",
    )


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
                "citation.publication_info.place",
                "citation.publication_info.publisher",
                "description.abstract",
                "description.purpose",
                "time_period.begin_date",
                "time_period.end_date",
                "time_period.single_date",
                "time_period.current",
                "data_quality.attribute_accuracy",
                "data_quality.logical_consistency",
                "data_quality.completeness",
                "data_quality.lineage.process_steps",
                "point_of_contact.person",
                "point_of_contact.organization",
                "point_of_contact.address",
                "point_of_contact.city",
                "point_of_contact.phone",
                "distribution.distributor.person",
                "distribution.distributor.organization",
                "distribution.distributor.address",
                "distribution.distributor.city",
                "distribution.distributor.phone",
                "metadata.contact.person",
                "metadata.contact.organization",
                "metadata.contact.address",
                "metadata.contact.city",
                "metadata.contact.phone",
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
            "abstract": _abstract_scaffold(inspection, layer_info),
            "purpose": _purpose_scaffold(inspection, layer_info),
            "supplemental_information": _supplemental_scaffold(inspection),
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
        "point_of_contact": _contact_template(),
        "data_quality": {
            "attribute_accuracy": _attribute_accuracy_scaffold(inspection),
            "logical_consistency": _logical_consistency_scaffold(inspection),
            "completeness": _completeness_scaffold(inspection),
            "lineage": {
                "process_steps": [
                    {
                        "description": _lineage_scaffold(inspection),
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
            "distributor": _distribution_contact_template(),
            "liability": TODO_DISTRIBUTION,
            "online_resource": "",
            "fees": "None.",
        },
        "metadata": {
            "date": datetime.now().strftime("%Y%m%d"),
            "contact": _metadata_contact_template(),
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

    doc["distribution"]["distributor"] = deepcopy(doc["point_of_contact"])
    doc["metadata"]["contact"] = deepcopy(doc["point_of_contact"])

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


def _abstract_scaffold(inspection: DatasetInspection, layer_info: LayerInfo | None) -> str:
    dataset_name = inspection.dataset_name.replace("_", " ")
    format_name = inspection.data_format
    extent_text = _extent_summary(layer_info)
    layer_text = _layer_summary(inspection)
    feature_text = _feature_summary(layer_info)
    return (
        f"{TODO_ABSTRACT}\n"
        f"This metadata record describes the {dataset_name} dataset in {format_name} format. "
        f"{layer_text} {feature_text} {extent_text} "
        "USER INPUT NEEDED: add the scientific context, map purpose, publication framing, "
        "and any important geologic interpretation that cannot be derived from the dataset structure alone."
    ).strip()


def _purpose_scaffold(inspection: DatasetInspection, layer_info: LayerInfo | None) -> str:
    dataset_name = inspection.dataset_name.replace("_", " ")
    layer_text = _layer_summary(inspection)
    return (
        f"{TODO_PURPOSE}\n"
        f"The {dataset_name} dataset appears to support geospatial analysis, visualization, and distribution of mapped data. "
        f"{layer_text} USER INPUT NEEDED: explain why these data were created, the intended scientific or mapping use, "
        "and any limits on how the dataset should be interpreted."
    ).strip()


def _supplemental_scaffold(inspection: DatasetInspection) -> str:
    selected = inspection.selected_layer or "the dataset as a whole"
    if _looks_like_gems_dataset(inspection):
        return (
            f"{TODO_SUPPL}\n"
            f"{inspection.dataset_name} appears to conform to GeMS (Geologic Map Schema). MetaMapper auto-populated structural details for {selected}. "
            "Inherited GeMS entity and attribute definitions may be referenced from the GeMS standard rather than rewritten field-by-field. "
            "USER INPUT NEEDED: add processing notes, related products, geologic interpretation, companion report references, "
            "and any dataset-specific caveats that users should read before reuse."
        ).strip()
    return (
        f"{TODO_SUPPL}\n"
        f"MetaMapper auto-populated structural details for {selected} from the source dataset. "
        "USER INPUT NEEDED: add processing notes, related products, geologic interpretation, companion report references, "
        "and any dataset-specific caveats that users should read before reuse."
    ).strip()


def _attribute_accuracy_scaffold(inspection: DatasetInspection) -> str:
    return (
        "TODO: USER INPUT NEEDED. REVISE THIS ATTRIBUTE ACCURACY STATEMENT.\n"
        f"MetaMapper identified {len(inspection.layer_details) or (1 if inspection.layer_info else 0)} entity or layer definitions from the dataset. "
        "USER INPUT NEEDED: describe how attribute values were checked, whether values were interpreted from source mapping or measurements, "
        "and any known attribute limitations or uncertainty."
    )


def _logical_consistency_scaffold(inspection: DatasetInspection) -> str:
    return (
        "TODO: USER INPUT NEEDED. REVISE THIS LOGICAL CONSISTENCY STATEMENT.\n"
        f"The inspected dataset includes {len(inspection.layer_names)} discovered layer(s) or table(s). "
        "USER INPUT NEEDED: describe topology checks, schema consistency checks, identifier validation, "
        "or other quality-control steps that were applied before release."
    )


def _completeness_scaffold(inspection: DatasetInspection) -> str:
    extent_text = _extent_summary(_preferred_layer_info(inspection))
    return (
        "TODO: USER INPUT NEEDED. REVISE THIS COMPLETENESS STATEMENT.\n"
        f"The dataset extent currently corresponds to {extent_text.lower()} "
        "USER INPUT NEEDED: describe what is included, what is excluded, the mapping or observation limits, "
        "and any known geographic or thematic omissions."
    )


def _lineage_scaffold(inspection: DatasetInspection) -> str:
    return (
        f"{TODO_LINEAGE}\n"
        f"MetaMapper inspected the source dataset at {inspection.dataset_path}. "
        "USER INPUT NEEDED: replace this with a real process step describing compilation, interpretation, editing, "
        "or publication preparation work performed by the data producer."
    )


def _extent_summary(layer_info: LayerInfo | None) -> str:
    if not layer_info or not layer_info.extent:
        return "Spatial extent was not derived automatically."
    bounds = _bounding_coordinates(layer_info)
    west = bounds.get("west")
    east = bounds.get("east")
    north = bounds.get("north")
    south = bounds.get("south")
    return f"Approximate bounds are west {west}, east {east}, south {south}, and north {north}."


def _layer_summary(inspection: DatasetInspection) -> str:
    if inspection.selected_layer:
        return f"The selected layer is {inspection.selected_layer}."
    if inspection.layer_names:
        if len(inspection.layer_names) == 1:
            return f"The dataset contains 1 discovered layer: {inspection.layer_names[0]}."
        preview = ", ".join(inspection.layer_names[:5])
        extra = len(inspection.layer_names) - 5
        if extra > 0:
            preview += f", and {extra} more"
        return f"The dataset contains {len(inspection.layer_names)} discovered layers or tables, including {preview}."
    return "No layers were identified automatically."


def _feature_summary(layer_info: LayerInfo | None) -> str:
    if not layer_info:
        return ""
    parts: list[str] = []
    if layer_info.data_kind:
        parts.append(f"It is a {layer_info.data_kind} dataset")
    if layer_info.geometry_type and layer_info.geometry_type != "None":
        parts.append(f"with {layer_info.geometry_type} geometry")
    if layer_info.feature_count is not None:
        parts.append(f"and approximately {layer_info.feature_count} features or records")
    if not parts:
        return ""
    return " ".join(parts) + "."


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
                "central_meridian": "",
                "latitude_projection_origin": "0.0",
                "false_easting": "500000.0",
                "false_northing": "0.0",
                "x_resolution": "",
                "y_resolution": "",
                "unit": spatial_reference.unit if spatial_reference and spatial_reference.unit else "meters",
            },
            "geodetic": {
                "datum": spatial_reference.datum if spatial_reference and spatial_reference.datum else "",
                "ellipsoid": "",
                "semi_major_axis": "",
                "denominator_of_flattening": "",
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
                "datum": spatial_reference.datum if spatial_reference and spatial_reference.datum else "",
                "ellipsoid": "",
                "semi_major_axis": "",
                "denominator_of_flattening": "",
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

    gems_dataset = _looks_like_gems_dataset(inspection)
    entities: list[dict[str, Any]] = []
    for layer_info in layer_infos:
        custom_attributes: list[dict[str, Any]] = []
        omitted_standard_fields: list[str] = []
        omitted_esri_fields: list[str] = []
        for field in layer_info.fields:
            standard_source = _standard_field_source(layer_info, field.name)
            if standard_source == "GeMS":
                omitted_standard_fields.append(field.name)
                continue
            if standard_source == "ESRI":
                omitted_esri_fields.append(field.name)
                continue
            attribute: dict[str, Any] = {
                "label": field.name,
                "definition": _attribute_definition(field),
                "definition_source": _attribute_definition_source(layer_info, field),
                "unrepresentable_domain": f"Raw field type: {field.field_type}",
            }
            if field.alias:
                attribute["alias"] = field.alias
            if field.length is not None:
                attribute["length"] = field.length
            if field.nullable is not None:
                attribute["nullable"] = field.nullable
            custom_attributes.append(attribute)

        entity: dict[str, Any] = {
            "name": layer_info.name,
            "description": _entity_description(layer_info, custom_attributes, omitted_standard_fields, omitted_esri_fields),
            "definition_source": _entity_definition_source(layer_info),
            "data_kind": layer_info.data_kind,
            "geometry_type": layer_info.geometry_type,
            "feature_count": layer_info.feature_count,
            "attributes": custom_attributes,
        }
        entity["omitted_standard_fields"] = omitted_standard_fields
        entity["omitted_esri_fields"] = omitted_esri_fields

        if layer_info.spatial_reference:
            entity["spatial_reference"] = layer_info.spatial_reference.to_dict()
        if layer_info.extent:
            entity["extent"] = layer_info.extent.to_dict()
        if layer_info.raster:
            entity["raster"] = layer_info.raster.to_dict()
        entities.append(entity)

    result: dict[str, Any] = {"entities": entities}
    if gems_dataset:
        result["overview"] = {
            "description": (
                "This geodatabase appears to follow GeMS (Geologic Map Schema). "
                "Standard GeMS entities and inherited GeMS attributes are referenced from the GeMS standard; "
                "only non-standard custom fields are documented individually below."
            ),
            "citation": "GeMS (Geologic Map Schema) standard definitions and reviewed companion metadata for this dataset.",
        }
    return result


def _entity_description(
    layer_info: LayerInfo,
    custom_attributes: list[dict[str, Any]],
    omitted_standard_fields: list[str],
    omitted_esri_fields: list[str],
) -> str:
    parts = [_entity_base_description(layer_info)]
    if layer_info.data_kind:
        parts.append(f"Data kind: {layer_info.data_kind}.")
    if layer_info.geometry_type and layer_info.geometry_type != "None":
        parts.append(f"Geometry type: {layer_info.geometry_type}.")
    if layer_info.feature_count is not None:
        parts.append(f"Approximate record count: {layer_info.feature_count}.")
    if omitted_standard_fields:
        parts.append(
            f"{len(omitted_standard_fields)} inherited GeMS field(s) are referenced from the GeMS schema rather than documented individually."
        )
    if omitted_esri_fields:
        parts.append(
            f"{len(omitted_esri_fields)} ESRI-managed system field(s) are omitted from detailed attribute documentation."
        )
    if custom_attributes:
        parts.append(f"{len(custom_attributes)} custom field(s) are documented individually below.")
    return " ".join(parts)


def _entity_definition_source(layer_info: LayerInfo) -> str:
    if _is_gems_entity_name(layer_info.name):
        return "GeMS"
    if layer_info.spatial_reference and layer_info.spatial_reference.name:
        return f"Source dataset schema inspection ({layer_info.spatial_reference.name})."
    return "Source dataset schema inspection."


def _attribute_definition(field: Any) -> str:
    alias_text = f" ({field.alias})" if getattr(field, "alias", None) else ""
    return f"Attribute {field.name}{alias_text} imported from the source dataset schema as type {field.field_type}."


def _attribute_definition_source(layer_info: LayerInfo, field: Any) -> str:
    if getattr(field, "alias", None):
        return f"Source dataset field schema and alias for layer {layer_info.name}."
    return f"Source dataset field schema for layer {layer_info.name}."


def _entity_base_description(layer_info: LayerInfo) -> str:
    short_name = layer_info.name.split("/")[-1]
    description = GEMS_ENTITY_DESCRIPTIONS.get(short_name)
    if description:
        return description
    return f"Entity derived from the source dataset layer {layer_info.name}."


def _is_gems_entity_name(name: str) -> bool:
    return name.split("/")[-1] in GEMS_ENTITY_DESCRIPTIONS


def _standard_field_source(layer_info: LayerInfo, field_name: str) -> str | None:
    if field_name in ESRI_STANDARD_FIELD_DEFINITIONS:
        return "ESRI"
    if field_name in GEMS_STANDARD_FIELD_DEFINITIONS:
        return "GeMS"
    short_name = layer_info.name.split("/")[-1]
    if field_name == f"{short_name}_ID":
        return "GeMS"
    if field_name.endswith("_ID") and _is_gems_entity_name(short_name):
        return "GeMS"
    return None


def _looks_like_gems_dataset(inspection: DatasetInspection) -> bool:
    layer_infos = inspection.layer_details or ([inspection.layer_info] if inspection.layer_info else [])
    gems_score = 0
    for layer_info in layer_infos:
        short_name = layer_info.name.split("/")[-1]
        if short_name in GEMS_ENTITY_DESCRIPTIONS:
            gems_score += 2
        field_names = {field.name for field in layer_info.fields}
        gems_score += sum(1 for field_name in field_names if field_name in GEMS_STANDARD_FIELD_DEFINITIONS)
    return gems_score >= 3


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
