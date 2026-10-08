# Project organization and validation

Use one installed copy of MetaMapper for multiple map projects. Keep production
datasets and their scientific metadata together in project folders, separate
from the software checkout:

```text
Code/Current/metadata-flow/       reusable software, tests, generic examples
Geology/Projects/
  Healdsburg/
    source/                     original geodatabase snapshots and references
    working/                    actively edited geodatabase
    metadata/
      project.yaml              citation, scientific narrative, methods, contacts
      feature_metadata/         individual entity XML/YAML records
    qa/                         boundary audits and validation reports
    deliverables/               dated release packages
  Another-map/
    ...
```

Preserve original snapshots before editing. Run the metadata tool against a
specific working snapshot using its path; it does not need to be copied into
the software repository. Keep editable YAML and generated metadata in the map
project. Maintain the narrative in YAML, then regenerate XML, to avoid separate
copies diverging. Project-specific scripts and profiles belong to that project;
reusable behavior belongs in MetaMapper.

Use a project Git repository for small text artifacts such as metadata YAML,
scripts, citations, and QA summaries when useful. Ignore binary geodatabases,
temporary ArcGIS files, and bulk generated products. Back up geodatabases and
dated snapshots separately; Git is not their backup system. Keep each final
release package together with its source snapshot identifier, tool version or
Git commit, validator version, and validation reports.

The intended delivery sequence is:

1. Inspect the chosen database snapshot and audit geographic bounds and schema.
2. Complete the scientific narrative and documented publication facts in YAML.
3. Generate standalone and per-entity XML records.
4. Run official Metadata Wizard validation on every record; correct errors and
   repeat. For automation, USGS MP is an alternative and must be identified by name.
5. Review the scientific content and consistency with the data independently
   of syntax validation, then assemble the dated deliverables and QA reports.

MetaMapper currently has an external-command validation hook in `validate` and
`build-validate`, configured by `validation.external_command` and optionally
`validation.report_path`. It does not yet have a dedicated Metadata Wizard
adapter, and the Healdsburg-specific export script currently performs only
internal structural checks. Official validation therefore needs an installed
validator or a separate documented Wizard run; internal passes must not be
reported as official validation.

Official references:

- [Metadata Wizard validation](https://doi-usgs.github.io/fort-pymdwizard/usage/Validating%20a%20Record.html)
- [USGS metadata review](https://www.usgs.gov/data-management/metadata-review)
- [USGS Metadata Parser](https://geology.usgs.gov/tools/metadata/tools/doc/mp.html)
