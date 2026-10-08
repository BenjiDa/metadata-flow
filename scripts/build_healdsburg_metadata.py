"""Rebuild standalone and per-entity Healdsburg metadata from the supplied snapshot.

Run with PYTHONPATH=src and the optional GIS inspection dependencies installed.
The source geodatabase is opened read-only. No feature is moved, deleted, or clipped.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path
import re
import warnings
from xml.etree import ElementTree as ET
import zipfile

import pyogrio
import pandas as pd
import yaml

from metamapper.config import MetadataConfig, find_missing_required_fields
from metamapper.inspection_backends import OpenSourceBackend
from metamapper.prefill import (build_prefill_document, GEMS_ENTITY_DESCRIPTIONS,
                               GEMS_STANDARD_FIELD_DEFINITIONS, ESRI_STANDARD_FIELD_DEFINITIONS)
from metamapper.spatial_audit import audit_bounds, layer_role
from metamapper.validators import run_internal_validation
from metamapper.xml_builder import build_metadata_xml, write_metadata_xml

GEMS = 'https://pubs.usgs.gov/tm/11b10/tm11b10.pdf'
DEFINITIONS = {
    'Age': 'Geologic age of the described map unit, as recorded in the map-unit description.',
    'Name': 'Name of the map unit or named record.',
    'FullName': 'Expanded name of the map unit.',
    'Description': 'Geologic description of the map unit.',
    'HierarchyKey': 'Sortable key specifying the position of an entry in the descriptive hierarchy.',
    'ParagraphStyle': 'Paragraph style used to format the map-unit description.',
    'AreaFillRGB': 'Red, green, and blue color specification for the map-unit area fill.',
    'AreaFillPatternDescription': 'Description of the pattern used for the map-unit area fill.',
    'DescriptionSourceID': 'Identifier of the source of the unit description; refers to DataSources.',
    'Source': 'Bibliographic citation or description identifying the source of mapped information.',
    'URL': 'Web address associated with the source citation.',
    'Term': 'Term defined by this glossary entry.',
    'Definition': 'Definition of the glossary term or geomaterial classification.',
    'DefinitionSourceID': 'Identifier of the source of the definition; refers to DataSources.',
    'IndentedName': 'Display name of the geomaterial, indented to indicate its hierarchical position.',
    'Azimuth': 'Orientation azimuth in degrees clockwise from north. Interpret planar attitudes using the applicable GeMS orientation convention and feature Type.',
    'Inclination': 'Inclination of the planar or linear feature in degrees from horizontal; interpretation depends on Type.',
    'StationID': 'Identifier linking an observation to its field station, where such a record is available.',
    'StationsID': 'Legacy station identifier field. Its relationship to StationID has not been established; do not assume the two fields are interchangeable.',
    'FieldSampleID': 'Identifier assigned to a sample during field collection.',
    'AlternateSampleID': 'Additional identifier for the sample.',
    'MaterialAnalyzed': 'Material subjected to the analysis recorded by this entry.',
    'NumericAge': 'Numerical age of the analyzed material, in the units recorded in AgeUnits.',
    'AgePlusError': 'Positive uncertainty associated with NumericAge, in AgeUnits.',
    'AgeMinusError': 'Negative uncertainty associated with NumericAge, in AgeUnits.',
    'AgeUnits': 'Units of the numerical age and its associated uncertainties.',
    'ErrorMeasure': 'Description of the statistical measure used to express the reported age uncertainty.',
    'AnalysisSourceID': 'Identifier of the source of analytical results; refers to DataSources.',
    'FossilForms': 'Fossil taxa or forms identified in the sample.',
    'FossilAge': 'Age interpreted from the fossil assemblage.',
    'FossilFormsSourceID': 'Identifier of the source of fossil identification; refers to DataSources.',
    'FossilAgeSourceID': 'Identifier of the source of the fossil-age interpretation; refers to DataSources.',
    'MapProperty': 'Name of the map-level property documented by this entry.',
    'MapPropertyValue': 'Value assigned to the named map-level property.',
    'Lithology': 'Lithologic classification of a component of the map unit.',
    'PartType': 'Classification of the part of the map unit represented by this lithology entry.',
    'ProportionTerm': 'Qualitative description of the abundance of the lithologic component.',
    'ProportionValue': 'Numerical proportion of the lithologic component, where supplied.',
    'ScientificConfidence': 'Confidence assigned to the lithologic interpretation.',
    'Value': 'Value represented by the isovalue line; units depend on the mapped quantity.',
    'ValueConfidence': 'Confidence or uncertainty associated with the isovalue-line value.',
    'created_user': 'Geodatabase editor-tracking account that created the record; not a statement of scientific authorship.',
    'created_date': 'Geodatabase editor-tracking creation timestamp; not a field observation date.',
    'last_edited_user': 'Geodatabase editor-tracking account that last edited the record.',
    'last_edited_date': 'Geodatabase editor-tracking last-edit timestamp; not a field observation date.',
    'CITATION': 'Legacy citation text field. All inspected values are null or empty; use DataSourceID and DataSources for provenance.',
    'Type2': 'Legacy secondary geologic-line classification containing feature and qualification text; retained alongside Type.',
    'Symbol2': 'Secondary structural-orientation symbol code retained alongside Symbol; precedence between the two fields has not been documented.',
    'Shape_Length_1': 'Legacy length field retained alongside Shape_Length. Its calculation history and currency are not established; do not assume it is synchronized with geometry.',
    'ROUTEID': 'Identifier of the route associated with the cross-section surface profile.',
    'long_nad27': 'Legacy-named longitude attribute. The compiler specifies that the stored layer CRS is authoritative (WGS84); the field name does not establish NAD27 coordinates.',
    'lat_nad27': 'Legacy-named latitude attribute. The compiler specifies that the stored layer CRS is authoritative (WGS84); the field name does not establish NAD27 coordinates.',
    'gradient': 'Geophysical gradient-related value in the supporting point layer. Numerical units, normalization, and processing method were not supplied; no unit conversion is implied.',
    'ContourMin': 'Lower contour interval bound for the supporting geophysical polygon. Units and processing method were not supplied.',
    'ContourMax': 'Upper contour interval bound for the supporting geophysical polygon. Units and processing method were not supplied.',
    'OriginClassID': 'Identifier of the originating feature class in a stored topology diagnostic.',
    'OriginID': 'OBJECTID of the originating feature referenced by the topology diagnostic.',
    'DestClassID': 'Identifier of the destination feature class, where the topology rule uses a second feature.',
    'DestID': 'OBJECTID of the destination feature referenced by the topology diagnostic.',
    'TopoRuleType': 'ArcGIS code identifying the kind of topology rule associated with this diagnostic.',
    'TopoRuleID': 'Identifier of the topology rule within its topology definition.',
    'IsException': 'Flag recording whether the topology diagnostic was marked as an exception.',
    'IsRetired': 'System flag associated with the dirty-area diagnostic record.',
    'DirtyArea_Length': 'Stored perimeter of a topology dirty area in native coordinate units.',
    'DirtyArea_Area': 'Stored area of a topology dirty area in squared native coordinate units.',
    'DirtyArea': 'Geometry identifying an area edited since the applicable topology validation state.',
}
ANNOTATION = {
    'FeatureID': 'Identifier of the feature associated with this annotation, if feature-linked.',
    'ZOrder': 'Drawing order of the annotation element.',
    'AnnotationClassID': 'Identifier of the annotation class.',
    'Element': 'ArcGIS serialized annotation element; binary content requires ArcGIS for full interpretation.',
    'SymbolID': 'Identifier of the annotation symbol in the annotation symbol collection.',
    'Status': 'ArcGIS annotation placement status code.',
    'TextString': 'Text displayed by the annotation element.',
    'FontName': 'Name of the font used to display the annotation.',
    'FontStyle': 'Font style used to display the annotation.',
    'FontSize': 'Annotation font size in points.',
    'Underline': 'Flag indicating underlined annotation text.',
    'VerticalAlignment': 'Vertical alignment code for the annotation text.',
    'HorizontalAlignment': 'Horizontal alignment code for the annotation text.',
    'XOffset': 'Horizontal offset used for annotation placement.',
    'YOffset': 'Vertical offset used for annotation placement.',
    'Angle': 'Rotation angle of the annotation text.',
    'FontLeading': 'Line spacing used for annotation text.',
    'WordSpacing': 'Spacing between words in the annotation.',
    'CharacterWidth': 'Character width setting for annotation text.',
    'CharacterSpacing': 'Spacing between characters in the annotation.',
    'FlipAngle': 'Angle threshold used by ArcGIS to control annotation text flipping.',
    'Override': 'ArcGIS bit mask identifying annotation symbol property overrides.',
}
ENTITY = {
    'DataSourcePolys': 'Polygons identifying geographic areas associated with mapping sources; source identifiers refer to DataSources.',
    'MapUnitOverlayPolys': 'Optional polygons for map units superposed on the primary map-unit coverage.',
    'OverlayPolys': 'Optional thematic polygons superposed on the geologic map.',
    'CartographicLines': 'Lines used in preparing the map, including cartographic boundaries and section traces as classified by Type.',
    'IsoValueLines': 'Optional lines connecting locations of equal value for a mapped quantity.',
    'FossilPoints': 'Optional fossil localities, fossil identifications, and age interpretations.',
    'StandardLithology': 'Optional structured descriptions of lithologic components of map units.',
    'MiscellaneousMapInformation': 'Optional key-value descriptions of map-level properties.',
    'GeoMaterialDict': 'Hierarchical dictionary of geomaterial classifications and their definitions.',
    'CMULines': 'Lines in the correlation-of-map-units diagram, stored in a drawing layout rather than at Earth locations.',
    'CMUPolys': 'Polygons representing boxes or areas in the correlation-of-map-units diagram.',
    'CMUPoints': 'Label and symbol placement points in the correlation-of-map-units diagram.',
    'CSAContactAndFaults': 'Interpreted contacts and faults in cross section A, stored in section-distance and elevation coordinates.',
    'CSAFrame': 'Frame lines and labels defining cross-section axes and presentation limits.',
    'CSASurfaceProfile': 'Topographic surface profile along cross section A, in section-distance and elevation coordinates.',
    'CSAMapUnitPolys': 'Polygons representing the interpreted subsurface distribution of map units in cross section A.',
}


def field_definition(name, layer, crs):
    if name.upper() in {'OBJECTID','FID'}:
        return 'Internal geodatabase record number; corresponds to the original OBJECTID used in the audit.'
    if name.lower() == 'shape':
        return 'Native geometry object maintained by the geodatabase. Diagram coordinates and geographic coordinates have distinct meanings documented at the entity level.'
    if name in DEFINITIONS:
        return DEFINITIONS[name]
    if name in ANNOTATION:
        return ANNOTATION[name]
    if name in GEMS_STANDARD_FIELD_DEFINITIONS:
        return GEMS_STANDARD_FIELD_DEFINITIONS[name]
    if name in ESRI_STANDARD_FIELD_DEFINITIONS:
        return ESRI_STANDARD_FIELD_DEFINITIONS[name]
    if name.lower() == 'shape_length':
        return 'Geometry length or perimeter maintained in native coordinate units.'
    if name.lower() == 'shape_area':
        return 'Geometry area maintained in squared native coordinate units.'
    if name.lower() in {'type', 'label'}:
        return GEMS_STANDARD_FIELD_DEFINITIONS[name.title()]
    if name.endswith('_ID') or name == 'ContactsAndFaultsID':
        return f'Identifier of this {layer} record; uniqueness was checked in the supplied snapshot and is reported separately.'
    raise ValueError(f'No meaningful field definition supplied for {layer}.{name}')


def write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('examples/sample_data/Healdsburg_map_gems_1.gdb'))
    parser.add_argument('--profile', type=Path, default=Path('configs/healdsburg_metadata.yml'))
    parser.add_argument('--out', type=Path, default=Path('outputs/healdsburg'))
    parser.add_argument('--refresh-audit', action='store_true')
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    profile = yaml.safe_load(args.profile.read_text())
    nominal = profile['spatial_domain']['bounding_coordinates']
    audit_path = out/'audit/boundary_audit.json'
    if args.refresh_audit or not audit_path.exists():
        audit_bounds(args.dataset, tuple(nominal[k] for k in ['west','south','east','north']), out/'audit')
    audit = json.loads(audit_path.read_text())
    by_name = {row['layer']: row for row in audit['layers']}
    inspection = OpenSourceBackend().inspect(args.dataset, all_layers=True)
    write_yaml(out/'inspection.yaml', inspection.to_dict())
    frames = {layer.name: pyogrio.read_dataframe(args.dataset, layer=layer.name, read_geometry=False, fid_as_index=True)
              for layer in inspection.layer_details}
    dmu = frames['DescriptionOfMapUnits']
    sources = frames['DataSources']
    glossary = frames['Glossary']
    dmu_values = {str(row.MapUnit): str(row.Name or '') + (' — '+str(row.Description) if row.Description else '')
                  for row in dmu.itertuples() if row.MapUnit is not None and str(row.MapUnit).strip()}
    source_values = {str(row.DataSources_ID): str(row.Source) for row in sources.itertuples()}
    glossary_values = {str(row.Term): str(row.Definition) for row in glossary.itertuples()}
    quality, entities = [], []
    schema_items = out/'evidence/gdb_items.json'
    items = {row['Name']: row for row in json.loads(schema_items.read_text())} if schema_items.exists() else {}
    for layer in inspection.layer_details:
        name = layer.name
        frame = frames[name]
        role = layer_role(name)
        description = ENTITY.get(name, GEMS_ENTITY_DESCRIPTIONS.get(name))
        if not description:
            if role == 'topology diagnostics':
                description = 'Stored ArcGIS topology '+('dirty-area records identifying edits requiring validation.' if 'DirtyAreas' in name else 'diagnostics referencing participating feature classes and rule identifiers.')
            elif 'Anno' in name or 'Annotation' in name:
                description = 'ArcGIS annotation elements used to display '+('cross-section unit labels.' if role == 'cross-section diagram' else 'correlation-diagram labels.' if role == 'correlation diagram' else 'map text or structural-orientation labels.')
            elif 'gradient' in name:
                description = 'Supporting '+('magnetic' if name.startswith('mag') else 'gravity')+' gradient point data covering the quadrangle and a surrounding margin. Stored WGS84 CRS is authoritative, as confirmed by the compiler.'
            elif name.startswith('Contour_'):
                description = 'Supporting '+('magnetic' if 'mag' in name else 'gravity')+' contour-interval polygons; numerical units and processing method were not supplied.'
            else:
                raise ValueError(f'No entity description for {name}')
        description += f' The supplied snapshot contains {len(frame):,} records.'
        if not len(frame):
            description += ' This is an empty schema class; it supplies no observations or mapped coverage in this snapshot.'
        if role in {'cross-section diagram','correlation diagram'}:
            description += ' Coordinates describe diagram layout, not Earth locations; exclude this entity from geographic extent calculations.'
        elif role == 'topology diagnostics':
            description += ' Diagnostics may be retained from earlier validation; presence does not by itself establish unresolved geologic errors.'
        entity = dict(name=name, description=description, definition_source='Supplied database, GeMS entity conventions, and compiler account.',
                      role=role, feature_count=len(frame), geometry_type=layer.geometry_type, attributes=[])
        fields = [(field.name, field.field_type, field.alias, field.nullable) for field in layer.fields]
        definition = items.get(name, {}).get('Definition')
        if definition:
            root = ET.fromstring(definition)
            fields = [(f.findtext('Name'), f.findtext('FieldType'), f.findtext('AliasName'), f.findtext('IsNullable'))
                      for f in root.findall('./GPFieldInfoExs/GPFieldInfoEx')]
        # ArcGIS item definitions can retain incomplete schema snapshots after
        # edits. The current readable schema is authoritative for field coverage.
        names = {field[0] for field in fields}
        for field in layer.fields:
            if field.name not in names:
                fields.append((field.name, field.field_type, field.alias, field.nullable))
                names.add(field.name)
        current_info = pyogrio.read_info(args.dataset, layer=name)
        for key, dtype in [('fid_column', 'geodatabase record ID'), ('geometry_name', 'native geometry')]:
            field_name = current_info.get(key)
            if field_name and field_name not in names:
                fields.append((field_name, dtype, field_name, key != 'fid_column'))
                names.add(field_name)
        if not fields:
            raise ValueError(f'No schema fields for {name}')
        issues = dict(layer=name, records=len(frame), fields={})
        for field_name, dtype, alias, nullable in fields:
            definition = field_definition(field_name, name, layer.spatial_reference)
            if field_name == 'Shape_Length':
                definition += ' Units are meters for UTM and section-distance coordinates, and degrees for geographic-coordinate layers.'
            if field_name == 'Shape_Area':
                definition += ' Units are square meters for UTM and section coordinates, and squared degrees for geographic-coordinate layers.'
            domain = f'Storage type: {dtype}; nullable: {nullable}. '
            domain += 'No stored records in this snapshot.' if not len(frame) else 'Values as stored in the supplied database; null and empty values indicate information not supplied.'
            attribute = dict(label=field_name, definition=definition,
                             definition_source='GeMS standard and supplied database' if field_name in GEMS_STANDARD_FIELD_DEFINITIONS else 'Source schema, observed values, ArcGIS conventions, and compiler account.',
                             unrepresentable_domain=domain)
            if alias:
                attribute['alias'] = alias
            if field_name in frame:
                series = frame[field_name]
                blank = series.isna() | pd.Series([isinstance(v,str) and not v.strip() for v in series], index=series.index, dtype=bool)
                vals = series[~blank]
                counts = dict(null_or_blank_count=int(blank.sum()), populated_count=int((~blank).sum()))
                text_values = sorted({str(v) for v in vals})
                counts['distinct_count'] = len(text_values)
                if field_name.endswith('_ID') or field_name == 'ContactsAndFaultsID':
                    counts['duplicate_populated_count'] = int(vals.duplicated().sum())
                lookup = dmu_values if field_name == 'MapUnit' else source_values if field_name.endswith('SourceID') or field_name == 'DataSourceID' else glossary_values
                if field_name in {'MapUnit','Type','Type2','IdentityConfidence','ExistenceConfidence','GeoMaterialConfidence','IsConcealed','DataSourceID','LocationSourceID','OrientationSourceID','DescriptionSourceID','Term'}:
                    attribute.pop('unrepresentable_domain')
                    # Domains describe observed values, without claiming schema enforcement.
                    attribute['enumerated_domain'] = [dict(value=v, definition=lookup.get(v, f'Observed value "{v}"; no corresponding explanatory lookup supplied.'),
                                                          definition_source='DescriptionOfMapUnits, DataSources, or Glossary in the supplied database; observed-value domain.') for v in text_values]
                    if not text_values:
                        attribute['unrepresentable_domain'] = domain
                if field_name == 'MapUnit':
                    counts['unmatched_map_units'] = sorted(set(text_values)-set(dmu_values))
                if field_name.endswith('SourceID') or field_name == 'DataSourceID':
                    refs = {x.strip() for v in text_values for x in re.split(r'[;|,]', v) if x.strip()}
                    counts['unmatched_source_ids'] = sorted(refs-set(source_values))
                if field_name in {'LocationConfidenceMeters','Azimuth','Inclination','OrientationConfidenceDegrees'}:
                    numeric = vals.astype(float)
                    counts['minimum'] = float(numeric.min()) if len(numeric) else None
                    counts['maximum'] = float(numeric.max()) if len(numeric) else None
                    counts['negative_count'] = int((numeric < 0).sum())
                    if field_name in {'LocationConfidenceMeters','OrientationConfidenceDegrees'}:
                        attribute['definition'] += ' GeMS uses -9 to represent an unknown or unavailable uncertainty, rather than a negative measured error.'
                issues['fields'][field_name] = counts
            entity['attributes'].append(attribute)
        entities.append(entity)
        quality.append(issues)
    (out/'audit/attribute_audit.json').write_text(json.dumps(quality, indent=2)+'\n')

    doc = build_prefill_document(inspection)
    for key, value in profile.items():
        if key not in {'review_questions','evidence_sources','data_quality'}:
            doc[key] = deepcopy(value)
    doc['inspection'].pop('user_required_fields', None)
    doc['inspection']['boundary_audit'] = 'audit/boundary_audit.json'
    doc['metadata']['contact'] = deepcopy(profile['point_of_contact'])
    doc['distribution']['distributor'] = deepcopy(profile['point_of_contact'])
    doc['distribution']['online_resource'] = ''
    doc['distribution']['format_name'] = 'Esri File Geodatabase (GeMS-style working database)'
    primary = next(layer for layer in inspection.layer_details if layer.name == 'MapUnitPolys')
    from metamapper.prefill import _spatial_reference_document
    doc['spatial_reference'] = _spatial_reference_document(primary)
    doc['spatial_reference']['utm'].update(central_meridian='-123.0', x_resolution='0.0001', y_resolution='0.0001')
    doc['spatial_reference']['geodetic'].update(ellipsoid='GRS 1980', semi_major_axis='6378137.0', denominator_of_flattening='298.257222101')
    doc['entity_attribute_information'] = dict(overview=dict(description='Each feature class and table, including empty schema classes and supporting diagrams, is documented individually. All source fields are described explicitly. Observed domains document this snapshot and do not assert enforcement by the database.', citation=GEMS), entities=entities)
    geo_bounds = [row['geographic_bounds'] for row in audit['layers'] if row['geographic_bounds'] and row['role'] not in {'topology diagnostics'}]
    actual = dict(west=min(b[0] for b in geo_bounds), south=min(b[1] for b in geo_bounds), east=max(b[2] for b in geo_bounds), north=max(b[3] for b in geo_bounds))
    doc['spatial_domain']['bounding_coordinates'] = actual
    doc['spatial_domain']['intended_quadrangle_bounds'] = nominal
    main_rows = [r for r in audit['layers'] if r['role']=='map data']
    outside = sum(r['outside_count'] for r in main_rows)
    beyond = sum(r['beyond_tolerance_count'] for r in main_rows)
    invalid = sum(r['invalid_count'] for r in main_rows)
    empty_geom = sum(r['null_or_empty_count'] for r in main_rows)
    doc['description']['supplemental_information'] = (
        'Intended coverage is the Healdsburg 30-by-60-minute quadrangle, 123 to 122 degrees west and 38.5 to 39 degrees north. '
        'Bounding coordinates in this record describe actual geographic data, including supporting geophysical margins; they are not a claim that all data have been clipped to the quadrangle. '
        'Primary map data use NAD83 / UTM zone 10N (EPSG:26910). Supporting geophysical layers use stored WGS84 (EPSG:4326); '
        'the compiler confirmed that stored CRS values are authoritative despite legacy nad27 field names. Cross-section and correlation-diagram '
        'coordinates represent section distance/elevation or page layout and are excluded from geographic bounds. Per-entity records explain those coordinates. '
        'The 0.0001-meter coordinate storage resolution is not an accuracy estimate. Z and M dimensions occur in some geometries; they have not been validated as geologic measurements. '
        'This snapshot includes empty optional classes, duplicated geophysical layers, annotations, and retained topology diagnostics. '
        'Use the accompanying metadata index and audit before selecting layers for analysis. Publication citation and final compilation scale remain unconfirmed.')
    doc['data_quality'] = dict(
        attribute_accuracy='Attribute definitions and observed coded values were checked against the supplied schema, DescriptionOfMapUnits, Glossary, and DataSources. '
        'No independent numerical attribute-accuracy assessment was performed. Confidence fields describe interpretations rather than measured errors. '
        'OrientationPoints contains 2,946 records with LocationConfidenceMeters=-9, the GeMS convention for unknown or unavailable uncertainty. '
        'Legacy duplicate fields and blank citation text are documented in the field descriptions. Attribute-level nulls, duplicate identifiers, and unmatched lookup references are listed in audit/attribute_audit.json.',
        logical_consistency=f'The compiler reports completed topology checks. A read-only check of the supplied snapshot found {invalid} invalid primary-map polygon geometries and {empty_geom} primary-map records with null or empty geometry. '
        'Stored topology diagnostics and dirty areas were inventoried without treating them as a current pass/fail result. Foreign-key membership and populated identifier uniqueness were checked and reported in audit/attribute_audit.json. '
        'No automatic repair, clipping, reclassification, or deletion was performed.',
        completeness=f'The intended coverage is the Healdsburg 30-by-60-minute quadrangle. The supplied workspace contains {len(entities)} feature classes and tables, including 10,023 map-unit polygons, 35,121 contacts/faults records, 5,066 structural-orientation points, and 366 geologic lines. '
        f'Against the assumed NAD83 graticule boundary, {outside} main-map features extend outside the quadrangle; {beyond} exceed a 25-meter reporting tolerance. '
        'Supporting geophysical data extend farther beyond the boundary. No geographically referenced map features were found remotely offshore. '
        'Optional empty feature classes do not establish absence of the corresponding geologic phenomena. Map-unit description records include headings and incomplete descriptive fields. The final mapping scale and thematic completeness have not been confirmed.',
        lineage=deepcopy(profile['data_quality']['lineage']))
    doc['data_quality']['lineage']['process_steps'].append(dict(description='On October 7, 2026, inspected the supplied database read-only, inventoried every feature class and table, checked per-feature geographic bounds using each stored CRS, and produced standalone and per-entity FGDC metadata. Corrected the metadata tool to transform each layer extent before aggregation and exclude empty layers and diagram coordinates. These operations changed metadata generation only; source geometry and attributes were not modified.', date='20261007'))
    doc['keywords'] = dict(theme_keywords=[dict(thesaurus='None', keywords=['geologic map','GeMS','stratigraphy','structural geology','faults','folds','Franciscan Complex','Great Valley Complex','Sonoma Volcanics','Clear Lake Volcanics','Quaternary deposits','geologic history','geologic framework for hazards and resources'])], place_keywords=dict(thesaurus='None',keywords=['California','northern Coast Ranges','Healdsburg 30-by-60-minute quadrangle']), general_keywords=[])
    doc['data_credits'] = 'Compiled primarily from previous mapping cited in DataSources, with additional original mapping and fieldwork during 2022–2026, as reported by the compiler. The full publication author list has not been supplied.'
    doc['validation'] = dict(external_command=None, report_path=None)
    validation = []

    def emit(record, destination):
        missing = find_missing_required_fields(record)
        if missing:
            raise ValueError(f'Unfinished required values: {missing}')
        write_yaml(destination.with_suffix('.yaml'), record)
        write_metadata_xml(build_metadata_xml(MetadataConfig(record)), destination.with_suffix('.xml'))
        result = run_internal_validation(destination.with_suffix('.xml'))
        validation.append(dict(record=str(destination.relative_to(out)), **result.to_dict()))

    emit(doc, out/'Healdsburg_metadata')
    lines = ['# Healdsburg metadata package', '', 'Prepared October 7, 2026 from the supplied geodatabase. Source data were not altered.', '',
             '## Scientific abstract', '', doc['description']['abstract'], '', '## Purpose', '', doc['description']['purpose'], '',
             '## Read this before release', '', 'These are completed working metadata records. Authorship, final title, scale, publisher, and release citation remain unconfirmed; these facts are stated explicitly rather than invented. Internal structural validation is not an external FGDC schema certification or a scientific review.', '',
             '## Deliverables', '', '- `Healdsburg_metadata.xml` and `.yaml`: standalone geodatabase record.',
             '- `feature_metadata/`: one standalone XML and editable YAML record per feature class or table.',
             '- `main_map_feature_metadata.csv`: provenance and confidence values for each main-map feature, keyed to its original OBJECTID. Values are retained from the source; -9 uncertainty means unknown under GeMS.',
             '- `audit/outside_features.csv`: original OBJECTIDs, layer roles, offending bounds, and distances.',
             '- `audit/main_map_outside_features.csv`: the main-map subset, excluding diagrams, diagnostics, annotations, and geophysical margins.',
             '- `audit/outside_feature_locations.geojson`: point markers at the farthest outside vertex of each listed feature.',
             '- `audit/attribute_audit.json`: nulls, duplicate identifiers, and unmatched lookup values.',
             '- `audit/geometry_issues.csv`: invalid or missing geometry by original OBJECTID.',
             '- `audit/boundary_overview.png`: geographic overview of the map and outside locations.', '',
             '## Boundary findings', '', f'{outside} main-map features extend outside the assumed quadrangle; {beyond} exceed 25 meters. The tolerance classifies findings and does not suppress the complete outside list. Diagrams are not tested as Earth locations.', '',
             'The assumed boundary is the NAD83 graticule box 123–122° W, 38.5–39° N. Confirm the intended neatline and datum before editing edge features. Small systematic edge overruns can reflect a clipping or boundary-definition issue rather than isolated misplaced vertices.', '',
             '| Entity | Records | Role | Outside / >25 m | Invalid | Metadata |', '|---|---:|---|---:|---:|---|']
    for entity in entities:
        record = deepcopy(doc)
        name = entity['name']
        row = by_name[name]
        record['citation']['title'] = name+' — '+profile['citation']['title']
        record['description']['abstract'] = entity['description']+' '+profile['description']['abstract']
        record['description']['purpose'] = entity['description'].split('. The supplied snapshot')[0]+'. '+profile['description']['purpose']
        record['entity_attribute_information']['entities'] = [deepcopy(entity)]
        record['dataset']['selected_layer'] = name
        record['dataset']['layers'] = [name]
        record['inspection']['auto_populated'] = next(layer.to_dict() for layer in inspection.layer_details if layer.name==name)
        bounds = row['geographic_bounds']
        if bounds:
            record['spatial_domain']['bounding_coordinates'] = dict(zip(['west','south','east','north'], bounds))
        else:
            record['spatial_domain']['bounding_coordinates'] = nominal
            record['description']['supplemental_information'] += ' This entity has no geographic feature extent; its bounding coordinates express the geographic scope of the parent map only.'
        layer = next(layer for layer in inspection.layer_details if layer.name==name)
        if entity['role'] in {'cross-section diagram','correlation diagram'}:
            record['spatial_reference'] = dict(type='local', local=dict(description='Section-distance/elevation drawing coordinates in meters; no geographic location is implied.' if entity['role']=='cross-section diagram' else 'Correlation-of-map-units drawing coordinates placed in a layout using a UTM-tagged coordinate space; these are not actual Earth locations.', georeference='Geographic context is the parent Healdsburg map. An explicit section-trace or diagram-to-map transformation is not supplied by this record.'))
        elif layer.spatial_reference:
            if layer.spatial_reference.epsg == 26910:
                record['spatial_reference'] = deepcopy(doc['spatial_reference'])
            else:
                record['spatial_reference'] = _spatial_reference_document(layer)
                from pyproj import CRS
                crs = CRS.from_user_input(layer.spatial_reference.wkt or layer.spatial_reference.epsg)
                record['spatial_reference']['geodetic'].update(ellipsoid=crs.ellipsoid.name, semi_major_axis=str(crs.ellipsoid.semi_major_metre), denominator_of_flattening=str(crs.ellipsoid.inverse_flattening))
                # Empty Web Mercator annotation classes are drawing layers.
                if not crs.is_geographic and layer.spatial_reference.epsg != 26910:
                    record['spatial_reference'] = dict(type='local', local=dict(description=f'Native drawing CRS: {crs.name}. This empty annotation class has no mapped geographic extent.', georeference='No records in the supplied snapshot. Native CRS definition is preserved in inspection.yaml.'))
                else:
                    native = items.get(name, {}).get('Definition')
                    scale = ET.fromstring(native).findtext('SpatialReference/XYScale') if native else None
                    if scale:
                        resolution = str(1.0/float(scale))
                        note = 'Angular coordinate resolution is derived from the source geodatabase XY storage scale and does not indicate positional accuracy.'
                    else:
                        # Uncataloged duplicate gradient tables expose five-
                        # decimal-degree positions. Describe observed precision.
                        resolution = '0.00001'
                        note = 'Angular resolution describes the observed five-decimal-degree point coordinates; source geodatabase storage precision was not recovered for this uncataloged supporting layer. This is not positional accuracy.'
                    record['spatial_reference']['geographic'].update(latitude_resolution=resolution, longitude_resolution=resolution)
                    record['description']['supplemental_information'] += ' '+note
        record['data_quality']['completeness'] = entity['description']+f" Boundary audit: {row['outside_count']} features strictly outside, {row['beyond_tolerance_count']} more than 25 meters outside. "+doc['data_quality']['completeness']
        emit(record, out/'feature_metadata'/name)
        lines.append(f"| {name} | {entity['feature_count']:,} | {entity['role']} | {row['outside_count']} / {row['beyond_tolerance_count']} | {row['invalid_count']} | [XML](feature_metadata/{name}.xml) · [YAML](feature_metadata/{name}.yaml) |")
    lines += ['', '## Methods and provenance', '']
    lines += [step['description']+'\n' for step in doc['data_quality']['lineage']['process_steps']]
    lines += ['', '## Facts still requiring confirmation', '']+[f'- {q}' for q in profile['review_questions']]
    lines += ['', '## Sources', '']+[f'- {link}' for link in profile['evidence_sources']]
    (out/'README.md').write_text('\n'.join(lines)+'\n')
    (out/'validation_summary.json').write_text(json.dumps(dict(validation_scope='Internal structural checks, not full FGDC schema validation', record_count=len(validation), passed=all(r['passed'] for r in validation), records=validation),indent=2)+'\n')
    fields=[]
    for entity in entities:
        for attr in entity['attributes']:
            fields.append(dict(entity=entity['name'],field=attr['label'],definition=attr['definition']))
    with (out/'field_dictionary.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['entity','field','definition']);writer.writeheader();writer.writerows(fields)
    # Feature-level provenance and confidence are also delivered as actual
    # record-level metadata, keyed to the unmodified source OBJECTIDs.
    feature_fields = ['layer','objectid','persistent_id','map_unit','feature_type','source_ids','source_citations',
                      'location_confidence_meters','orientation_confidence_degrees','existence_confidence','identity_confidence','station_id','notes']
    with (out/'main_map_feature_metadata.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=feature_fields)
        writer.writeheader()
        for layer in inspection.layer_details:
            if layer_role(layer.name) != 'map data' or layer.geometry_type == 'None':
                continue
            frame = frames[layer.name]
            for fid, feature in frame.iterrows():
                def value(key):
                    val = feature.get(key)
                    return '' if pd.isna(val) else str(val)
                refs = {v.strip() for key in frame.columns if key.endswith('SourceID')
                        for v in re.split(r'[;|,]',value(key)) if v.strip()}
                ids = '; '.join(f'{key}={value(key)}' for key in frame.columns if key.endswith('_ID') and value(key))
                writer.writerow(dict(layer=layer.name, objectid=int(fid),persistent_id=ids,
                                     map_unit=value('MapUnit'), feature_type=value('Type'),source_ids='; '.join(sorted(refs)),
                                     source_citations=' | '.join(source_values.get(ref,'Unresolved source identifier: '+ref) for ref in sorted(refs)),
                                     location_confidence_meters=value('LocationConfidenceMeters'),orientation_confidence_degrees=value('OrientationConfidenceDegrees'),
                                     existence_confidence=value('ExistenceConfidence'), identity_confidence=value('IdentityConfidence'),
                                     station_id=value('StationID') or value('StationsID'),notes=value('Notes')))
    archive = out.parent/'Healdsburg_metadata_package.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(out.rglob('*')):
            if path.is_file() and 'evidence' not in path.parts:
                zipped.write(path,Path('Healdsburg_metadata')/path.relative_to(out))
    print(f'Wrote {len(validation)} records and {len(fields)} field descriptions to {out}; internal validation passed: {all(r["passed"] for r in validation)}')


if __name__ == '__main__':
    main()
