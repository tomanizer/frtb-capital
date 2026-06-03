# 39. Orchestration suite capital aggregation

Date: 2026-06-03

## Status

Accepted

## Context

ADR 0018 deferred firm-level `calculate_suite_capital` to a post-M1 milestone.
ADR 0032 delivered SA arithmetic (`SBM + DRC + RRAO`) and structural IMA
fallback route recording but left top-of-house aggregation out of scope.

The orchestration package now implements `calculate_suite_capital` in
`frtb_orchestration.suite`. It aggregates pre-computed component summaries
(`ImaCapitalSummary`, `StandardisedApproachCapitalResult`, `CvaCapitalSummary`)
with cross-component validation of calculation date, base currency, and
regulatory jurisdiction family. Package metadata reports
`ImplementationStatus.IMPLEMENTED` for the orchestration entrypoint, and
`test_suite_capital.py` provides end-to-end reconciliation evidence.

Documentation and older ADRs still described suite aggregation as
unimplemented, which misled integrators and agent briefs.

## Decision

`frtb-orchestration` owns additive top-of-house suite capital:

```text
Suite capital = IMA capital + SA capital + CVA capital
```

where SA capital is the composed `SBM + DRC + RRAO` total from
`compose_standardised_approach_capital` or an equivalent
`StandardisedApproachCapitalResult`.

Before addition, `calculate_suite_capital` validates:

- all three summaries are present and correctly typed;
- `calculation_date` and `base_currency` match across components;
- `profile_id` values map to one suite jurisdiction family via
  `suite_jurisdiction_family` (ADR 0022 family guard extended to IMA and CVA);
- component totals are non-negative where required.

The result is a frozen `SuiteCapitalResult` with reconciled subtotals.
`SuiteCapitalResult.__post_init__` enforces
`total_capital == ima + sa + cva` within numerical tolerance.

This step performs static composition only. MAR10.1 multipliers, 60-day
look-back floors, and desk-level SA fallback capital calculation remain in the
owning component packages or upstream runners; orchestration does not apply
those adjustments here.

Runtime production modules continue to consume public handoff or summary
contracts only. They must not import sibling capital package internals.

## Consequences

- ADR 0018 M2 suite-aggregation scope is delivered for the summary-handoff
  path documented in `docs/modules/frtb-orchestration/README.md`.
- ADR 0032 statement that `calculate_suite_capital` remains out of scope is
  superseded by this ADR for aggregation behaviour; ADR 0032 SA arithmetic
  remains valid.
- Package README, AGENTS/CLAUDE briefs, and `docs/ARCHITECTURE.md` must describe
  implemented suite aggregation, not scaffold-only behaviour.
- Cross-component floors, consolidated audit-log emission, and manifest-driven
  end-to-end suite runs may still evolve in follow-on work without reopening
  the additive composition contract.
- Material changes to jurisdiction-family maps or reconciliation tolerances
  require deterministic tests and follow ADR 0005.

## References

- [`packages/frtb-orchestration/src/frtb_orchestration/suite.py`](../../packages/frtb-orchestration/src/frtb_orchestration/suite.py)
- [`docs/modules/frtb-orchestration/README.md`](../modules/frtb-orchestration/README.md)
- [ADR 0018](0018-suite-orchestration-contract-milestone.md)
- [ADR 0032](0032-orchestration-sa-arithmetic-and-fallback-routing.md)
- [ADR 0022](0022-sa-jurisdiction-profile-consistency-guard.md)