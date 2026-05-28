# Conceptual Soundness

## Model Design

The package separates upstream risk generation from capital assembly. Upstream
systems are responsible for market data, trade valuation, scenario generation,
and stress-artifact production. `frtb-ima` consumes validated inputs and applies
transparent, deterministic capital calculations with explicit audit records.

This split is conceptually appropriate for an IMA prototype because Basel
MAR31-MAR33 and the U.S. NPR 2.0 proposed market-risk framework distinguish the
quality of model inputs, desk eligibility, PLA/backtesting, stressed expected
shortfall, NMRF stress scenarios, and capital aggregation. Keeping those
boundaries explicit makes unsupported production workflows visible instead of
embedding implicit assumptions in calculators.

## Core Components

| Component | Conceptual basis | Regulatory anchor | Evidence |
| --- | --- | --- | --- |
| Data contracts | Capital inputs must have aligned scenario, risk-factor, and desk metadata before calculation. | Basel MAR31-MAR33 input-lineage concepts; U.S. NPR 2.0 market-risk workflow traceability. | `data_contracts.py`, `scenario.py`, `DATASET_CONTRACT.md`. |
| RFET | Risk factors are classified before capital routing, with an audit-grade evidence path separate from fast scalar classification. | Basel MAR31 RFET; U.S. NPR 2.0 Type A/Type B NMRF modelling choices; EU Article 325be and Delegated Regulation (EU) 2022/2060. | `rfet.py`, `rfet_evidence.py`, requirement IDs `NPR-MR-RFET-001` to `NPR-MR-RFET-003`. |
| Expected shortfall | Tail-loss averaging captures downside risk beyond VaR and is the basis for IMA expected shortfall. | Basel MAR33; U.S. NPR 2.0 expected-shortfall-based measures; EU Article 325bc. | `expected_shortfall.py`, independent reference-vector tests. |
| Liquidity horizon adjustment | Nested vectors by risk-factor liquidity horizon avoid applying one scalar multiplier to an already aggregated ES. | Basel MAR33 liquidity-horizon adjustment; proposed section `__.215`; EU Articles 325bc and 325bd. | `lha_builder.py`, `liquidity_horizon.py`, `scenario_validation.py`. |
| IMCC | The constrained/unconstrained blend captures diversification limits across risk classes. | Basel MAR33; proposed models-based non-default capital mechanics; EU Articles 325ba-325bc. | `imcc.py`, `reduced_set.py`. |
| NMRF / SES | Non-modellable risk factors require stress-scenario treatment and separate SES aggregation. | Basel MAR33 NMRF stress scenarios; U.S. NPR 2.0 Type A/Type B SES treatment; EU Article 325bk. | `nmrf.py`, `nmrf_method_selection.py`, `nmrf_stress_spec.py`, `nmrf_valuation_run.py`. |
| PLA and backtesting | Desk model eligibility depends on comparing model P&L to hypothetical/actual P&L and VaR exceptions. | Basel MAR32; proposed section `__.213`; EU Articles 325bf-325bg and Delegated Regulation (EU) 2022/2059. | `pla.py`, `backtesting.py`. |
| Audit artifacts | Model outputs must be reproducible and reviewable outside runtime logs. | MAR31-MAR33 model governance and traceability; U.S. NPR 2.0 governance basis. | `audit.py`, `audit_inputs.py`, `VALIDATION_PACK.md`. |

## Suitability Of Formulas

The formulas are suitable for the prototype because they preserve the key
regulatory mechanics that drive IMA capital:

- ES is computed from empirical loss tails at the policy confidence level.
- LHA ES is computed from nested risk-factor vectors, so each liquidity horizon
  component has its own scenario losses.
- IMCC separately evaluates all-risk-class and per-risk-class constrained terms
  before applying the policy blend.
- Type A and Type B NMRFs are routed distinctly, with Type A included in IMCC
  and SES and Type B included in SES only.
- PLA and backtesting remain desk-level eligibility diagnostics rather than
  hidden capital adjustments.

The package intentionally avoids product-specific pricing logic because that
would mix the risk-engine responsibility with the capital-layer responsibility.

## Evidence Strength

Current evidence is strongest for deterministic calculation mechanics:

- unit and property tests cover normal, edge, and invalid-input paths;
- independent reference-vector tests cover ES, LHA ES, IMCC, SES, PLA, and
  supervisory multiplier mappings;
- the committed `capital_run_v1` fixture provides a stable integration sentinel;
- CI enforces linting, typing, tests, notebooks, dependency audit, SBOM, and
  coverage floors.

Evidence is weaker for production governance workflows that require bank data,
supervisory interpretation, and independent validation. These are listed in
[`03_assumptions_and_limitations.md`](03_assumptions_and_limitations.md) and
tracked through the audit backlog.
