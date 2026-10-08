# Metadata delivery preferences

- After generating or editing metadata, run the official Metadata Wizard
  validation when available, for both the standalone and per-entity XML records.
  Correct reported errors, rerun validation, and retain the reports. Syntax
  validation must be accompanied by checks of scientific content and source data.
- The USGS Metadata Parser (MP) is an acceptable automated FGDC validation
  alternative, but identify it explicitly rather than claiming Wizard was run.
- If the official validator is unavailable, report that clearly and distinguish
  the tool's internal structural checks from official validation. Continue
  authorized work and deliver reviewable records with the validation status.
- Keep production geodatabases and project-specific metadata outside this
  software repository. Keep reusable code, small test fixtures, and generic
  examples here. Do not relocate existing user data without an instruction to do so.
- See docs/project-workflow.md for the recommended project layout.
