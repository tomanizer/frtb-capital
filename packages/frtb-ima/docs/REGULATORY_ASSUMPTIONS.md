# Regulatory assumptions for prototype

This package implements a **prototype** FRTB IMA capital calculator inside the
`frtb-capital` monorepo. It is inspired by Basel FRTB IMA, the March 2026 U.S.
NPR 2.0 market-risk proposal, and the EU CRR/CRR3 FRTB internal-model
framework.

It is not a production regulatory calculator and should not be used for regulatory reporting without legal, risk, model validation, and supervisory review.

For a bidirectional code/regulation map, see [REGULATORY_TRACEABILITY.md](REGULATORY_TRACEABILITY.md).

## Basel FRTB IMA background

Basel FRTB separates market risk capital into standardized and internal-model approaches. The Basel standard contains the trading book boundary, standardized approach chapters, and internal models chapters covering model requirements, backtesting, profit-and-loss attribution, expected shortfall, and non-modellable risk factors.

The Basel references used by the prototype are primarily MAR30, MAR31, MAR32, MAR33, and MAR99.

## Prototype NPR 2.0 basis

All U.S. NPR 2.0 content is treated as proposed-rule material. The prototype
uses the following documented modelling basis:

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
15. Fed NPR PLA uses a Kolmogorov-Smirnov statistic comparing HPL and RTPL
    over a 250-business-day policy window. ECB/PRA comparison profiles also
    compute Spearman rank correlation and use the worse KS/Spearman joint zone.
16. Backtesting counts both APL and HPL exceptions at 97.5% and 99.0% VaR
    confidence levels. The Fed profile applies exception limits of 30 at 97.5%
    and 12 at 99.0%.
17. Missing APL, HPL, or VaR observations count as backtesting exceptions
    unless marked as official-holiday related.

## Policy parameter citation allowlist

`RegulatoryPolicy.cited_by` records the regulatory citation for each numeric
threshold or parameter used by policy-aware calculations. Two numeric policy
fields are deliberately treated as structural modelling choices rather than
thresholds:

- `liquidity_horizons`: the tuple of supported liquidity-horizon buckets used
  to structure nested scenario vectors.
- `lha_weights`: the deterministic weights derived from adjacent liquidity
  horizons for liquidity-horizon-adjusted ES aggregation.

Changes to either field are material model-design changes and require ADR-led
review, but they are not threshold overrides in the same sense as PLA,
backtesting, RFET, ES confidence, reduced-set, stress-period, NMRF rho, or
supervisory multiplier parameters.

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
- redesignation add-ons (within IMA desk lifecycle),
- SA, DRC, and CVA capital (planned sibling packages in the monorepo),
- legal-entity and firm-level consolidation (orchestration layer),
- actual supervisory submission workflows,
- formal stress-period approval governance and raw market-data sourcing,
- vendor real-price evidence workflows,
- EU RTS-level RFET data-pooling/vendor-reliance rules,
- production-grade data lineage, storage, telemetry, and control framework.

## Determinism guarantee

The committed `capital_run_v1` fixture is the package-level reproducibility
sentinel. The CI test matrix runs the full fixture on Python 3.11, 3.12, and
3.13, serialises the computed output with canonical JSON settings, and compares
the SHA-256 digest with the committed expectation under
`tests/fixtures/determinism/`.

Within that boundary, the guarantee is:

1. With the committed fixture inputs, committed code, and the dependency
   versions resolved by `uv.lock`, the fixture output hash is expected to be
   stable for each supported Python minor version.
2. A change to calculation logic, fixture inputs, Python minor behaviour, or the
   resolved NumPy minor version must either preserve the committed hash or
   intentionally update the hash registry in the same change.
3. The guarantee covers the canonical fixture output dictionary, not every
   intermediate floating-point array or optional diagnostic rendering.

Known limits:

- The repository does not yet enforce bit-level equivalence across operating
  systems, BLAS implementations, or CPU vector widths.
- Extreme floating-point edge cases outside the committed synthetic fixture may
  still show last-bit differences when NumPy dispatches to different platform
  kernels.
- Regulatory reproducibility for proprietary bank inputs will require future
  input hashing, code-version, policy-version, and replay controls.

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
   collected into `DeskAuditRecord` / `CapitalRunAuditLog` NDJSON artifacts
   and deterministic Markdown reports.
6. Stress-period selection now has a first-class pre-run component that selects
   common risk-class stress windows from supplied historical loss/severity
   vectors with NumPy-native rolling-window severity scoring.
7. Liquidity-horizon mapping is implemented for caller-supplied regulatory
   categories, including short-maturity and weighted-average multi-underlying
   helpers.

Remaining deliberate boundaries:

- Direct, stepwise, and full-revaluation NMRF pricing/revaluation remains an
  upstream risk-engine responsibility. The prototype specifies required
  valuation runs, reconciles, validates, and consumes the resulting artifacts,
  but does not embed institutional pricing models.
- RFET qualitative criteria remain external inputs. Vendor lineage, data-pooling
  eligibility, supervisory overrides, and new-issuance pro-rating remain out of
  scope.
- Raw market-data sourcing, formal stress-period approval governance,
  reduced-set governance, proprietary trade/vendor-to-LH-category evidence,
  risk-factor bucketing, and firm-level consolidation are not complete
  regulatory workflows.
- External telemetry backends, OpenTelemetry, Prometheus/Datadog metrics,
  streaming audit writers for very large desk batches, Parquet/DuckDB audit
  analytics, and final regulatory disclosure templates remain
  orchestration-layer future scope.
