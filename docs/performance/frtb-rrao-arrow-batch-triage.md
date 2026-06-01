# FRTB-RRAO Arrow Batch Triage

Issue: #300

## Scope

The RRAO high-volume path uses Arrow handoff -> package-owned NumPy batch ->
package RRAO line kernel. It preserves the row API for compatibility, but the
accepted-row path does not materialize one `RraoPosition` dataclass per input
row.

Regulatory scope is the existing package scope:

- Basel MAR23.2-MAR23.8 for residual-risk inclusion, exclusions, and 1.0% /
  0.1% add-ons.
- U.S. NPR 2.0 proposed section __.211(a)-__.211(c) for exotic exposures,
  other residual risks, investment-fund included portions, supervisor-directed
  rows, exclusions, and gross effective notional add-ons.
- EU CRR Article 325u and Delegated Regulation (EU) 2022/2328 Articles 1-3 for
  EU comparison rows already supported by `frtb-rrao`.

## Supported Data Shapes

The first batch path supports flat canonical residual-risk rows with these
axes:

- Identity and scoping: `position_id`, `source_row_id`, `desk_id`,
  `legal_entity`.
- Exposure: `gross_effective_notional`, `currency`, `notional_source`.
- Classification evidence: `evidence_type`, `evidence_label`,
  `classification_hint`.
- Exclusions: `exclusion_reason`, `exclusion_evidence_id`, plus flat
  back-to-back match ids for exact third-party back-to-back pairs.
- Supervisor-directed rows: `supervisor_directive_id`.
- Option/exclusion metadata: `underlying_count`, path-dependency and
  optionality flags.
- Investment-fund rows: flat descriptor columns for fund id, section
  __.205(e)(3)(iii) method evidence, included exposure type, fund gross
  notional, included exposure ratio, look-through flag, and mandate flag.
- Audit metadata: source system/file lineage, source hash, handoff hash,
  diagnostics, and row citations.

The batch path deliberately rejects opaque nested payload columns such as a JSON
`investment_fund_descriptor` or `back_to_back_match`. Nested regulatory evidence
must be flattened into named columns so validation can fail closed before
capital is calculated.

## Hotspots

Expected RRAO hotspots are not the arithmetic. The add-on calculation is
additive and cheap. The expensive path in high-volume ingestion is repeatedly
allocating and validating row dataclasses before classification.

The batch path addresses these hotspots:

- Adapter normalization and diagnostics run on Arrow tables and package-owned
  arrays.
- Repeated `RraoPosition` construction is avoided for accepted rows.
- Validation of required text, numeric arrays, lineage, and many evidence flags
  runs against arrays before capital lines are emitted.
- Back-to-back and investment-fund evidence are validated from typed arrays,
  without reconstructing nested row dataclasses.
- Classification and add-on construction use package reference-data lookups and
  produce the existing public `RraoCapitalLine` and `RraoSubtotal` audit
  records.
- Decision selection now precomputes classification, risk-weight key, reason
  code, and citation groups with profile-rule masks. The final row loop only
  emits the public audit lines; it no longer performs a reference-data lookup
  for each accepted position.
- Arrow handoff numeric columns are passed as NumPy arrays where possible,
  including zero-copy `float64` views for required gross effective notional
  columns. Object and dictionary text columns are converted chunk-wise without
  routing the whole column through `to_pylist()`.

Output capital lines are still materialized because they are the public audit
surface. The performance target is to remove accepted input-row dataclass churn,
not to hide line-level audit output.

## Architecture Rationale

Using a package-owned batch keeps the regulatory rules visible in RRAO code:
classification still flows through explicit evidence, exclusion, investment
fund, risk-weight, and citation lookups. Arrow is the handoff format, not the
calculation language. NumPy arrays provide stable, typed columns for the hot
path while preserving deterministic result records and existing reconciliation
checks.

This is preferable to embedding RRAO rules in dataframe expressions because the
decision points are regulatory branches, not generic aggregations. The code
continues to name the rule-level concepts from Basel MAR23.2-MAR23.8, U.S. NPR
2.0 proposed section __.211, and EU Article 325u / Delegated Regulation (EU)
2022/2328 directly.

## Validation Evidence

The batch implementation is covered by `packages/frtb-rrao/tests/test_rrao_arrow_batch.py`.
The tests assert:

- row-built batches preserve the existing row input hash;
- Arrow handoff batches reconcile with the existing RRAO v1 fixture for lines,
  excluded lines, subtotals, total, source row ids, and citations;
- investment-fund rows reconcile against the row API;
- high-volume synthetic batches report zero accepted-row `RraoPosition`
  materialization;
- handoff diagnostics are preserved; and
- opaque nested payloads fail closed instead of falling back to row
  materialization.

Issue #317 added vectorization-specific evidence:

- required Arrow `float64` gross effective notional handoff uses a zero-copy
  NumPy view where Arrow permits it;
- chunked dictionary-encoded text columns are accepted deterministically;
- `copy_arrays=False` does not freeze caller-owned NumPy arrays;
- profile evidence-rule lookup is mask-based rather than per-row; and
- the benchmark reports row, column-batch, and Arrow-batch timings, exact total
  deltas, ordering hashes, and accepted-row dataclass counts.

The 2026-06-01 target-scale run on 100,000 synthetic rows reported row
calculation at 10.731 seconds, column-batch calculation at 3.522 seconds, and
Arrow-batch calculation at 3.820 seconds. Column-batch and Arrow-batch total
capital deltas were both 0.0, and both high-performance paths materialized 0
accepted input-row dataclasses.
