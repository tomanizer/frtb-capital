# frtb-common

Shared primitives for the `frtb-capital` workspace.

This package is intentionally small. It owns cross-package mechanics and shared
audit primitives, while capital-component packages own their regulatory
semantics and calculation batches.

Current contents:

- explicit unsupported/unimplemented exception types;
- shared attribution and impact contracts:
  [`ATTRIBUTION.md`](ATTRIBUTION.md);
- immutable package metadata for package status;
- implementation and validation status enums;
- package-neutral standardised-component summaries:
  - `ComponentCapitalSummary` for the audited capital total, run identity,
    lineage hashes, generic counts, citations, and warnings;
  - `StandardisedComponent` identifiers for SBM, DRC, and RRAO;
  - `ComponentSummaryError` for shared field-level contract violations;
- package-neutral organisation and calculation-scope metadata:
  - stable identifier aliases for legal entities, business divisions, business
    lines, desks, Volcker desks, books, trading books, portfolios, hierarchy
    nodes, and model-approval scopes;
  - `CalculationScopeLevel` and frozen `CalculationScope` for carrying the
    selected scope on package inputs, outputs, and audit records without
    hierarchy traversal or rollup logic;
- risk-factor metadata carrier primitives:
  - `RiskFactorId`, `RiskFactorMappingVersion`, and `RiskFactorLineageId`
    for stable cross-package identifiers and mapping provenance;
  - `RiskFactorRiskClassCode`, `RiskFactorTypeCode`, `SensitivityTypeCode`,
    `BucketId`, `Tenor`, and `CurrencyCode` for calculation-ready metadata
    values supplied by the owning taxonomy, result-store snapshot, or upstream
    adapter;
  - these are immutable value primitives, not a canonical risk-factor master,
    RFET evidence store, regulatory mapping table, or frontend classification
    mechanism.
- Arrow-backed normalized tabular primitives:
  - `ColumnSpec`, aliases, package-neutral logical types, null/chunk/dictionary
    policies;
  - `NormalizedArrowTable` for accepted/rejected Arrow tables, adapter
    diagnostics, row id column naming, metadata, and source hashes;
  - deterministic source, Arrow table, and normalized Arrow-table hashes;
  - dictionary-code extraction and deterministic Arrow table sorting helpers;
  - schema export helpers in `frtb_common.arrow_table_schema`:
    `column_spec_to_json_schema`, `column_specs_to_json_schema`, and
    `column_specs_to_arrow_schema`.
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
- deterministic JSON hashing with `stable_json_hash` for package-neutral
  payloads, plus SHA-256 validation helpers;
- regulatory citation enforcement helpers for package policy tests:
  - `assert_policy_has_regulatory_citations`;
  - `MissingRegulatoryCitationsError`.

The package performs no capital calculation. It also does not own enterprise
hierarchy traversal, top-of-house rollups, rule-profile semantics, capital audit
records, sign conventions, business calendars, or component regulatory
parameters unless a future cross-cutting ADR explicitly extracts those contracts
into `frtb-common`.

ADR 0033 M3 removed the old `*Handoff*`, `*_HANDOFF_COLUMN_SPECS`, and
`*_from_handoff` public names. Use the Arrow table and component summary names
listed above.

`pyarrow` imports are limited to shared Arrow-ingest and CRIF normalization mechanics
under [ADR 0023](../../docs/decisions/0023-arrow-tabular-handoff-boundary.md).
Capital kernels continue to receive package-owned typed inputs and NumPy arrays
under [ADR 0011](../../docs/decisions/0011-core-runtime-dependency-policy.md).

## Arrow Schema Export

Clients can generate JSON Schema or Arrow schema descriptions from public
`ColumnSpec` tuples without importing component packages from `frtb-common`:

```bash
uv run python scripts/export_arrow_schema.py \
  --package frtb_drc \
  --spec DRC_NONSEC_ARROW_COLUMN_SPECS \
  --format json-schema \
  --output dist/schemas/drc_nonsec.arrow.schema.json
```

The library functions live in `frtb_common.arrow_table_schema`; the CLI dynamically
imports the requested package or module so dependency direction remains
package-neutral.
