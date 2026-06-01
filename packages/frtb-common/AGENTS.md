# AGENTS.md — frtb-common

`frtb-common` owns shared primitives used across the `frtb-capital` suite.

## Scope

- Shared exception types.
- Shared status and metadata containers.
- Package-neutral Arrow tabular handoff primitives: accepted/rejected tables,
  column specs, adapter diagnostics, row ids, deterministic hashes, and
  explicit null/chunk/dictionary policies.
- Future shared regulatory-policy, audit, calendar, sign-convention, and
  calculation-context primitives.

## Rules

- Keep this package dependency-light. Runtime dependencies beyond the standard
  library require an ADR; `pyarrow` is approved for normalized tabular handoff
  by [`ADR 0023`](../../docs/decisions/0023-arrow-tabular-handoff-boundary.md).
- Do not move IMA-local abstractions here unless the extraction is explicitly
  scoped and tested.
- Do not put SBM, DRC, RRAO, CVA, or IMA regulatory semantics in common
  handoff primitives. Package-owned batches translate handoff tables into
  calculation-specific axes and arrays.
- Do not import from capital component packages.
- Use frozen dataclasses and enums for public data containers.
