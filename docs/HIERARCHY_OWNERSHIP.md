# Enterprise Hierarchy Ownership

This suite treats enterprise hierarchy as a result-store read model over
calculation-ready component outputs. Component kernels may preserve stable
scope identifiers, but they do not traverse hierarchy graphs, create rollups, or
query stored hierarchy metadata.

## Ownership Matrix

| Layer | Owns | Must not do |
| --- | --- | --- |
| `frtb-common` | Stable organisation identifier aliases and `CalculationScope` metadata primitives. | Store parent-child hierarchy edges, resolve hierarchy versions, or aggregate capital rows. |
| Capital component packages | Preserve supplied scope IDs on inputs, results, audit records, and lineage payloads. | Import `frtb_result_store`, traverse enterprise hierarchy, or infer missing organisation metadata. |
| `frtb-result-store` | Canonical synthetic hierarchy nodes, edges, effective-dated versions, source-row mappings, aggregate rows, detail-row read models, and API/query contracts. | Calculate capital formulae or reinterpret component regulatory semantics. |
| `frtb-orchestration` | Compose cross-framework capital and output-floor views over already resolved component totals for a selected scope. | Fetch result-store hierarchy payloads, own hierarchy metadata, or perform enterprise traversal inside component kernels. |
| Dashboard/API consumers | Call result-store or backend hierarchy contracts and render explicit `OK`, `NO_DATA`, or `UNSUPPORTED` states. | Invent hierarchy data client-side, silently zero missing rows, or recalculate capital. |

## Implementation Rules

- New hierarchy nodes, edges, effective-date windows, and fixture row mappings
  belong in `frtb-result-store`.
- New component fields should use `frtb-common.CalculationScope` or package
  adapters that serialize its stable IDs. These fields are audit metadata, not
  graph traversal instructions.
- Component package tests should prove metadata propagation at component-owned
  grains. They should not depend on result-store hierarchy fixtures.
- Result-store tests must protect stable node IDs, single-root versions,
  duplicate rejection, cycle rejection, orphan row rejection, ancestor-path
  validation, aggregate/detail reconciliation, and explicit no-data or
  unsupported query states.
- Orchestration scope views consume resolved component totals. If a future
  orchestration feature needs hierarchy lookup, the lookup belongs behind a
  result-store/backend contract and should be documented before implementation.
- Dashboard code consumes backend contracts for hierarchy rails, aggregate
  blotters, and source-row drilldown. Browser code must not synthesize
  hierarchy membership or capital totals.

## Validation Evidence

Current guardrails are intentionally split by owner:

- `packages/frtb-common/tests/test_scope.py` validates stable immutable
  `CalculationScope` identifiers without hierarchy traversal.
- `packages/frtb-common/tests/test_workspace_boundaries.py` blocks component
  imports of `frtb_result_store` and hierarchy read-model modules.
- Component package `test_*_org_scope.py` files validate metadata propagation
  on inputs, results, audit records, and batch paths.
- `packages/frtb-result-store/tests/test_org_hierarchy.py` validates hierarchy
  node contracts, row mappings, rollups, source-row drilldown, and query states.
- `packages/frtb-orchestration/tests/test_scope_views.py` validates composition
  over already resolved scope totals.

Keep this split when adding hierarchy, scope, or rollup behavior.
