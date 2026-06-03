# 29. Unified standardised-component orchestration handoff contract

Date: 2026-06-02

## Status

Accepted

Vocabulary note: ADR 0033 supersedes this ADR's public "handoff" wording with
the canonical component summary vocabulary (`ComponentCapitalSummary`,
`ComponentSummaryError`, `to_component_summary`, and orchestration
`*_summary` keywords). The composition contract and package-boundary semantics
in this ADR are unchanged.

SA arithmetic availability statements in this ADR are historical. Additive SA
composition and structural IMA fallback route recording are implemented by
[ADR 0032](0032-orchestration-sa-arithmetic-and-fallback-routing.md).

## Context

ADR 0018 made deterministic component handoff and SA composition the next
orchestration milestone (M1). The handoff mechanism that emerged was
inconsistent across the three Standardised Approach components:

- `frtb-sbm` owned a projection adapter `to_orchestration_handoff` that produced
  a package-local `SbmOrchestrationHandoff` (because the raw `SbmCapitalResult`
  exposes `total_capital`, not an SA-specific total).
- `frtb-drc` and `frtb-rrao` had no adapter. Orchestration's `recognise_drc_result`
  and `recognise_rrao_result` reached directly into the raw `DrcCapitalResult` /
  `RraoCapitalResult` internals (e.g. `categories`, `lines`, `excluded_lines`).
- Orchestration carried its own `ComponentResultHandoff` and `StandardisedComponent`
  types plus duck-typing `recognise_*` helpers that structurally validated
  arbitrary objects.

This coupled orchestration to component-internal result fields that the owning
packages are free to refactor, made SBM the odd component out, and split the
handoff contract across four locations.

## Decision

Adopt a single, package-neutral handoff contract owned by `frtb-common`.

1. **`frtb_common.ComponentResultHandoff`** (frozen dataclass) is the only shape
   orchestration consumes for SA composition. It carries audited identity
   (`run_id`, `calculation_date`, `base_currency`, `profile_id`), the additive
   `total_capital`, lineage hashes (`profile_hash`, `input_hash`), generic
   counts (`line_count`, `excluded_line_count`, `subtotal_count`), `citations`,
   and `warnings`. Field-level invariants are enforced in `__post_init__` and
   raise `frtb_common.ComponentHandoffError`. `frtb_common.StandardisedComponent`
   (SBM/DRC/RRAO) identifies the producing component.

2. **Each SA component owns its projection.** `frtb-sbm`, `frtb-drc`, and
   `frtb-rrao` each expose `to_orchestration_handoff(result) -> ComponentResultHandoff`.
   Components depend only on `frtb-common`; the layering contract is preserved.

3. **Orchestration consumes only the typed handoff (hard cut).** The duck-typing
   `recognise_sbm_result` / `recognise_drc_result` / `recognise_rrao_result`
   helpers are removed. `compose_standardised_approach_capital` now takes
   `sbm_handoff` / `drc_handoff` / `rrao_handoff` of type
   `ComponentResultHandoff | None`, validates that each handoff sits in its
   expected component slot, then applies the jurisdiction-family guard (ADR 0022)
   before the missing-component and not-yet-implemented checks.

This **supersedes the recognise-based handoff mechanism** described in the
ADR 0018 M1 inputs table. The M1a/M1b/M1c/M2 milestone sequencing is unchanged;
this ADR only fixes the contract those milestones build on.

## Consequences

- `frtb-common` gains a small, stable, neutral type shared by every SA component
  and orchestration. This is the only home that avoids reversing the dependency
  direction (components must not import orchestration).
- `frtb-sbm`'s package-local `SbmOrchestrationHandoff` is removed. It was never
  in the package's public `__all__`; one SBM test that asserted on the handoff
  view was updated, and a test that imported `recognise_sbm_result` from
  orchestration (a reverse-layer coupling) no longer does so.
- Orchestration runtime imports no sibling capital package. The runtime
  import-guard test is extended to also forbid `frtb_ima`, so future IMA handoff
  recognition stays structural rather than importing IMA internals.
- **No numerical outputs change** from the handoff rename alone. SA aggregation
  arithmetic is delivered in
  [ADR 0032](0032-orchestration-sa-arithmetic-and-fallback-routing.md); suite
  aggregation is delivered in
  [ADR 0039](0039-orchestration-suite-capital-aggregation.md).

## References

- [`docs/decisions/0018-suite-orchestration-contract-milestone.md`](0018-suite-orchestration-contract-milestone.md)
- [`docs/decisions/0010-standardised-approach-component-taxonomy.md`](0010-standardised-approach-component-taxonomy.md)
- [`docs/decisions/0022-sa-jurisdiction-profile-consistency-guard.md`](0022-sa-jurisdiction-profile-consistency-guard.md)
- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
