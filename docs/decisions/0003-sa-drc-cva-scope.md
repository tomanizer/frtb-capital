# 3. SA component stack and CVA scope within the suite

Date: 2026-05-28

## Status

Accepted; partly superseded by
[ADR 0010](0010-standardised-approach-component-taxonomy.md) for the Standardised
Approach package taxonomy.

## Context

The Standardized Approach (SA), including SBM, DRC, and RRAO, and Credit Valuation Adjustment (CVA) are architecturally distinct from the Internal Models Approach (IMA):

- **SBM** is sensitivity-based (delta, vega, curvature aggregated by buckets) — fundamentally different from IMA's scenario-based expected shortfall.
- **DRC** is jump-to-default-based (issuer exposures, hedging benefit, bucket aggregation) — a separate calculation paradigm within the SA stack.
- **RRAO** is a residual-risk add-on for positions with exotic or other residual risks.
- **CVA** uses counterparty exposures and credit spreads — yet another input domain.

Each requires a distinct upstream data contract: SBM needs trade-level sensitivities, DRC needs issuer-level JTD, RRAO needs residual-risk classifications and gross notionals, and CVA needs counterparty-level exposures. None of these fit the `ScenarioCube` / `RiskFactorDefinition` contracts that IMA consumes.

Adding any of these to `frtb-ima` would make the package name a misnomer and conflate four distinct models into one codebase.

## Decision

Each of SA, DRC, and CVA was originally expected to be a separate package inside
this monorepo, not part of `frtb-ima`. ADR 0010 refines the SA side of this
decision: `SA` is now treated as a composition label implemented by
`packages/frtb-sbm/`, `packages/frtb-drc/`, and `packages/frtb-rrao/`, while
`packages/frtb-cva/` remains a separate planned package. Each package will:

- Have its own `pyproject.toml`, version, tests, and model documentation pack.
- Use the same shared abstractions from `frtb-common` (audit records, regulatory policy framework, sign conventions, business calendar).
- Follow the same suite-level style and review standards.
- Be independently validated under SR 11-7 / PRA SS 1/23.

Firm-level aggregation and floors that compare across charges (e.g. IMA capital vs SA floor, redesignation add-ons) live in `frtb-orchestration`, not in any individual capital package.

## Consequences

**Positive:**

- Clear model boundary per SR 11-7.
- Each package can be staffed, validated, and released independently.
- No conceptual contamination between the separate calculation paradigms.

**Negative:**

- Five packages to maintain in parallel.
- Inter-package consistency must be enforced via the workspace standards (CLAUDE.md, AGENTS.md, ADRs).

## References

- `tomanizer/frtb-capital` audit issue #1 (transferred from
  `tomanizer/FRTB-IMA` audit issue #31).
- ADR 0002: monorepo structure.
- ADR 0010: standardised approach component taxonomy.
- `docs/ARCHITECTURE.md`.
