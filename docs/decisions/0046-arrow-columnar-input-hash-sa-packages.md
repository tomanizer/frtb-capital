# 46. Arrow columnar input hashes for SA package ingress

Date: 2026-06-29

## Status

Accepted

## Context

[ADR 0023](0023-arrow-tabular-handoff-boundary.md) makes Arrow an approved
handoff and adapter boundary, while calculation kernels remain NumPy/dataclass
runtime code. RRAO introduced an Arrow IPC columnar input hash for its Arrow
batch path in `638e49e`, replacing row-by-row JSON payload construction for
accepted Arrow tables.

DRC, SBM, and CVA still used row-compatible JSON hashes on their Arrow ingress
paths. That meant accepted Arrow tables were decoded into package batches and
then walked row by row to build JSON payloads before capital calculation. At
large target scales, this hashing dominated Arrow build/validation time and
reintroduced the object-allocation pattern that the Arrow ingress path is meant
to avoid.

The suite is a non-live prototype. Backwards compatibility for stored
`input_hash` values is not a constraint for this performance/audit-contract
change. Existing notebooks, fixtures, and benchmark artefacts that store Arrow
path `input_hash` values must be regenerated when they intentionally assert the
Arrow ingress hash.

## Decision

DRC, SBM, and CVA Arrow ingress paths must use an Arrow IPC columnar input hash
instead of row-JSON payload hashing.

The algorithm label is:

```text
arrow-columnar-v2
```

For a single accepted Arrow table, the hash contract is:

1. use the accepted normalized Arrow table already available at ingress;
2. build a canonical hash table by iterating the package's canonical
   `ColumnSpec` sequence;
3. for each column, combine chunks and cast in bulk to the canonical Arrow type
   implied by `TabularLogicalType` (`float64`, `int64`, `bool`, or `string`);
4. fill absent optional columns with typed null arrays of the accepted row count;
5. serialize the canonical table to an Arrow IPC stream;
6. SHA-256 the bytes prefixed by `arrow-columnar-v2` and a NUL separator.

CVA is a multi-table input. Its Arrow hash uses the same per-table IPC contract
for counterparties, netting sets, hedges, and SA-CVA sensitivities, plus a small
stable-JSON context prefix for `CvaCalculationContext`. Missing CVA entity tables
are represented by a stable absent-table sentinel so `None` and an empty accepted
table are distinct inputs.

SBM portfolio-level Arrow dispatch aggregates per-batch Arrow hashes with the
label `arrow-columnar-v2-portfolio`; it does not reconstruct row payloads across
risk-class/measure batches.

DRC preserves its prior order-insensitive position hash behavior by sorting the
canonical Arrow hash table by `position_id` and `source_row_id` before IPC
serialization. Other Arrow paths are row-order-sensitive: accepted table ordering
is part of the hash contract, and normalization/dispatch owns any stable ordering
required by that package path.

Row/dataclass ingress paths keep the existing JSON-row hash contract and use the
`json-row-v1` algorithm label.

## Affected Packages And Entry Points

| Package | Arrow entry points |
| --- | --- |
| `frtb-drc` | `build_drc_nonsec_batch_from_arrow`, `build_drc_securitisation_non_ctp_batch_from_arrow`, `build_drc_ctp_batch_from_arrow` |
| `frtb-sbm` | `build_sbm_batch_from_arrow`, `calculate_sbm_capital_from_arrow`, `calculate_sbm_portfolio_capital_from_arrow_tables` |
| `frtb-cva` | `calculate_cva_capital_from_arrow` and entity handoff builders used by that wrapper |

RRAO already uses the same single-table algorithm label. IMA is out of scope
because its audit-input hash contract is separate.

## Consequences

Positive:

- Arrow ingress no longer pays the row-JSON serialization cost for DRC, SBM, or
  CVA input hashes.
- Result audit payloads expose `input_hash_algorithm`, so callers can distinguish
  Arrow columnar hashes from row JSON hashes.
- The hash contract is tied to canonical Arrow schemas and package-owned column
  specs instead of transient Python row payload shape.

Negative:

- Stored Arrow-path `input_hash` values are intentionally invalidated.
- Tests, notebooks, and generated benchmark artefacts that asserted row/Arrow
  hash equality must assert capital equivalence plus the new algorithm label
  instead.
- Arrow IPC hashes are sensitive to canonical table ordering unless a package
  explicitly sorts the canonical hash table.

Risks to guard against:

- Do not import Arrow into capital kernels; the IPC hash adapters remain package
  adapter/assembly boundary code under ADR 0023.
- Do not use sibling package hash helpers. Each package owns its local Arrow hash
  adapter or a future shared `frtb-common` helper introduced by a separate ADR.
- Do not silently recompute row JSON hashes on Arrow paths for compatibility.

## Validation

Package tests must cover:

- a valid 64-character hex digest on Arrow ingress;
- `input_hash_algorithm == "arrow-columnar-v2"` for single-table Arrow results;
- `input_hash_algorithm == "arrow-columnar-v2-portfolio"` for SBM Arrow portfolio
  dispatch results;
- deterministic repeated hashing of the same accepted Arrow table(s);
- capital equivalence with row/dataclass paths where the capital inputs are
  otherwise identical.

Performance PRs should rerun the relevant target-scale benchmark and report the
observed Arrow batch timing and algorithm label in the PR body.

## References

- [ADR 0023](0023-arrow-tabular-handoff-boundary.md): Arrow tabular handoff boundary.
- [ADR 0033](0033-arrow-batch-and-component-summary-vocabulary.md): Arrow ingress vocabulary.
- [ADR 0045](0045-canonical-batch-pipeline-with-adapter-ingress.md): canonical batch pipeline.
- GitHub issue [#925](https://github.com/tomanizer/frtb-capital/issues/925): cross-package hash migration.
- GitHub issues [#926](https://github.com/tomanizer/frtb-capital/issues/926), [#927](https://github.com/tomanizer/frtb-capital/issues/927), and [#928](https://github.com/tomanizer/frtb-capital/issues/928): package implementation slices.
