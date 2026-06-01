# frtb-common

Shared primitives for the `frtb-capital` workspace.

This package is intentionally small. It owns cross-package mechanics and shared
audit primitives, while capital-component packages own their regulatory
semantics and calculation batches.

Current contents:

- explicit unsupported/unimplemented exception types;
- immutable package metadata for scaffold status;
- implementation and validation status enums.
- Arrow-backed normalized tabular handoff primitives:
  - `ColumnSpec`, aliases, package-neutral logical types, null/chunk/dictionary
    policies;
  - `NormalizedTabularHandoff` for accepted/rejected Arrow tables, adapter
    diagnostics, row id column naming, metadata, and source hashes;
  - deterministic source, Arrow table, and normalized handoff hashes;
  - dictionary-code extraction and deterministic Arrow table sorting helpers.
- CRIF-to-Arrow normalization helpers:
  - package-neutral CRIF column discovery, alias normalization, and primitive
    coercion;
  - deterministic accepted/rejected row partitioning with `AdapterDiagnostic`
    records;
  - package-supplied RiskType mappings or callbacks, without encoding SBM,
    DRC, RRAO, CVA, or IMA regulatory semantics in `frtb-common`.

The package performs no capital calculation.
