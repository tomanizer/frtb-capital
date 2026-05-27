# Regulatory assumptions for prototype

This repository implements a **prototype** FRTB IMA capital calculator inspired by Basel FRTB IMA, the March 2026 U.S. NPR 2.0 market-risk proposal, and the EU CRR/CRR3 FRTB internal-model framework.

It is not a production regulatory calculator and should not be used for regulatory reporting without legal, risk, model validation, and supervisory review.

For a bidirectional code/regulation map, see [REGULATORY_TRACEABILITY.md](REGULATORY_TRACEABILITY.md).

## Basel FRTB IMA background

Basel FRTB separates market risk capital into standardized and internal-model approaches. The Basel standard contains the trading book boundary, standardized approach chapters, and internal models chapters covering model requirements, backtesting, profit-and-loss attribution, expected shortfall, and non-modellable risk factors.

The Basel references used by the prototype are primarily MAR30, MAR31, MAR32, MAR33, and MAR99.

## Prototype NPR 2.0 assumptions

All U.S. NPR 2.0 content is treated as proposed-rule working assumptions. The prototype uses these assumptions:

1. Market risk IMA capital is based on expected shortfall-style calculations.
2. Scenario generation uses 10-day overlapping historical shocks for IMCC-style ES.
3. Liquidity horizon adjustment uses nested P&L vectors by risk-factor liquidity horizon.
4. Liquidity horizons are 10, 20, 40, 60, and 120 business days.
5. Risk factors are classified as:
   - modellable,
   - Type A NMRF,
   - Type B NMRF.
6. A risk factor is modellable if it passes qualitative and quantitative tests.
7. A Type A NMRF passes the qualitative test but fails the quantitative real-price test.
8. A Type B NMRF fails the qualitative test or otherwise does not qualify as modellable or Type A.
9. Type A NMRFs are included in both IMCC and SES.
10. Type A NMRF SES values aggregate with zero-correlation root-sum-square
    treatment in the SES formula.
11. Type B NMRFs are included in SES only, with the proposed 0.36 correlation
    parameter in the Type B aggregation term.
12. RFET classifications are available before valuation. NMRF method selection
    can consume auditable method evidence, emits valuation instructions and
    upstream valuation-run specs for Type A and Type B NMRFs. Returned stress
    artifacts are reconciled to the specs before the capital layer consumes
    them.
13. Missing or mismatched Type A or Type B NMRF stress artifacts are hard
    validation errors; the capital layer does not silently substitute linear
    approximations. Prototype-labelled valuation artifacts fail reconciliation
    unless a demo/test caller explicitly opts into synthetic artifacts.
14. Stress-period selection is a pre-run calibration step by risk class. The
    prototype selects windows from supplied historical loss/severity vectors
    using a fixed observation-count business-day proxy for a 12-month period.
    It does not source raw market data, price trades, or approve a formal
    regulatory stress-period methodology.
15. PLA uses a Kolmogorov-Smirnov statistic comparing HPL and RTPL over a
    250-business-day policy window.
16. Backtesting counts both APL and HPL exceptions at 97.5% and 99.0% VaR
    confidence levels. The Fed profile applies exception limits of 30 at 97.5%
    and 12 at 99.0%.
17. Missing APL, HPL, or VaR observations count as backtesting exceptions
    unless marked as official-holiday related.

## EU CRR / CRR3 comparison assumptions

The EU comparison layer is based on Regulation (EU) No 575/2013 as amended by CRR2 and CRR3, especially:

1. Article 325ba for own-funds requirements under alternative internal models.
2. Article 325bb for expected shortfall risk measure aggregation.
3. Article 325bc for partial expected shortfall calculations and the 10-day base horizon.
4. Article 325bd for liquidity horizons and risk-factor mapping.
5. Article 325be and Delegated Regulation (EU) 2022/2060 for risk-factor modellability.
6. Article 325bf and Delegated Regulation (EU) 2022/2059 for backtesting.
7. Article 325bg and Delegated Regulation (EU) 2022/2059 for profit-and-loss attribution.
8. Article 325bk for the stress scenario risk measure.

The EU references are used for traceability and comparison. The code does not
claim to calculate final EU own-funds requirements.

## Important limitation

The prototype intentionally excludes or simplifies:
- default risk charge,
- standardized approach implementation,
- fallback capital requirements,
- redesignation add-ons,
- legal-entity consolidation,
- actual supervisory submission workflows,
- formal stress-period approval governance and raw market-data sourcing,
- vendor real-price evidence workflows,
- EU RTS-level PLA Spearman correlation,
- EU RTS-level RFET data-pooling/vendor-reliance rules,
- production-grade data lineage, storage, telemetry, and control framework.

## Recent accuracy audit

The May 2026 accuracy pass corrected four prior simplifications:

1. Type A SES aggregation is no longer a conservative linear sum. It now follows
   the proposed zero-correlation root-sum-square term and combines with the
   Type B partial-correlation term under one square root.
2. Trading-desk backtesting now has an NPR-style gate that evaluates 97.5% and
   99.0% VaR exception counts separately for APL and HPL, including missing-data
   exception treatment and optional prorated thresholds for shorter approved
   histories.
3. The PLA policy wrapper now enforces the 250-business-day policy window before
   applying the KS threshold classification.
4. NMRF treatment now has an explicit post-RFET method-selection step, method
   evidence diagnostics, upstream valuation-run specs, valuation-run artifact
   reconciliation, vectorized stress-artifact SES extraction, and fail-hard
   validation for missing Type A/B NMRF artifacts.
5. Policy-wrapper boundaries can emit structured JSON log records with run,
   desk, regime, and scalar result fields. Decomposed result objects can be
   collected into `DeskAuditRecord` / `CapitalRunAuditLog` NDJSON artifacts.
6. Stress-period selection now has a first-class pre-run component that selects
   common risk-class stress windows from supplied historical loss/severity
   vectors with NumPy-native rolling-window severity scoring.

Remaining deliberate boundaries:

- Direct, stepwise, and full-revaluation NMRF pricing/revaluation remains an
  upstream risk-engine responsibility. The prototype specifies required
  valuation runs, reconciles, validates, and consumes the resulting artifacts,
  but does not embed institutional pricing models.
- RFET qualitative criteria remain external inputs. Vendor lineage, data-pooling
  eligibility, supervisory overrides, and new-issuance pro-rating remain out of
  scope.
- Raw market-data sourcing, formal stress-period approval governance,
  reduced-set governance, risk-factor bucketing, and firm-level consolidation
  are not complete regulatory workflows.
- External telemetry backends, OpenTelemetry, Prometheus/Datadog metrics,
  streaming audit writers for very large desk batches, Parquet/DuckDB audit
  analytics, and full regulatory report generation remain orchestration-layer
  future scope.
