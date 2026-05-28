# 3. SA, DRC, and CVA scope as separate packages within the suite

Date: 2026-05-28

## Status

Accepted

## Context

The Standardized Approach (SA), Default Risk Charge (DRC), and Credit Valuation Adjustment (CVA) capital charges are architecturally distinct from the Internal Models Approach (IMA):

- **SA** is sensitivity-based (delta, vega, curvature aggregated by buckets) — fundamentally different from IMA's scenario-based expected shortfall.
- **DRC** is jump-to-default-based (issuer exposures, hedging benefit, bucket aggregation) — a separate calculation paradigm.
- **CVA** uses counterparty exposures and credit spreads — yet another input domain.

Each requires a distinct upstream data contract: SA needs trade-level sensitivities, DRC needs issuer-level JTD, CVA needs counterparty-level exposures. None of these fit the `ScenarioCube` / `RiskFactorDefinition` contracts that IMA consumes.

Adding any of these to `frtb-ima` would make the package name a misnomer and conflate four distinct models into one codebase.

## Decision

Each of SA, DRC, and CVA will be a **separate package** inside this monorepo (`packages/frtb-sa/`, `packages/frtb-drc/`, `packages/frtb-cva/`), not part of `frtb-ima`. Each will:

- Have its own `pyproject.toml`, version, tests, and model documentation pack.
- Use the same shared abstractions from `frtb-common` (audit records, regulatory policy framework, sign conventions, business calendar).
- Follow the same suite-level style and review standards.
- Be independently validated under SR 11-7 / PRA SS 1/23.

Firm-level aggregation and floors that compare across charges (e.g. IMA capital vs SA floor, redesignation add-ons) live in `frtb-orchestration`, not in any individual capital package.

## Consequences

**Positive:**

- Clear model boundary per SR 11-7.
- Each package can be staffed, validated, and released independently.
- No conceptual contamination between the four calculation paradigms.

**Negative:**

- Five packages to maintain in parallel.
- Inter-package consistency must be enforced via the workspace standards (CLAUDE.md, AGENTS.md, ADRs).

## References

- `tomanizer/FRTB-IMA` audit issue #31.
- ADR 0002: monorepo structure.
- `docs/ARCHITECTURE.md`.
