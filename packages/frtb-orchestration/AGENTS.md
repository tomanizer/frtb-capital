# AGENTS.md — frtb-orchestration

Follow the suite-level portable worktree policy in
[`../../AGENTS.md`](../../AGENTS.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

`frtb-orchestration` owns suite-level aggregation and routing.

## Current status

The package implements orchestration contracts end to end:

- SA composition consumes `frtb_common.ComponentCapitalSummary` from package-owned
  SBM, DRC, and RRAO adapters, validates component slots and jurisdiction
  families plus run-context consistency, and returns the additive
  `SBM + DRC + RRAO` result.
- IMA fallback route recording accepts structural desk eligibility signals and
  records `SA_FALLBACK` desks as routed to the Standardised Approach stack.
- `recognise_cva_summary` and `recognise_ima_summary` project public component
  results into `CvaCapitalSummary` and `ImaCapitalSummary`.
- `calculate_suite_capital` aggregates `IMA + SA + CVA` with cross-component
  date, currency, and jurisdiction-family validation (ADR 0039).

## Rules

- May declare dependencies on `frtb-common` and capital component packages, but
  runtime source must not import sibling capital packages unless a future ADR
  changes the boundary.
- Owns SA composition from `frtb-sbm + frtb-drc + frtb-rrao`.
- Owns top-of-house suite aggregation from component summaries.
- Owns fallback routing when IMA eligibility fails.
- Do not emit successful placeholder capital.
- Do not reach into private component batch modules; consume public input_table or
  result-summary contracts only.
- May compose scenario/shock/surface evidence views over resolved artifact IDs,
  but must not import `frtb_result_store`, fetch artifact payloads, or infer
  artifact semantics. Result-store and Navigator layers own storage/query/UI
  behavior for artifact metadata.
- May compose scope-aware capital and output-floor views over already resolved
  component totals, but must not own enterprise hierarchy metadata, traverse
  hierarchy graphs, or import `frtb_result_store`. See
  [`../../docs/HIERARCHY_OWNERSHIP.md`](../../docs/HIERARCHY_OWNERSHIP.md).
