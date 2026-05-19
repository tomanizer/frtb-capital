# Regulatory assumptions for prototype

This repository implements a **prototype** FRTB IMA capital calculator inspired by Basel FRTB IMA and the March 2026 U.S. NPR 2.0 market-risk proposal.

It is not a production regulatory calculator and should not be used for regulatory reporting without legal, risk, model validation, and supervisory review.

## Basel FRTB IMA background

Basel FRTB separates market risk capital into standardized and internal-model approaches. The Basel standard contains the trading book boundary, standardized approach chapters, and internal models chapters covering model requirements, backtesting, profit-and-loss attribution, expected shortfall, and non-modellable risk factors.

## Prototype NPR 2.0 assumptions

The prototype uses these working assumptions:

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
10. Type B NMRFs are included in SES only.
11. PLA is prototyped using a Kolmogorov-Smirnov statistic comparing HPL and RTPL.
12. Backtesting is prototyped using VaR exception counts.

## Important limitation

The prototype intentionally excludes or simplifies:
- default risk charge,
- standardized approach implementation,
- fallback capital requirements,
- redesignation add-ons,
- legal-entity consolidation,
- actual supervisory submission workflows,
- full stress-period selection governance,
- vendor real-price evidence workflows,
- production data lineage and audit controls.
