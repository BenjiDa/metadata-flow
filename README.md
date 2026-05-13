# metamapper

`metamapper` is a scriptable alternative to the USGS Metadata Wizard for building FGDC-style geologic metadata XML from a structured YAML file. It is not a fork of the Metadata Wizard GUI and does not depend on it.

The first version in this repo is intentionally simple and inspectable:

- read a YAML metadata file
- build FGDC/USGS-style XML
- validate the XML with internal checks or an optional external command
- write readable validation reports to `outputs/`

## Install

```bash
pip install -e .
```

## Workflow

1. Create or edit a YAML file such as `configs/example_metadata.yml`.
2. Build XML:

```bash
metamapper build configs/example_metadata.yml
```

This writes:

```text
outputs/metadata.xml
```

3. Validate XML:

```bash
metamapper validate outputs/metadata.xml
```

4. Build and validate in one step:

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
