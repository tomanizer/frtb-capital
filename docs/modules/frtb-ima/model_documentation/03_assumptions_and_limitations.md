# Assumptions And Limitations

This document is the authoritative assumptions-and-limitations statement for the
`frtb-ima` capital model. It is structured so that validators can challenge each
assumption against the evidence that supports it, identify where the
implementation makes a defensible modelling choice, and identify where the
model boundary stops and upstream / downstream systems pick up.

Source of record for raw policy parameters:
[`REGULATORY_ASSUMPTIONS.md`](../../../../packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md).
Implementation-status inventory:
[`NPR_2_0_MARKET_RISK.yml`](../../../../packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml).
Architectural decision records: [`docs/decisions/`](../../../decisions/).

## 1. Modelling Basis

| Item | Statement |
|------|-----------|
| Primary regulatory profile | U.S. NPR 2.0 (proposed rule, March 2026) — treated as proposed material |
| Conceptual baseline | Basel FRTB MAR30–MAR33 and MAR99 (traffic-light multipliers) |
| Comparison anchors | EU CRR3 Articles 325ba–325bg and 325bk; Delegated Regulations (EU) 2022/2059 and 2022/2060; UK CRR / PRA rulebook placeholders |
| Package boundary | IMA desk-level capital assembly inside a multi-package suite — not a full FRTB calculator and not a firm-level consolidator |
| Validation status | Independent validation engagement defined in `docs/VALIDATION_ENGAGEMENT_CHARTER.md`; model is currently `under_validation` |

## 2. Core assumptions (cross-cutting)

| Area | Assumption | Conditions for validity | Evidence | Linked ADR |
|------|------------|------------------------|----------|------------|
| Sign convention — losses | Scenario cube, stress histories, NMRF artifact losses use positive-loss convention | All upstream producers conform; data-contract validators enforce on ingest | `data_contracts.py`, `nmrf.py`, fixture manifest | — |
| Sign convention — P&L | APL, HPL, RTPL use positive-profit convention; VaR uses positive magnitude | Backtesting exception is triggered when `-pnl > var` | `backtesting.py` | — |
| ES estimator | Weighted-interpolated ES is the policy default; discrete `ceil(n × (1−α))` tail mean retained for back-compat | Sufficient tail observations (≥ ~10 at α=0.975); see Section 5 of ADR 0004 | `expected_shortfall.py`; `test_reference_vectors.py` Uniform and truncated-normal references | ADR 0004 |
| Liquidity horizon set | Supported horizons {10, 20, 40, 60, 120} business days; LH10 always present | Risk factors are classified into one of the five buckets upstream | `regimes.py: DEFAULT_LIQUIDITY_HORIZONS`; `liquidity_horizon_mapping.py` | — |
| LHA construction | LHA ES is computed from *nested* risk-factor vector subsets, never from scalar scaling of an already-aggregated ES | Subsets are nested (LH20 ⊆ LH10, etc.); LH10 is the full set | `lha_builder.py`, `scenario_validation.py`; the toy scalar approximation in `liquidity_horizon.py` is isolated and used only in its own comparison tests | ADR 0008 |
| IMCC blend | `IMCC = 0.5 × unconstrained + 0.5 × Σ constrained_per_risk_class` | Both legs computed from the same nested LH vectors; weight is policy-controlled and documented | `imcc.py`; policy field `imcc_unconstrained_weight` | — |
| Type A SES aggregation | Zero-correlation root-sum-squares across Type A SES contributions (policy-selectable to conservative linear sum) | Type A factors are uncorrelated by assumption — see ADR 0006 for the modelling case | `nmrf.py`; policy field `type_a_ses_aggregation_mode` | ADR 0006 |
| Type B SES correlation | ρ = 0.36 fixed across Type B SES contributions | Anchored in U.S. NPR 2.0 proposed §`__.215` and Basel MAR33.16 | `regimes.py: type_b_ses_rho`; `nmrf.py` | — |
| PLA metrics | KS only for Fed NPR; KS + Spearman for ECB/PRA | Policy gate enforced at run boundary; KS thresholds 0.09/0.12, Spearman 0.80/0.70 | `pla.py`; `PLAMetricsRequired` enum | ADR 0007 |
| Supervisory multiplier | Basel MAR99 Table 2 step function from 1.5 (≤4 exceptions) to 2.0 (≥10) | Exception counts are the 12-month rolling figure at 99% level | `capital.py`; `regimes.py: DEFAULT_SUPERVISORY_MULTIPLIER_SCHEDULE` | — |
| Desk eligibility | Two-state guard: `IMA_ELIGIBLE` or `SA_FALLBACK` — no in-between traffic-light state inside the package | The package does not assemble SA capital; SA is a sibling-package responsibility | `regimes.py: DeskEligibilityStatus`; `capital.py: desk_eligibility_from_results` | ADR 0009 |
| Audit records as source of record | Post-run NDJSON audit records, not runtime logs, are the authoritative artifact for reproducibility | Records contain `model_version`, `code_version`, `policy_hash`, `inputs_hash`, `input_manifest` and pass `replay.py` reproduction | `audit.py`, `replay.py` | — |

## 3. Assumptions by calculation area

### 3.1 Expected shortfall

| Assumption | Detail |
|------------|--------|
| Single-period mark-to-loss | ES is computed on a single-period loss distribution. No multi-period chaining inside the ES function. |
| Estimator finite-sample bias | `WEIGHTED_INTERPOLATED` carries lower finite-sample bias than `DISCRETE_CEIL` at small sample sizes. Tail mass `n × (1−α)` is allocated proportionally between the full and partial tail observation. See ADR 0004. |
| Sample size requirement | The estimator is meaningful only when the implied tail count is at least 1 observation. The function does not impose a minimum higher than that; callers should configure the scenario set to give sufficient tail observations at the policy α (typically α = 0.975 → ~6 tail observations per 250 scenarios). |
| Independence from time ordering | ES treats scenario losses as exchangeable. Path dependence in the loss generation must be captured upstream. |

**Validator challenge / answer:** *"Why interpolated and not Harrell-Davis or kernel?"* — Interpolated ES is the simplest estimator that removes the discrete bias of `ceil`-based tail mean while remaining estimator-free of bandwidth choices. ADR 0004 records the trade-off explicitly.

### 3.2 Liquidity horizon adjustment

| Assumption | Detail |
|------------|--------|
| Nested vector construction | Each LH bucket vector is built from the *subset* of risk factors with LH ≥ that bucket, applied to the same scenarios. Not a scalar scaling of an already-aggregated ES. |
| LH10 mandatory | Every LHA computation requires the LH10 subset (the full set of risk factors); enforced by `lha_builder` and `scenario_validation`. |
| Square-root-of-time inside `√(Σ wᵢ × ES²ᵢ)` | The combination formula assumes Gaussian-like additivity of squared ES across horizons. This is a regulatory specification, not a derivation; we implement it as written. |
| LH category-to-horizon mapping | The regulatory category table from NPR 2.0 / MAR33 is provided in `liquidity_horizon_mapping.py`. Caller-supplied policy hooks can override per supervisor-approved deviations. |

**Validator challenge / answer:** *"Does the scalar approximation appear anywhere in production calculation paths?"* — No. It exists in `liquidity_horizon.py` as a labelled comparison helper used only by its own comparison tests; verified by grep. ADR 0008 records the nested-vector decision.

### 3.3 IMCC

| Assumption | Detail |
|------------|--------|
| 50/50 unconstrained-vs-constrained blend | Implemented as the policy default per Basel MAR33 / NPR 2.0 §`__.214`. The 0.5 weight is policy-controlled (`imcc_unconstrained_weight`) to support sensitivity analysis. |
| Per-risk-class constrained term | Each risk class contributes its independently-aggregated LHA ES; classes are summed (no correlation discount across classes in the constrained term). |
| Reduced-set scaling factor | When the reduced risk-factor set is used, the IMCC is scaled by the variation-explained ratio (≥ 75% threshold per policy). The implementation supports the selector workflow per `reduced_set.py` but does not embed reduced-set governance. |

**Validator challenge / answer:** *"What happens if the reduced set does not meet the 75% threshold?"* — Selection fails with a policy-aware error before IMCC is computed; capital cannot be assembled until reduced-set governance is satisfied or the threshold is policy-modified.

### 3.4 RFET (Risk-Factor Eligibility Test)

| Assumption | Detail |
|------------|--------|
| Two paths exist by design | `rfet.py` is the fast scalar classification; `rfet_evidence.py` is the audit-grade path with full exclusion trails. They are not duplicate implementations — the audit-grade path is the source of record for validator review. |
| Modellability thresholds | Short-LH risk factors (LH ≤ 20 days): ≥ 24 real-price observations over the 365-day lookback (`rfet_short_lh_threshold = 24`, `rfet_short_lh_max_days = 20`, `rfet_lookback_days = 365`). Long-LH risk factors (LH > 20 days): ≥ 16 real-price observations over the same window (`rfet_long_lh_threshold = 16`). Implemented per Basel MAR31.12 and NPR 2.0 §`__.212`. |
| Observation de-duplication | One eligible observation per business date per risk factor; source de-duplication per bucket; representativeness check on bucket membership. |
| New-issuance prorating | Opt-in feature for risk factors with insufficient history due to recent issuance. Disabled by default. |
| Vendor data, data-pooling | Out of scope. The package validates evidence in the form it receives; it does not implement vendor reliance rules or RTS-level data-pooling controls. |

**Validator challenge / answer:** *"How are timestamp-normalisation and timezone questions handled?"* — `rfet_evidence.py` enforces one-count-per-date using the supplied date; timezone normalisation is upstream. This is recorded as a documented partial-implementation in `NPR_2_0_MARKET_RISK.yml`.

### 3.5 NMRF (Non-Modellable Risk Factors) and SES

| Assumption | Detail |
|------------|--------|
| Method selection is governance, not pricing | `nmrf_method_selection.py` decides between direct, stepwise, full-revaluation, and max-loss methods based on evidence the caller supplies. The package does not price trades. |
| Valuation artifacts are upstream | `nmrf_valuation_run.py` reconciles returned artifacts against the issued specifications and fails hard on mismatch. Artifacts include `generated_by_prototype` flags; production runs reject prototype artifacts unless explicitly allowed. |
| Type A vs Type B taxonomy | U.S. NPR 2.0 terminology. ECB CRR3 and PRA UK CRR policies emit an `UnsupportedFeature` notice for the taxonomy. |
| Stress period | Selected from supplied historical loss/severity vectors per risk class. The selection algorithm is the rolling-window maximum-severity rule; tie-breaking is policy-controlled. |
| SES aggregation | Type A: zero-correlation root-sum-squares (or conservative linear sum). Type B: ρ = 0.36 fixed correlation. Aggregation is over SES values, not over individual NMRF losses. |

**Validator challenge / answer:** *"How does the package prevent prototype artifacts from being used in real runs?"* — `NMRFValuationRunResult` carries a `generated_by_prototype` flag per artifact; reconciliation in `nmrf_valuation_run.py` rejects prototype artifacts unless `allow_prototype_artifacts=True` is explicitly set, which is a deliberate audit-visible action.

### 3.6 PLA and backtesting

| Assumption | Detail |
|------------|--------|
| Aligned observation set | The package assumes the caller has aligned HPL, RTPL, APL, and VaR vectors by business date. Alignment is upstream. |
| Business-calendar governance | Optional caller-supplied calendars and official-holiday masks are supported; full calendar governance is upstream. |
| KS statistic | Computed via vectorised empirical CDFs in numpy — no `scipy` dependency in the core path. |
| Spearman correlation | Custom average-rank implementation in `pla.py` — no `scipy` dependency. EU/PRA path is gated on `PLAMetricsRequired.KS_AND_SPEARMAN`. |
| Zone aggregation | The worse-of KS and Spearman zones is the assigned zone for EU/PRA. The aggregation rule is documented and tested in `pla.py:_worse_zone`. |
| Exception counts | Trailing window of 250 business days at the policy α (default 0.975 and 0.99). Exceptions are counted per level; eligibility derives from the worst level. |

**Validator challenge / answer:** *"Are KS and Spearman tested against an independent implementation?"* — Yes: `test_reference_vectors.py` compares the in-package KS and Spearman against `scipy.stats.ks_2samp` (asymptotic statistic) and `scipy.stats.spearmanr` as peer-library references, with `abs=1e-15` tolerance. The in-package implementations remain numpy-only — scipy appears only in the reference-vector tests, not in the calculation path.

### 3.7 Capital assembly

| Assumption | Detail |
|------------|--------|
| Spot-vs-average formula | `MBC = max(IMCC_{t-1} + SES_{t-1}, multiplier × IMCC_60d_avg + SES_60d_avg) + PLA_addon` — per MAR33 / NPR 2.0 proposed §`__.214`. |
| Eligibility hard gate | If the desk is `SA_FALLBACK`, models-based capital raises `IMAIneligibleError`. SA capital assembly is not in scope. |
| PLA add-on | NPR-style add-on computed only for green/amber desks via the `k = 0.5 × standardized_amber / standardized_green_amber` formula. Red zone forces SA fallback. |
| Floor enforcement | Multiplier floor of 1.50 is enforced numerically; cannot be circumvented by policy override. |

**Validator challenge / answer:** *"What if the spot and average terms are extremely close?"* — `CapitalComponents.binding_term` records `"SPOT"` or `"AVERAGE"` deterministically per the `>=` rule; reproducible across runs.

## 4. Boundary conditions

The package enforces these contracts at every public function:

| Contract | Enforced by |
|----------|-------------|
| Input arrays are non-empty | `_validate_*` helpers in each module |
| Input arrays contain only finite values | numpy `isfinite` checks at every ingest |
| Vector lengths match across aligned inputs (positions, risk factors, dates) | `data_contracts.py`, `scenario_validation.py` |
| LH10 is present in every nested LH subset | `lha_builder.py`, `scenario_validation.py` |
| SHA-256 hashes are exactly 64 hex characters | `audit.py: _validate_sha256_hex` |
| Capital values cannot be negative where regulatorily impossible | `_validate_non_negative_finite` in `capital.py` |
| Multiplier ≥ 1.50 | `capital.py: models_based_capital` |
| Sign conventions hold | Documented in each module docstring; tested per module |

## 5. Implemented boundaries

Implementations covered by the calculation gate (90% coverage floor, 95% target):

- Validated data contracts for positions, risk factors, RFET evidence, scenario cubes, desk runs, and capital-run outputs.
- RFET scalar and audit-grade evidence-assessment paths.
- Expected shortfall (both estimators), LHA ES, IMCC (unconstrained and constrained), reduced-set diagnostics + selection workflow, stress-period selection from supplied vectors.
- NMRF method selection, valuation-run specifications, valuation-run artifact reconciliation, SES aggregation (Type A and Type B).
- PLA (KS and Spearman, with regime-gated metric requirement) and backtesting (with optional business-calendar / holiday masks).
- Desk capital assembly with PLA add-on, supervisory multiplier mapping, and the `IMAIneligibleError` gate.
- Deterministic synthetic capital-run fixture, validation notebooks, audit report rendering, NDJSON serialisation, replay CLI.
- Cross-Python-minor determinism registry (3.11 / 3.12 / 3.13).
- Independent numerical reference vectors using scipy analytic forms.
- Hypothesis property tests for ES, IMCC, LHA, NMRF, PLA, capital.
- Mutation-testing baseline.

## 6. Material limitations

The following are *not* full production workflows and must be challenged or substituted by validation:

| Limitation | Compensating control | Closure plan |
|------------|---------------------|--------------|
| No regulatory final-rule interpretation or legal sign-off | Citations point to proposed material; ADRs record modelling choices | Legal review before production use |
| No trading-desk approval lifecycle (loss of eligibility, remediation, re-entry) | Two-state guard at the calculation boundary | External workflow integration |
| SBM, DRC, RRAO, CVA, SA fallback, firm-level consolidation out of scope | Sibling packages own these | Suite-level integration |
| No market-data sourcing, instrument classification, trade enrichment, vendor data lineage | Input manifest carries data-source identifiers; data-contract validators check shape and finiteness | Upstream system integration |
| RFET data-pooling controls not implemented | Caller-supplied evidence accepted as-is; documented partial in `NPR_2_0_MARKET_RISK.yml` (NPR-MR-RFET-002) | Vendor / pooling layer |
| Institutional pricing and revaluation engines for NMRF stress not implemented | Artifacts are reconciled and validated, never priced; prototype artifacts gated behind explicit flag | Pricing-engine integration |
| Full business-calendar governance not implemented | Optional caller-supplied calendars + holiday masks accepted | Calendar service integration |
| Formal stress-period approval governance not implemented | Selection algorithm is deterministic and reproducible; selection is policy-controlled | Governance workflow |
| Reduced-set data-quality proof beyond 60-day / 75% variation-explained diagnostic | Diagnostic is implemented; selector emits the evidence trail | Data-quality controls |
| Production telemetry, large-run storage, Parquet/DuckDB analytics | Audit records are NDJSON-serialisable; downstream storage is orchestration-layer | Orchestration / observability stack |
| Final regulatory disclosure templates | Audit report rendering exists; disclosure templates are jurisdiction-specific | Regulatory-reporting layer |

## 7. Things explicitly NOT assumed

This section exists to prevent over-interpretation of model scope. The model does **not** assume:

- That market-data quality has been independently verified upstream.
- That trade valuations used to construct the scenario cube are themselves model-validated.
- That every risk factor in the input data is in fact in scope per supervisor approval — that determination is upstream.
- That historical loss series supplied for stress-period selection have been calibration-approved.
- That ECB CRR3 or PRA UK CRR policies are fully implemented — both regimes emit `UnsupportedFeature` notices for known gaps.
- That `generated_by_prototype` NMRF artifacts are acceptable in production runs — they are not, by default.
- That a single capital run constitutes evidence of correctness — only the regression fixture + reference vectors + determinism registry together provide evidence.

## 8. Validation implications

For an independent validation pass per the engagement charter, the highest-leverage challenge areas are:

| Area | Challenge question | Where to find evidence |
|------|-------------------|------------------------|
| Conceptual soundness | Are nested-vector LHA, 50/50 IMCC blend, Type A/B SES taxonomy, and PLA traffic-light all consistent with cited regulation? | `01_conceptual_soundness.md`, `02_derivation.md`, ADRs 0004, 0006, 0007, 0008, 0009 |
| Numerical accuracy | Do ES, KS, Spearman, multiplier, SES outputs match independent references within tolerance? | `tests/test_reference_vectors.py`, `tests/fixtures/capital_run_v1/` |
| Determinism | Do outputs hash identically across Python 3.11 / 3.12 / 3.13? | `tests/test_determinism.py`, `tests/fixtures/determinism/*.sha256` |
| Parameter citations | Is every regulatory parameter sourced from `RegulatoryPolicy.cited_by` rather than a hardcoded module constant? | `regimes.py: REGULATORY_PARAMETER_CITATIONS` |
| Material limitations | Are the boundaries between this package and upstream / downstream systems exactly as stated, with no implicit assumption? | This document, Section 6 |
| Reproducibility | Can MRM reproduce any committed audit record from the inputs, independently? | `replay.py`, `VALIDATION_PACK.md` |
| Material-change response | Will methodology changes re-enter validation as defined? | ADR 0005, this engagement charter |

Validation findings should be filed per the workflow in `docs/VALIDATION_ENGAGEMENT_CHARTER.md` §7.
