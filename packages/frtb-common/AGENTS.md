# AGENTS.md — frtb-common

Follow the suite-level portable worktree policy in
[`../../AGENTS.md`](../../AGENTS.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

`frtb-common` owns shared primitives used across the `frtb-capital` suite.

## Scope

- Shared exception types.
- Shared status and metadata containers.
- Package-neutral Arrow tabular handoff primitives: accepted/rejected tables,
  column specs, adapter diagnostics, row ids, deterministic hashes, and
  explicit null/chunk/dictionary policies.
- Package-neutral CRIF-to-Arrow normalization helpers: column discovery,
  aliases, primitive coercion, accepted/rejected partitioning, diagnostics, and
  package-supplied RiskType mapping hooks.
- Future shared regulatory-policy, audit, calendar, sign-convention, and
  calculation-context primitives.
- Stable organisation identifier aliases and `CalculationScope` metadata for
  downstream hierarchy-aware rollups.

## Rules

- Keep this package dependency-light. Runtime dependencies beyond the standard
  library require an ADR; `pyarrow` is approved for normalized tabular handoff
  by [`ADR 0023`](../../docs/decisions/0023-arrow-tabular-handoff-boundary.md).
- Do not move IMA-local abstractions here unless the extraction is explicitly
  scoped and tested.
- Do not put SBM, DRC, RRAO, CVA, or IMA regulatory semantics in common
  handoff or CRIF primitives. Package-owned adapters supply RiskType mappings,
  then translate handoff tables into calculation-specific axes and arrays.
- Do not store hierarchy edges, traverse hierarchy graphs, or aggregate capital
  rows here. Enterprise hierarchy ownership is documented in
  [`../../docs/HIERARCHY_OWNERSHIP.md`](../../docs/HIERARCHY_OWNERSHIP.md).
- Do not import from capital component packages.
- Use frozen dataclasses and enums for public data containers.
