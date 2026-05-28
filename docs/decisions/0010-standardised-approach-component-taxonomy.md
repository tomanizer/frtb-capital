# 10. Standardised Approach component taxonomy

Date: 2026-05-28

## Status

Accepted

## Context

Basel MAR20.4 defines the standardised approach capital requirement as the sum
of the sensitivities-based method, default risk charge, and residual risk add-on.
The earlier suite architecture used a single planned SA package name. That name
is too coarse for implementation: SBM, DRC, and RRAO have different input
contracts, formula families, validation evidence, and audit surfaces.

The repo also briefly introduced an SA-prefixed SBM component name in planning
docs. That name duplicates the `SA` composition label inside the component name
and makes cross-document navigation harder.

## Decision

`SA` is a regulatory approach and composition label, not a standalone package.
The implementation packages are:

- `frtb-sbm`: sensitivities-based method, covering delta, vega, curvature,
  bucket aggregation, correlation scenarios, and SBM audit output.
- `frtb-drc`: default risk charge for non-securitisation, securitisation
  non-CTP, and correlation trading portfolio default risk.
- `frtb-rrao`: residual risk add-on for exotic and other residual risks.

The composed SA total is:

```text
SA capital = SBM capital + DRC capital + RRAO capital
```

`frtb-orchestration` owns that composition and any IMA fallback routing. If an
IMA desk is not eligible for models-based treatment, `frtb-ima` emits the
eligibility signal and orchestration routes the desk to the SA component stack.
No individual SA component imports another SA component.

The canonical component name is `frtb-sbm`.

## Consequences

**Positive:**

- The package taxonomy matches the regulatory formula and the different input
  domains of SBM, DRC, and RRAO.
- The IMA package stays focused on models-based capital and a fallback handoff
  signal.
- The orchestration package has a clear role: compose SA, compare/reroute IMA
  fallback, and aggregate top-of-the-house capital.
- Each SA component can have its own model documentation pack, validation
  evidence, fixtures, and release cadence.

**Negative:**

- There are more planned packages to maintain.
- Cross-component consistency must be actively managed through `frtb-common`,
  ADRs, and documentation checks.
- Historical references to obsolete standalone-SA and SA-prefixed-SBM names
  need cleanup or explicit supersession notes.

## References

- Basel Framework MAR20.4 standardised approach composition.
- [ADR 0002](0002-monorepo-structure.md): monorepo structure.
- [ADR 0003](0003-sa-drc-cva-scope.md): original separation of SA, DRC, and
  CVA from IMA, superseded here for the SA package taxonomy.
- `tomanizer/frtb-capital` issue #46.
