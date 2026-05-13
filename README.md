# metamapper

`metamapper` is a scriptable alternative to the USGS Metadata Wizard for building FGDC-style geologic metadata XML from a structured YAML file. It is not a fork of the Metadata Wizard GUI and does not depend on it.

The first version in this repo is intentionally simple and inspectable:

- inspect a GIS dataset and prefill an editable YAML draft
- read a YAML metadata file
- build FGDC/USGS-style XML
- validate the XML with internal checks or an optional external command
- write readable validation reports to `outputs/`

## Install

```bash
pip install -e .
```

Optional open-source inspection backend:

```bash
pip install -e ".[inspect]"
```

If ArcPy is available in the Python environment, MetaMapper will prefer it for ArcGIS datasets such as File Geodatabases and feature classes.

## Workflow

1. Inspect a dataset and generate a draft YAML file:

```bash
metamapper inspect path/to/dataset --out outputs/prefill.yaml
```

For multi-layer datasets such as File Geodatabases:

```bash
metamapper layers path/to/geodatabase.gdb
metamapper inspect path/to/geodatabase.gdb --layer MapUnitPolys --out outputs/prefill.yaml
```

2. Review and edit the generated YAML manually.

For guided completion of required fields:

```bash
metamapper missing outputs/prefill.yaml
metamapper fill outputs/prefill.yaml
```

MetaMapper intentionally leaves user-authored fields as `TODO:` placeholders where scientific interpretation or publication context is required, such as:

- abstract
- purpose
- supplemental information
- lineage/process steps
- attribute definitions
- use constraints
- publication citation details
- contact information
- distribution liability

3. Build XML:

```bash
metamapper build outputs/prefill.yaml --out outputs/metadata.xml
```

This writes:

```text
outputs/metadata.xml
```

4. Validate XML:

```bash
metamapper validate outputs/metadata.xml
```

5. Build and validate in one step:

```bash
metamapper build-validate configs/example_metadata.yml
```

If validation passes, the CLI prints:

```text
Metadata validation passed.
```

## Outputs

Validation writes:

```text
outputs/validation_report.txt
outputs/validation_summary.json
```

The JSON summary includes:

- `passed`
- `error_count`
- `warning_count`
- `missing_required_fields`
- `validation_messages`

## Guided Completion

Use `missing` to see which required fields still block XML generation:

```bash
metamapper missing outputs/prefill.yaml
```

Use `fill` to interactively complete required metadata fields:

```bash
metamapper fill outputs/prefill.yaml
```

To also prompt for long narrative fields:

```bash
metamapper fill outputs/prefill.yaml --include-long-form
```

`fill` is designed for a mixed workflow:

- by default it prompts only for short, easy fields such as originators, publication date, publisher, and status
- longer narrative fields such as abstract, purpose, and data-quality text stay in the YAML for manual editing
- `--include-long-form` enables interactive prompting for those longer fields
- pressing Enter on a prompt keeps the current value unchanged

`build` remains strict and will still refuse to generate XML if required fields are blank or still contain `TODO:` placeholders.

## External Validation

`metamapper` can run an external validation command if one is provided in the YAML under `validation.external_command`, or via the CLI option on `validate`.

The command string may use:

- `{xml_path}`
- `{output_dir}`

If no external validator is provided, `metamapper` falls back to internal structural checks inferred from the example FGDC/USGS records in this repo.

## Examples

The repo keeps the original example metadata and validation outputs under:

- `examples/published_records/`
- `examples/validation_outputs/`

These examples are used as structural references for the XML builder and validation parser, not as hard-coded templates for a single map.

## Inspection Backends

MetaMapper uses modular dataset-inspection backends:

- `ArcPy` when available, preferred for ArcGIS File Geodatabases, feature classes, aliases, and other ArcGIS-specific metadata
- open-source `pyogrio` and `rasterio` when installed
- a basic file fallback that still produces a YAML draft with file path, size, modified date, and clear warnings when GIS metadata could not be extracted

The inspection output separates:

- auto-populated dataset details under the top-level `inspection` section
- user-required metadata fields in the normal build-compatible YAML structure, marked with `TODO:` placeholders until you fill them in
