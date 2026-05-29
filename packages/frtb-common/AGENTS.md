# AGENTS.md — frtb-common

`frtb-common` owns shared primitives used across the `frtb-capital` suite.

## Scope

- Shared exception types.
- Shared status and metadata containers.
- Future shared regulatory-policy, audit, calendar, sign-convention, and
  calculation-context primitives.

## Rules

- Keep this package dependency-light. Runtime dependencies beyond the standard
  library require an ADR.
- Do not move IMA-local abstractions here unless the extraction is explicitly
  scoped and tested.
- Do not import from capital component packages.
- Use frozen dataclasses and enums for public data containers.
