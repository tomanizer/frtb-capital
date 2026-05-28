# Intended Use

## Model Purpose

`frtb-ima` is the Internal Models Approach component in the `frtb-capital`
monorepo. It assembles desk-level market-risk capital inputs for model-eligible
trading desks from already prepared scenario P&L vectors, risk-factor evidence,
stress artifacts, and PLA/backtesting vectors.

The package is an ex-post capital assembly layer. It does not source market
data, price trades, generate scenarios, approve trading desks, or perform
firm-level capital consolidation.

## Intended Users

The intended users are quantitative developers, market-risk methodology teams,
model validators, and engineering reviewers evaluating calculation mechanics,
traceability, deterministic testing, and control design for an FRTB IMA-style
prototype.

The package may be used to:

- exercise expected shortfall, liquidity-horizon adjustment, IMCC, SES, PLA,
  backtesting, and desk-level capital assembly on synthetic or controlled input
  data;
- validate package-level data contracts and audit artifacts;
- demonstrate how an upstream risk engine could hand off scenario vectors and
  stress artifacts to an ex-post capital layer;
- support development of independent validation tests and documentation.

The package must not be used to:

- produce final regulatory capital;
- file regulatory reports;
- substitute for independent model validation, legal interpretation, or
  supervisory approval;
- source or transform proprietary market data without an approved upstream
  data-control layer.

## In-Scope Desks And Instruments

The in-scope boundary is a model-eligible trading desk whose upstream systems
can provide:

- 10-day scenario P&L vectors using a positive-loss sign convention;
- risk-factor definitions with risk class and liquidity horizon;
- RFET qualitative and quantitative evidence;
- stress-period inputs or pre-valued stress artifacts for NMRFs;
- HPL, RTPL, APL, and VaR vectors for PLA and backtesting;
- desk eligibility status from the governance process.

The package works at the risk-factor and desk-result level. It does not encode
product taxonomies, proprietary instrument enrichment, vendor field mappings,
or trading-book boundary decisions.

## Out Of Scope

The following are outside this package and belong to planned sibling packages or
upstream systems:

- SBM, Default Risk Charge, residual risk add-on, CVA, and fallback capital;
  SA fallback is owned by orchestration as the composed SBM + DRC + RRAO stack;
- legal-entity, firm-level, or top-of-house aggregation;
- market-data sourcing, cleaning, and lineage attestation;
- trade pricing, full revaluation, risk-engine scenario generation, and vendor
  adapter logic;
- formal model approval lifecycle, remediation workflows, and supervisory
  submissions;
- final disclosure templates and external reporting packages.

## Regulatory Anchors

The conceptual baseline is Basel MAR31-MAR33 and MAR99. The primary profile in
the code is the U.S. NPR 2.0 proposed-rule profile, with traceability to
proposed sections `__.213` for desk eligibility and PLA/backtesting gates and
`__.215` for liquidity-horizon adjusted expected shortfall mechanics. EU CRR3
Articles 325ba-325bg and Article 325bk are used as comparison anchors.

For the full code-to-regulation map, see
[`REGULATORY_TRACEABILITY.md`](../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md).
