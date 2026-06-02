# frtb-cva decisions and implementation plan

This document records the historical v1 implementation plan and current
remaining boundaries. The Basel MAR50 partial-runtime path now includes reduced
and full BA-CVA, supported SA-CVA delta/vega paths, mixed carve-out,
qualified-index routing, adapters, attribution, impact, performance controls,
and audit/replay evidence. U.S., EU, and UK comparison profiles and the MAR50.9
materiality-threshold alternative remain fail-closed.

## Decision log

### CVA-DEC-001: Implement reduced BA-CVA first

**Decision:** The first capital-producing implementation slice will support
reduced BA-CVA only.

**Reason:** Reduced BA-CVA provides the smallest cited end-to-end path using
counterparty/netting-set EAD inputs only. It establishes profile lookup, audit,
and public API patterns before SA-CVA sensitivities and hedge mechanics.

**Implication:** SA-CVA, full BA-CVA, mixed carve-out, and materiality-threshold
alternative requests must raise explicit unsupported-feature errors until their
slices land.

**Current status:** Reduced BA-CVA, full BA-CVA, SA-CVA, and mixed carve-out
slices have landed for supported Basel MAR50 inputs. MAR50.9 still fails
closed.

Basel anchor: MAR50.13(2), MAR50.14–MAR50.16.

### CVA-DEC-002: Keep data contracts and rule profiles package-local initially

**Decision:** CVA-specific dataclasses, enums, citations, and rule profiles start
in `frtb_cva.data_models`, `frtb_cva.regimes`, and `frtb_cva.reference_data`.

**Reason:** `frtb-common` is still a small scaffold. Moving CVA counterparty,
netting-set, hedge, and SA-CVA sensitivity types into common would prematurely
couple future package design to CVA internals.

**Implication:** Only truly shared primitives, such as unsupported-feature
exceptions and future generic rule-profile identity, should move to
`frtb-common` under a separate cross-cutting ADR if needed. The PRD reference to
profiles "supplied through `frtb-common`" is superseded by this decision for v1.

### CVA-DEC-003: Profiles own parameters; kernels receive typed values

**Decision:** Risk weights, correlations, hedge eligibility rules, α, ρ, β, `R`,
`m_CVA`, `D_BA-CVA`, and supported-feature switches belong in versioned rule
profiles and reference-data helpers. Calculation kernels receive typed values and
do not branch on global regime names.

**Reason:** This matches the DRC/SBM documentation pattern and keeps regulatory
traceability separate from numeric code.

**Implication:** Tests must cover profile lookup separately from calculations.

### CVA-DEC-004: SA-CVA sensitivities are portfolio-aggregate inputs

**Decision:** SA-CVA capital consumes portfolio-level aggregate sensitivities per
risk factor `k`, not counterparty-level sensitivity rows.

**Reason:** Basel MAR50.47 defines sensitivities of the aggregate CVA and of the
market value of all eligible hedges in the CVA portfolio.

**Implication:** `SaCvaSensitivity` records represent portfolio-factor
contributions. Upstream systems aggregate counterparty/trade sensitivities before
the capital boundary, or adapters sum rows sharing the same portfolio
risk-factor key.

### CVA-DEC-005: Positive regulatory CVA sign with minus-sign hedge netting

**Decision:** Under the default positive regulatory CVA convention (MAR50.32(1)),
net weighted sensitivity is `WS_k = WS_k^CVA − WS_k^Hdg`.

**Reason:** MAR50.52 and its footnote require a minus sign so positive CVA and
positive hedge sensitivities offset when buying protection.

**Implication:** Fixtures must include a hedge-offset case that fails if the sign
is implemented incorrectly. Negative-loss CVA conventions are unsupported unless
a future profile cites and tests an explicit alternative.

### CVA-DEC-006: Sum duplicate portfolio risk-factor rows before weighting

**Decision:** Multiple canonical sensitivity rows sharing the same portfolio
risk-factor key are summed deterministically before weighting and aggregation.

**Reason:** Adapters and upstream systems may emit one row per desk, legal
entity, or source system for the same factor `k`. Rejecting duplicates would be
overly brittle; silent last-row-wins would be non-auditable.

**Implication:** The portfolio risk-factor key definition must be documented per
risk class in [ARCHITECTURE_AND_DATA_DESIGN.md](ARCHITECTURE_AND_DATA_DESIGN.md).
Tests must cover duplicate-key summation and conflicting sign handling.

### CVA-DEC-007: Hedge benefit is never implicit

**Decision:** BA-CVA and SA-CVA hedge capital benefit is applied only when hedge
eligibility is explicitly recorded with evidence, citation ids, and method-specific
checks.

**Reason:** Workspace review standards and MAR50.10–MAR50.11, MAR50.37–MAR50.39
require explicit eligible-hedge treatment.

**Implication:** Ineligible hedges produce zero benefit with cited rejection
records; they are never silently dropped.

### CVA-DEC-008: Audit graph before attribution

**Decision:** The implementation provides deterministic counterparty,
netting-set, bucket, and risk-class explain records with attribution-ready
lineage. Analytical Euler allocation remains explicit about nonlinear residuals;
baseline-vs-candidate impact is outside the capital kernel.

**Reason:** SA-CVA nonlinearities (square roots, `S_b` floor/cap, hedge
disallowance, BA-CVA hedge floor) require stable branch metadata before
attribution can be trusted.

**Implication:** Runtime paths must retain stable ids from input through total
result. Attribution reports unsupported nonlinear branches rather than silently
reallocating them. See
[ADR 0012](../../decisions/0012-capital-impact-attribution.md).

### CVA-DEC-009: Non-IMM discount factor is profile-computable

**Decision:** Non-IMM netting sets may supply `discount_factor` explicitly or
allow the profile helper to compute
`DF = (1 - exp(-0.05 * M)) / (0.05 * M)` from effective maturity.

**Reason:** MAR50.15(4) defines the supervisory discount factor for banks not
using IMM.

**Implication:** Audit records must show whether DF was supplied or computed and
the maturity input used.

### CVA-DEC-010: Vega risk weights require explicit volatility inputs

**Decision:** Where MAR50 prescribes `RW_k = RW_σ · σ_k`, upstream inputs must
supply `σ_k` on sensitivity rows or profile-permitted defaults. Kernels must not
infer volatilities from trade metadata.

**Reason:** Vega scaling depends on current market volatility inputs that belong
to upstream CVA/sensitivity engines.

**Implication:** Missing required `σ_k` for supported vega paths fails validation.

### CVA-DEC-011: Issue sequence supersedes PRD delivery slice ordering

**Decision:** The [ISSUE_BREAKDOWN.md](ISSUE_BREAKDOWN.md) sequence governs v1
implementation order. Hedge eligibility is implemented after the first BA-CVA
capital slice even though the PRD lists hedges earlier.

**Reason:** Reduced BA-CVA can be validated without hedge benefit. Hedge
contracts are still required before SA-CVA and full BA-CVA capital paths.

**Implication:** Update planning docs together when issue order changes.

## Implemented sequence

1. Complete traceability skeleton, architecture docs, and requirements registry
   alignment.
2. Implement data models and validation.
3. Implement Basel MAR50 rule profile and reference data for reduced BA-CVA plus
   first SA-CVA GIRR delta tables.
4. Implement scope and method routing.
5. Implement BA-CVA stand-alone and reduced portfolio capital.
6. Wire public API, audit, and reduced BA-CVA fixture.
7. Implement hedge eligibility contracts.
8. Implement SA-CVA weighting and shared aggregation engine.
9. Deliver SA-CVA GIRR delta public slice and fixture.
10. Add remaining SA-CVA risk classes incrementally, including deferred vega
    paths where issues specify delta-first delivery.
11. Implement full BA-CVA, qualified-index option, and mixed carve-out assembly.
12. Add CRIF adapter, orchestration handoff, performance controls, and
    attribution/impact.

## Profile roadmap

| Profile id | Status in v1 | Notes |
| --- | --- | --- |
| `BASEL_MAR50_2020` | Capital-producing partial runtime | July 2020 calibration: `m_CVA = 1.0`, `D_BA-CVA = 0.65`; MAR50.9 remains unsupported. |
| `US_NPR20_VB` | Fail closed | Requires proposed section map before implementation |
| `EU_CRR3_CVA` | Fail closed | Articles 382–386 mapping deferred |
| `UK_PRA_CVA` | Fail closed | Crosswalk placeholder only today |

## Open items for later ADRs

- Moving generic citation/profile identity types to `frtb-common`.
- Extracting shared SA-CVA aggregation primitives if SBM and CVA convergence is
  justified without sibling imports.
- Materiality-threshold 100% CCR alternative (MAR50.9) if orchestration needs a
  supported path beyond fail-closed gates.
