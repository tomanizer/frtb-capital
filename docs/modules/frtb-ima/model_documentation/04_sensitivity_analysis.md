# Sensitivity Analysis

This document records the results of policy-parameter sensitivity sweeps run
against the committed `capital_run_v1` synthetic fixture. The sweeps perturb
one policy parameter at a time and hold all fixture inputs fixed. They are
**evidence-of-mechanics**, not a production validation campaign.

Independent validation under the engagement charter
(`docs/VALIDATION_ENGAGEMENT_CHARTER.md`) should treat these results as the
starting point and extend them against controlled, peer, or anonymized bank
fixtures per Section 7 below.

The reproducer is `packages/frtb-ima/scripts/sensitivity_sweep.py`. Raw output
is JSON; numbers in this document are transcribed verbatim from a single run
(no rounding beyond the script's 6-decimal-place rounding).

## 1. Objectives

Sensitivity analysis answers three questions for each policy parameter and
input axis:

1. **Direction:** does the output move in the expected direction when the
   parameter increases?
2. **Magnitude:** how large is the response, in absolute and proportional
   terms?
3. **Discontinuities:** are there cliffs (step functions, threshold effects)
   where small input changes produce large output changes?

## 2. Fixture composition

The committed `capital_run_v1` fixture has the following risk-factor
classification (the routing input for IMCC vs SES capital):

| Classification | Count |
|---|---|
| `MODELLABLE` | 8 |
| `TYPE_A_NMRF` | 1 |
| `TYPE_B_NMRF` | 1 |

The single Type B factor matters for interpreting Section 5.1: with N=1,
the Type B correlation parameter ρ is structurally without effect on
aggregated SES. Section 5.2 supplies a synthetic-vector demonstration that
isolates the formula's actual ρ-sensitivity.

## 3. Baseline outputs

Under the default Fed NPR 2.0 policy (`get_policy(FED_NPR_2_0)`) and the
committed fixture:

| Output | Value |
|---|---|
| IMCC | 64,370.825659 |
| Unconstrained LHA ES | 50,573.019383 |
| Constrained LHA ES | 78,168.631934 |
| Total SES | 5,631.072341 |

Baseline policy parameters that subsequent sweeps perturb:

| Parameter | Value |
|---|---|
| `es_confidence_level` | 0.975 |
| `es_estimator` | `WEIGHTED_INTERPOLATED` |
| `imcc_unconstrained_weight` | 0.5 |
| `type_b_ses_rho` | 0.36 |
| `supervisory_multiplier` (at 0 exceptions) | 1.50 |

## 4. Sweep results

### 4.1 Expected shortfall confidence level (ES α)

| α | Unconstrained LHA ES | Constrained LHA ES | IMCC | Δ IMCC vs baseline |
|---|---|---|---|---|
| 0.95 | 45,139.8407 | 70,110.7216 | 57,625.2812 | −10.48% |
| 0.96 | 46,564.6210 | 72,995.3849 | 60,035.6098 | −6.74% |
| 0.97 | 49,124.8032 | 76,316.8735 | 62,720.8384 | −2.56% |
| **0.975** | **50,573.0194** | **78,168.6319** | **64,370.8257** | **baseline** |
| 0.98 | 52,052.0432 | 80,409.4183 | 66,230.7308 | +2.89% |
| 0.99 | 54,829.3293 | 86,975.7449 | 70,902.5371 | +10.15% |

**Direction:** strictly monotone increasing in α as expected — higher
confidence level pulls more severe tail observations.

**Magnitude:** moving α from 0.95 to 0.99 increases IMCC by ~23% on this
fixture; the baseline 0.975 sits roughly mid-range.

**Discontinuity:** none observed — the interpolated estimator (Section 4.2)
ensures smooth response across the α grid.

### 4.2 ES estimator choice

| Estimator | IMCC | Δ vs interpolated |
|---|---|---|
| `WEIGHTED_INTERPOLATED` (baseline) | 64,370.8257 | — |
| `DISCRETE_CEIL` | 63,378.8450 | −1.54% |

On this fixture, switching the estimator from interpolated to ceil-based
discrete reduces IMCC by ~1.5%. ADR 0004 records why interpolated is the
policy default: it removes the finite-sample bias of the ceil rule by
allocating tail mass `n × (1−α)` proportionally between the full and partial
tail observation, giving a smoother response across α and across N.

**Validator note:** the sign of the (interpolated − discrete) difference is
fixture-dependent. On thin-tailed inputs the two estimators can converge; on
heavy-tailed inputs the gap widens. A heavy-tail fixture would tighten the
evidence here.

### 4.3 IMCC unconstrained weight

| `imcc_unconstrained_weight` | IMCC |
|---|---|
| 0.00 (fully constrained) | 78,168.6319 |
| 0.25 | 71,269.7288 |
| **0.50 (baseline)** | **64,370.8257** |
| 0.75 | 57,471.9225 |
| 1.00 (fully unconstrained) | 50,573.0194 |

**Direction:** strictly monotone decreasing in unconstrained weight as
expected — the unconstrained term is always ≤ the constrained term on this
fixture (constrained sums per-risk-class ES without cross-class
diversification).

**Magnitude:** moving from 0% to 100% unconstrained weight reduces IMCC by
~35% on this fixture. The 0.50 default sits exactly at the midpoint per
Basel MAR33 / NPR 2.0 §`__.214`.

**Linearity check:** IMCC at weight w should equal
`(1-w) × constrained + w × unconstrained = 78,168.6319 + w × (50,573.0194 - 78,168.6319)`.
Expected at w=0.25: 78,168.63 + 0.25 × (-27,595.61) = 71,269.73 ✓.
Expected at w=0.75: 78,168.63 + 0.75 × (-27,595.61) = 57,471.92 ✓.
Linear interpolation is exact to 6dp.

### 4.4 Type B SES correlation (ρ) — fixture sweep

| ρ | Total SES |
|---|---|
| 0.00 | 5,631.0723 |
| 0.18 | 5,631.0723 |
| **0.36 (baseline)** | **5,631.0723** |
| 0.54 | 5,631.0723 |
| 0.72 | 5,631.0723 |
| 0.99 | 5,631.0723 |

**Direction:** none. The fixture has only one Type B NMRF, so the Type B
aggregation has no off-diagonal correlation terms. Total SES on the fixture
is ρ-insensitive **by construction of the fixture, not by construction of
the formula**.

This is a fixture limitation, not a model limitation. Section 4.5 isolates
the formula's actual ρ-sensitivity.

### 4.5 Type B SES correlation (ρ) — synthetic demonstration

Synthetic Type B SES vectors of length N ∈ {2, 3, 5} with per-factor SES =
100 (Type A vector empty; only Type B drives total). Aggregation formula
per Basel MAR33.16 / U.S. NPR 2.0 §`__.215`:

> `SES_B = √(ρ × (Σ SES_i)² + (1 − ρ) × Σ SES_i²)`

| N | ρ | Type B correlated term | Total SES |
|---|---|---|---|
| 2 | 0.00 | 20,000.00 | 141.4214 |
| 2 | 0.18 | 23,600.00 | 153.6229 |
| 2 | 0.36 | 27,200.00 | 164.9242 |
| 2 | 0.54 | 30,800.00 | 175.4993 |
| 2 | 0.72 | 34,400.00 | 185.4724 |
| 2 | 0.99 | 39,800.00 | 199.4994 |
| 3 | 0.00 | 30,000.00 | 173.2051 |
| 3 | 0.18 | 40,800.00 | 201.9901 |
| 3 | 0.36 | 51,600.00 | 227.1563 |
| 3 | 0.54 | 62,400.00 | 249.7999 |
| 3 | 0.72 | 73,200.00 | 270.5550 |
| 3 | 0.99 | 84,000.00 | 289.8275 |
| 5 | 0.00 | 50,000.00 | 223.6068 |
| 5 | 0.36 | 188,000.00 | 433.5897 |
| 5 | 0.99 | 248,000.00 | 497.9960 |

**Direction:** strictly monotone increasing in ρ for every N ≥ 2 as
expected — higher correlation reduces diversification benefit.

**Magnitude:** at N=2, moving ρ from 0 to 0.99 increases SES by 41%
(141.42 → 199.50). At N=5, the same ρ move yields a 123% increase
(223.61 → 497.99). The marginal effect of ρ grows with N because there are
more off-diagonal correlation terms.

**Closed-form check:**
- ρ=0 (zero correlation) reduces to RSS: √(N) × per_factor_SES.
  - N=2: √2 × 100 = 141.42 ✓
  - N=3: √3 × 100 = 173.21 ✓
  - N=5: √5 × 100 = 223.61 ✓
- ρ=1 reduces to linear sum: N × per_factor_SES.
  - At ρ=0.99 (near 1) for N=2: expected 200, observed 199.50 ✓

### 4.6 Supervisory multiplier (MAR99 Table 2)

| Exception count | Multiplier |
|---|---|
| 0 | 1.50 |
| 1 | 1.50 |
| 2 | 1.50 |
| 3 | 1.50 |
| 4 | 1.50 |
| 5 | 1.70 |
| 6 | 1.76 |
| 7 | 1.83 |
| 8 | 1.88 |
| 9 | 1.92 |
| 10 | 2.00 |
| 11 | 2.00 |
| 12 | 2.00 |

**Direction:** monotone non-decreasing as expected.

**Discontinuity:** step function. Largest jump is at 4→5 exceptions (+0.20)
and 9→10 (+0.08 — the red-zone floor). The 4→5 transition is the most
material in capital terms because it occurs at the smallest exception count.

### 4.7 Capital response to multiplier (other inputs held fixed)

Holding IMCC = 64,370.83 and Total SES = 5,631.07 fixed (with the same
synthetic 60-day averages used in the workflow: IMCC × 1.03 and SES × 1.02):

| Exception count | Multiplier | Models-based capital | Binding term | Δ vs 0 exceptions |
|---|---|---|---|---|
| 0 | 1.50 | 105,196.6194 | AVERAGE | baseline |
| 4 | 1.50 | 105,196.6194 | AVERAGE | 0.00% |
| 5 | 1.70 | 118,457.0095 | AVERAGE | +12.60% |
| 8 | 1.88 | 130,391.3606 | AVERAGE | +23.95% |
| 9 | 1.92 | 133,043.4386 | AVERAGE | +26.47% |
| 10 | 2.00 | 138,347.5946 | AVERAGE | +31.51% |

**Direction:** monotone non-decreasing.

**Magnitude:** the most material single-step jump in capital terms is the
4→5 exception transition (+12.60%), reflecting the multiplier going from
1.50 to 1.70.

**Binding term:** stays `AVERAGE` throughout the sweep on this fixture
(the multiplier × average term always exceeds the spot term). A fixture
where spot ≈ average would expose a binding-term flip.

## 5. Cliffs and discontinuities catalogued

| Source | Type | Location | Magnitude |
|---|---|---|---|
| Supervisory multiplier | Step function | 4→5 exceptions | Multiplier +0.20 (1.50→1.70); IMCC-driven capital +12.6% on this fixture |
| Supervisory multiplier | Step function | 9→10 exceptions | Multiplier +0.08 (1.92→2.00) red-zone floor |
| ES estimator selection | Discrete choice | `WEIGHTED_INTERPOLATED` vs `DISCRETE_CEIL` | ~1.5% on this fixture; sign depends on tail shape |
| PLA zone boundaries | Step function | KS = 0.09 (green/amber) and 0.12 (amber/red) | Crossing 0.12 forces SA fallback (IMA-ineligible) |
| Reduced-set variation explained | Hard threshold | 75% | Selection fails below threshold; IMCC scaling does not occur |
| Backtesting exception limits | Hard threshold | 30 at 97.5% level, 12 at 99% level | Eligibility flip (model → SA fallback) |
| Desk eligibility | Two-state | `IMA_ELIGIBLE` ↔ `SA_FALLBACK` | Hard `IMAIneligibleError`; SA fallback is out of scope |

All but the first two were not exercised in the live sweeps but are
documented here because they are knowable from the policy structure and an
independent reviewer should be able to anticipate them.

## 6. Things this sweep does **not** cover

The following analyses from the original required-analyses table (Section 7
below) were not run because they require fixture changes, not policy
perturbation:

| Analysis | Why deferred | What it needs |
|---|---|---|
| Scenario count sweep | Requires regenerating fixtures at different N | New fixture variants at N=50, 100, 250, 500 |
| LH category reassignment | Requires altering the `risk_factors.csv` LH column | Sibling fixture with same scenarios, different LH assignment |
| Risk-class concentration | Requires reshaping the scenario cube | Synthetic concentrated fixture |
| RFET / reduced-set boundary tests | Requires varying observation count and coverage | Adversarial small-fixture series |
| NMRF Type A/B mix | Requires reclassifying the fixture's NMRF | Reclassified fixture variants |
| NMRF method comparison | Requires multi-artifact same-factor inputs | Specialised fixture with parallel direct/stepwise/full revaluation artifacts |
| PLA HPL/RTPL perturbation | Requires varying the supplied vectors | Adversarial PLA fixtures |
| Backtesting exception injection | Requires varying APL/HPL/VaR vectors | Adversarial backtesting fixtures |

These belong in the validation-engagement workplan, not in the sensitivity
script.

## 7. Required analyses (reference checklist)

The original sensitivity-analysis plan defined the following analyses.
Status column tracks coverage by this document.

| Analysis | Perturbation | Status |
|---|---|---|
| ES tail severity | Scale worst 1%, 2.5%, 5% scenario losses | Deferred (fixture-level) |
| ES confidence level | Vary α | **Done** — §4.1 |
| ES estimator | Compare interpolated vs ceil | **Done** — §4.2 |
| Scenario count | Run matched datasets with smaller and larger N | Deferred (fixture-level) |
| Liquidity horizon assignment | Move risk factors between LH categories | Deferred (fixture-level) |
| Risk-class concentration | Concentrate vs diversify | Deferred (fixture-level) |
| IMCC blend weight | Vary `imcc_unconstrained_weight` | **Done** — §4.3 |
| Reduced set | Vary contribution coverage around 75% threshold | Deferred (fixture-level) |
| Stress-window severity | Shift supplied loss/severity vectors and window lengths | Deferred (fixture-level) |
| NMRF Type A / Type B mix | Reclassify factors | Deferred (fixture-level) |
| NMRF stress method | Compare artifact types for same factor | Deferred (fixture-level) |
| Type B SES correlation | Vary ρ | **Done** — §4.4 (fixture) + §4.5 (synthetic) |
| PLA metric | Perturb HPL/RTPL | Deferred (fixture-level) |
| Backtesting | Inject APL/HPL exceptions | Deferred (fixture-level) — but §4.6 + §4.7 cover the multiplier cliff |
| Supervisory multiplier | Move exception counts across table | **Done** — §4.6 + §4.7 |

## 8. Datasets

Use only synthetic or approved controlled datasets. The committed
`capital_run_v1` fixture is the first regression sentinel; it is not enough
for production validation because it is generated by the same codebase and
is not an independent benchmark.

Independent validation under the engagement charter should add:

- hand-built small fixtures with closed-form expectations;
- adversarial edge-case fixtures (single observation, all-zero, extreme
  tails, single risk class);
- peer-model or spreadsheet references for major formulas;
- multi-Type-B-factor synthetic fixtures to exercise ρ-sensitivity in the
  capital path, not only in isolation;
- approved anonymized bank fixtures only after data-governance controls
  exist.

## 9. Acceptance evidence

Each sensitivity run records the following, per the reproducibility
guarantees in `docs/VALIDATION_ENGAGEMENT_CHARTER.md` §4:

- fixture identity and input hashes (`audit_inputs.compute_inputs_hash`);
- policy profile and `policy_hash`;
- code version (`frtb_ima.__version__`) and Python minor;
- parameter perturbation table;
- expected directional response;
- actual response and tolerance rationale;
- explanation for any non-monotonic or discontinuous behavior.

The current sweeps were produced by
`packages/frtb-ima/scripts/sensitivity_sweep.py`; the JSON output is
deterministic and reproducible by re-running the script against the same
fixture revision (`tests/fixtures/capital_run_v1/`).

Any sensitivity finding that causes a material model change is logged in
`06_change_history.md` per the ADR-0005 material-change policy.
