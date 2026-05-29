# Inputs, Outputs, And Lineage

## Inputs

The public API accepts an iterable of `RraoPosition` objects and an
`RraoCalculationContext`.

Each `RraoPosition` carries:

- stable ids: `position_id`, `source_row_id`, `desk_id`, and `legal_entity`;
- numerical input: non-negative finite `gross_effective_notional` and
  `currency`;
- evidence fields: `evidence_type`, `evidence_label`, optional
  `classification_hint`, optional exclusion evidence, and optional supervisor
  directive id;
- source lineage through `RraoSourceLineage`;
- optional `RraoBackToBackMatch` for exact back-to-back exclusions;
- optional `RraoInvestmentFundDescriptor` for the U.S. NPR investment-fund
  inclusion path.

`validation.py` rejects missing lineage, duplicate ids, non-finite notionals,
unsupported classification paths, missing exclusion evidence, missing
supervisor directive ids, and invalid investment-fund descriptors.

## Outputs

`calculate_rrao_capital` returns `RraoCapitalResult` with:

- run metadata: `run_id`, `calculation_date`, `base_currency`, `profile_id`;
- deterministic `profile_hash` and `input_hash`;
- included `lines` and zero-capital `excluded_lines`;
- deterministic `subtotals` by classification, evidence type, desk, and legal
  entity;
- `total_rrao`, citations, and proposed-rule warnings where applicable.

`serialize_rrao_result` produces the deterministic JSON-compatible audit
payload used by replay tests and benchmark payload hashes.

## Lineage And Attribution Readiness

The package preserves source row ids, desk ids, legal entities, evidence ids,
classification decisions, line citations, and excluded line records. These are
the stable anchors required for downstream attribution or impact analysis under
ADR 0012 without changing the capital number.

## Optional Adapters

`crif.py` converts supported CRIF/FNet-shaped rows into canonical positions
with source column lineage, warnings, and rejected-row records. It is an adapter
boundary only; regulatory classification still occurs through canonical
evidence fields and cited rule profiles.
