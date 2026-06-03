# 37. Analytical Euler decomposition framework

Date: 2026-06-02

## Status

Accepted

## Context

The suite needs a unified framework to explain changes in capital and trace contributions back to individual positions or risk factors. ADR 0012 established "attribution-readiness" hooks, and DRC has already implemented a post-calculation attribution module (ADR 0031). 

However, each package currently defines its own custom attribution structure or lacks one entirely. To enable unified reporting and dashboard composition at the orchestration layer, we need to standardize the attribution contract across the monorepo.

Furthermore, we need to define the treatment for SBM curvature capital aggregation. Curvature capital applies upward and downward shocks to risk factor exposures, introducing an asymmetric non-linear component. We must establish a clear mathematical treatment for SBM curvature attribution.

## Decision

1. **Unified Attribution Type in `frtb-common`**:
   We define a common `CapitalContribution` dataclass and `AttributionMethod` enum in `frtb-common` under the `frtb_common.attribution` module. All capital packages (`frtb-drc`, `frtb-sbm`, `frtb-cva`, `frtb-rrao`, `frtb-ima`) will project their post-calculation contributions down to this shared shape.

   ```python
   @dataclass(frozen=True)
   class CapitalContribution:
       contribution_id: str
       source_id: str
       source_level: str
       bucket_key: str | None
       category: str
       base_amount: float
       marginal_multiplier: float | None
       contribution: float | None
       method: AttributionMethod | str
       residual: float = 0.0
       reason: str = ""
   ```

2. **Linear Treatment of Curvature shocks**:
   SBM Curvature capital is treated as **purely linear** within the selected shock direction (up vs down). 
   - The SBM calculation kernel determines which shock direction (up or down) is active for each curvature risk factor bucket/currency.
   - Within that selected shock direction, the curvature charge is treated as linear, allowing the analytical Euler derivative to be calculated with respect to the active direction's shock exposure.

3. **Method Categorization**:
   - `ANALYTICAL_EULER`: For stable, differentiable branches (including SBM correlation matrices and linear curvature shock directions).
   - `RESIDUAL`: For reconciling remaining category-level capital where exact analytical allocation is not applicable.
   - `UNSUPPORTED`: For non-differentiable branches (active floors, zero denominators). The capital is allocated to `residual` to ensure 100% exact numerical reconciliation.

## Consequences

**Positive**:
- Orchestration can sum and group `CapitalContribution` structures uniformly across standard approach (SA) and IMA desks.
- Asymmetry in curvature does not break analytical Euler attribution; by anchoring to the selected shock direction, SBM curvature matches the SBM delta correlation aggregation pattern.
- The monorepo has a single source of truth for attribution types.

**Negative**:
- Individual package result models must undergo minor refactorings to replace package-local contribution models (e.g., `DrcCapitalContribution`) with the unified type from `frtb-common`.
