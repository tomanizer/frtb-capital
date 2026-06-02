# frtb-common

Shared primitives for the `frtb-capital` workspace.

This package is intentionally small. It owns cross-package mechanics and shared
audit primitives, while capital-component packages own their regulatory
semantics and calculation batches.

Current contents:

- explicit unsupported/unimplemented exception types;
- immutable package metadata for package status;
- implementation and validation status enums;
- package-neutral standardised-component orchestration handoffs:
  - `ComponentResultHandoff` for the audited capital total, run identity,
    lineage hashes, generic counts, citations, and warnings;
  - `StandardisedComponent` identifiers for SBM, DRC, and RRAO;
  - `ComponentHandoffError` for shared field-level contract violations;
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
  - a vectorized Arrow compute path for package-supplied static RiskType mapping
    tables, with the callback-capable row path retained for compatibility;
  - deterministic accepted/rejected row partitioning with `AdapterDiagnostic`
    records;
  - package-supplied RiskType mappings or callbacks, without encoding SBM,
    DRC, RRAO, CVA, or IMA regulatory semantics in `frtb-common`.
- JSON-ready serialization with `jsonable` for common domain values such as
  enums, dates, objects exposing `as_dict`, exceptions, mappings, and
  sequences;
- regulatory citation enforcement helpers for package policy tests:
  - `assert_policy_has_regulatory_citations`;
  - `MissingRegulatoryCitationsError`.

The package performs no capital calculation. It also does not own rule-profile
semantics, capital audit records, sign conventions, business calendars, or
component regulatory parameters unless a future cross-cutting ADR explicitly
extracts those contracts into `frtb-common`.

`pyarrow` imports are limited to shared handoff and CRIF normalization mechanics
under [ADR 0023](../../docs/decisions/0023-arrow-tabular-handoff-boundary.md).
Capital kernels continue to receive package-owned typed inputs and NumPy arrays
under [ADR 0011](../../docs/decisions/0011-core-runtime-dependency-policy.md).
