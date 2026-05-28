# Derivation

This section records the calculation logic used by `frtb-ima`. It is a model
documentation summary, not a substitute for the executable code or the
regulatory traceability tables.

## Expected Shortfall

Inputs are scenario losses where positive values mean losses. For a confidence
level `alpha`, expected shortfall is the average loss in the upper tail beyond
`alpha`.

For ordered losses `x_(1) <= ... <= x_(n)`, the package supports a weighted
interpolated estimator that applies full weight to the worst complete tail
observations and fractional weight to the next observation when
`n * (1 - alpha)` is not an integer. This is documented as the policy default
in ADR 0004 and in
[`REGULATORY_ASSUMPTIONS.md`](../../../../packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md#expected-shortfall-estimator).

Regulatory anchors:

- Basel MAR33 97.5 percent one-tailed ES.
- U.S. NPR 2.0 expected-shortfall-based measures for model-eligible positions.
- EU Article 325bc partial ES at 97.5 percent one-tailed confidence.

## Liquidity-Horizon Adjusted ES

The package uses nested liquidity-horizon vectors. `LH10` contains all selected
risk factors; `LH20` contains risk factors with liquidity horizon of at least
20 business days; and so on through `LH120`.

For horizon buckets `i`, LHA ES is:

```text
LHA_ES = sqrt(sum_i(weight_i * ES(P_LH_i)^2))
```

where `P_LH_i` is the scenario loss vector for the nested risk-factor subset at
the corresponding liquidity horizon. The weights are derived from adjacent
liquidity horizons in the configured policy. `LH10` must be present.

Regulatory anchors:

- Basel MAR33 liquidity-horizon adjustment.
- U.S. NPR 2.0 proposed section `__.215` liquidity-horizon adjusted expected
  shortfall.
- EU Articles 325bc and 325bd.

## IMCC

The model-based non-default component evaluates all-risk-class and
per-risk-class liquidity-horizon adjusted ES inputs for current and stressed
periods. The reduced-set stress scaling floor is:

```text
scaled_stress_ES = stress_ES * max(1, current_full_ES / current_reduced_ES)
```

The IMCC calculation then forms unconstrained and constrained terms and applies
the policy blend, currently a 50/50 blend for the Fed NPR 2.0 profile.

Regulatory anchors:

- Basel MAR33 IMA capital calculation and current/stressed ES concepts.
- U.S. NPR 2.0 models-based non-default capital mechanics.
- EU Articles 325ba, 325bb, and 325bc.

## SES For NMRFs

NMRF stress artifacts are produced upstream and reconciled by the package
before capital use. The capital layer extracts stressed expected shortfall from
the returned artifact losses and aggregates by NMRF type.

Type A NMRFs are included in both IMCC and SES. Type A SES uses
zero-correlation root-sum-square treatment:

```text
SES_A = sqrt(sum_i(SES_A_i^2))
```

Type B NMRFs are included in SES only. The Type B aggregation uses the policy
correlation parameter `rho`, currently `0.36` for the Fed NPR 2.0 profile:

```text
SES_B = sqrt(rho * (sum_i SES_B_i)^2 + (1 - rho) * sum_i(SES_B_i^2))
```

The total SES combines Type A and Type B terms under one square root in the
implemented decomposition.

Regulatory anchors:

- Basel MAR33 NMRF stress-scenario capital.
- U.S. NPR 2.0 Type A / Type B SES treatment.
- EU Article 325bk stress scenario risk measure comparison.

## PLA Metrics

The Fed NPR 2.0 profile compares HPL and RTPL over the policy window with a
Kolmogorov-Smirnov statistic. The package also implements a Spearman
rank-correlation metric for ECB/PRA comparison profiles and applies the worse
joint zone where that profile requires both metrics.

Regulatory anchors:

- Basel MAR32 PLA test and traffic-light thresholds.
- U.S. NPR 2.0 proposed section `__.213` PLA eligibility gates.
- EU Article 325bg and Delegated Regulation (EU) 2022/2059 Articles 4-5.

## Backtesting Metrics

Backtesting compares APL and HPL observations with VaR measures. With
positive-profit P&L and positive-magnitude VaR, an exception occurs when:

```text
-P&L > VaR
```

The Fed profile evaluates both 97.5 percent and 99.0 percent VaR exception
counts over the policy window, with missing observations treated as exceptions
unless they are official-holiday related.

Regulatory anchors:

- Basel MAR32 backtesting.
- U.S. NPR 2.0 proposed section `__.213` backtesting eligibility gates.
- EU Article 325bf and Delegated Regulation (EU) 2022/2059.

## Desk-Level Capital Assembly

The package assembles a desk-level models-based capital measure from IMCC, SES,
and PLA add-on components, subject to an explicit desk eligibility handoff. It
does not calculate SBM, DRC, RRAO, CVA, fallback stack capital, redesignation
add-ons, or firm-level consolidation.

Regulatory anchors:

- Basel MAR33 capital calculation and multiplier concepts.
- U.S. NPR 2.0 models-based market-risk measure and proposed section `__.213`
  eligibility context.
- EU Article 325ba own-funds requirement under alternative internal models.
