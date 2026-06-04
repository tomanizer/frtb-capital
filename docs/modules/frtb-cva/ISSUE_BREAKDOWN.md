# frtb-cva workable issue breakdown

These were implementation-ready issue drafts derived from
[DETAILED_REQUIREMENTS.md](DETAILED_REQUIREMENTS.md). They are retained as
historical planning evidence for the v1 delivery sequence. Current runtime
status is tracked in
[BASEL_FRTB_CVA.yml](../../../packages/frtb-cva/docs/requirements/BASEL_FRTB_CVA.yml) and
[packages/frtb-cva/docs/REGULATORY_TRACEABILITY.md](../../../packages/frtb-cva/docs/REGULATORY_TRACEABILITY.md).
Cross-cutting changes to `frtb-common` or orchestration should still reference
an ADR when they change shared contracts.

The historical issue sequence superseded PRD delivery-slice ordering where they
differed. See
[CVA-DEC-011](DECISIONS_AND_PLAN.md#cva-dec-011-issue-sequence-supersedes-prd-delivery-slice-ordering).

Requirement IDs in parentheses map to the detailed requirements document.

## Issue 1: Add CVA model documentation and traceability skeleton

**Goal:** Create the documentation pack that CVA implementation PRs kept
current during the v1 delivery sequence.

**Scope:**

- Add package-local `docs/REGULATORY_TRACEABILITY.md`,
  `docs/REGULATORY_ASSUMPTIONS.md`, and `docs/regulatory_sources.yml` under
  `packages/frtb-cva/`.
- Keep [ARCHITECTURE_AND_DATA_DESIGN.md](ARCHITECTURE_AND_DATA_DESIGN.md) and
  [DECISIONS_AND_PLAN.md](DECISIONS_AND_PLAN.md) current as implementation
  evolves.
- Expand [BASEL_FRTB_CVA.yml](../../../packages/frtb-cva/docs/requirements/BASEL_FRTB_CVA.yml) to map
  detailed requirement IDs to modules and tests.
- Update [docs/regulatory/crosswalk/frtb-cva.yml](../../regulatory/crosswalk/frtb-cva.yml)
  with Basel MAR50 and planned U.S./EU source refs.
- Cross-link module docs, package README, and requirements registry.

**Acceptance criteria:**

- Documentation distinguishes scaffold, planned, partial, and implemented
  status.
- No document presents CVA outputs as final regulatory capital.
- All source links point to primary regulatory sources or clearly marked
  implementation references.
- July 2020 calibration revision (`m_CVA = 1.0`, `D_BA-CVA = 0.65`) is noted
  where profile tables are described.
- Requirements registry entries reference `CVA-FUNC-*`, `CVA-BOUNDARY-*`, and
  `CVA-NFR-*` ids from [DETAILED_REQUIREMENTS.md](DETAILED_REQUIREMENTS.md).

**Tests/checks:** docs link check if available; existing package scaffold tests.

**Maps to:** CVA-BOUNDARY-001, CVA-NFR-008.

## Issue 2: Implement CVA data models and validation errors

**Goal:** Add frozen package-local data structures without capital calculation.

**Scope:**

- Add `data_models.py` with CVA enums and frozen dataclasses.
- Add `validation.py` with `CvaInputError`, invariant checks, and
  normalisation helpers.
- Keep `calculate_cva_capital` failing until the first capital slice lands.

**Acceptance criteria:**

- Public models cover `CvaCounterparty`, `CvaNettingSet`, `CvaHedge`,
  `SaCvaSensitivity`, `BaCvaStandAloneLine`, `BaCvaCounterpartyCapital`,
  `SaCvaWeightedSensitivity`, `SaCvaBucketCapital`, `SaCvaRiskClassCapital`,
  and `CvaCapitalResult`.
- Enums cover CVA method, risk class (GIRR, FX, CCS, RCS, equity, commodity),
  risk measure (delta, vega), sensitivity tag (`CVA`, `HDG`), hedge type, and
  eligibility status.
- Counterparty records include `region`; netting-set records include
  `uses_imm_ead`; SA-CVA sensitivity records include optional `volatility_input`
  for vega paths.
- Invalid enum, missing identity, duplicate stable id, non-finite amount,
  negative EAD, missing lineage, and implicit sign paths fail deterministically.
- No sibling package imports.

**Tests/checks:** `tests/test_data_models.py`, `tests/test_validation.py`.

**Maps to:** CVA-FUNC-002–005, CVA-BOUNDARY-002, CVA-NFR-004.

## Issue 3: Add CVA rule-profile and reference-data layer (Basel MAR50 first slice)

**Goal:** Implement cited profile lookup for reduced BA-CVA and the first SA-CVA
risk class.

**Scope:**

- Add `regimes.py` and `reference_data.py`.
- Add Basel MAR50 profile id, source publication metadata, and July 2020
  calibration metadata.
- Add BA-CVA Table 1 sector/credit-quality risk weights (MAR50.16), `α = 1.4`,
  `ρ`, and `D_BA-CVA = 0.65` (MAR50.14–MAR50.15).
- Add non-IMM discount-factor policy (`DF = (1 - exp(-0.05 · M)) / (0.05 · M)` or
  explicit supplied DF) (MAR50.15(4)).
- Add GIRR delta bucket, tenor, risk-weight, and correlation tables needed for
  the first SA-CVA fixture (MAR50.54–MAR50.57).
- Add profile hash generation.
- Explicitly mark full BA-CVA, non-GIRR SA-CVA classes, vega, qualified-index
  option, materiality-threshold alternative, and U.S./EU comparison profiles
  unsupported until mapped.

**Acceptance criteria:**

- Every table entry has a citation id.
- Missing lookup keys raise a package input error.
- Profile hash is deterministic.
- Unsupported profiles fail before calculation.

**Tests/checks:** `tests/test_reference_data.py`, `tests/test_regimes.py`.

**Maps to:** CVA-BOUNDARY-005, CVA-FUNC-009, CVA-FUNC-015.

## Issue 4: Implement scope, method selection, and carve-out policy

**Goal:** Encode CVA scope and method routing without calculating capital.

**Scope:**

- Add `scope.py` and extend `regimes.py` with method-selection policy.
- Support BA-CVA default, SA-CVA approval flag, netting-set carve-out to
  BA-CVA (MAR50.8), and explicit unsupported materiality-threshold alternative
  (MAR50.9).
- Record covered-transaction exclusions and regulatory-vs-accounting CVA flags
  as audit metadata only.
- Reject mixed-method runs with incomplete carve-out evidence.

**Acceptance criteria:**

- Method selection is explicit in calculation context and result metadata.
- Carve-out netting sets are routed to BA-CVA when SA-CVA is selected globally.
- Materiality-threshold requests fail closed with cited reason.
- No capital is computed in this issue.

**Tests/checks:** `tests/test_scope.py`, `tests/test_unsupported_features.py`.

**Maps to:** CVA-FUNC-006, CVA-FUNC-022.

## Issue 5: Implement BA-CVA stand-alone counterparty capital

**Goal:** Calculate `SCVA_c` from netting-set inputs.

**Scope:**

- Add `ba_cva.py` stand-alone functions.
- Apply MAR50.15: `α`, `RW_c`, `M_NS`, `EAD_NS`, `DF_NS` per netting set.
- Aggregate netting sets to counterparty stand-alone capital.
- Preserve sector/credit-quality lookup, EAD, maturity, discount factor, and
  citation ids.
- Reject missing EAD, maturity, or risk-weight keys.

**Acceptance criteria:**

- Sovereign IG and financial HY examples produce deterministic stand-alone
  capital.
- IMM vs non-IMM discount-factor branches are profile-driven.
- Invalid exposure inputs fail before calculation.
- Full BA-CVA and SA-CVA requests remain unsupported at public API.

**Tests/checks:** `tests/test_ba_cva_standalone.py`.

**Maps to:** CVA-FUNC-008, CVA-FUNC-003, CVA-FUNC-009.

## Issue 6: Implement BA-CVA reduced portfolio aggregation

**Goal:** Calculate `K_reduced` and apply `D_BA-CVA`.

**Scope:**

- Extend `ba_cva.py` with MAR50.14 portfolio formula using ρ = 50%.
- Sum systematic and idiosyncratic components across counterparties.
- Apply discount scalar `D_BA-CVA = 0.65`.
- Emit counterparty and total reduced BA-CVA records.

**Acceptance criteria:**

- Multi-counterparty portfolio produces lower total than simple sum of
  stand-alone capitals where ρ < 100%.
- Single-counterparty portfolio equals scaled stand-alone capital.
- Component records reconcile to total reduced BA-CVA.

**Tests/checks:** `tests/test_ba_cva_reduced.py`.

**Maps to:** CVA-FUNC-008.

## Issue 7: Add public reduced BA-CVA run API and audit records

**Goal:** Replace scaffold failure for supported reduced BA-CVA runs with a real
`CvaCapitalResult`.

**Scope:**

- Add `capital.py` public entry point wiring validation, scope, profile lookup,
  and reduced BA-CVA.
- Add `audit.py` for deterministic result serialisation, input hash, profile
  hash, and reconciliation checks.
- Keep SA-CVA, full BA-CVA, and mixed-method requests failing explicitly.

**Acceptance criteria:**

- `calculate_cva_capital` returns frozen `CvaCapitalResult` for supported reduced
  BA-CVA inputs.
- Result includes method, rule-profile hash, input hash, counterparty lines,
  netting-set lineage, citations, and warnings.
- Reconciliation errors fail tests.

**Tests/checks:** `tests/test_public_api.py`, `tests/test_audit.py`,
`tests/test_replay.py`.

**Maps to:** CVA-FUNC-001, CVA-FUNC-023, CVA-FUNC-024.

## Issue 8: Add synthetic reduced BA-CVA validation fixture

**Goal:** Provide a deterministic fixture pack for the first capital-producing
slice.

**Scope:**

- Add `tests/fixtures/ba_cva_reduced_v1/`.
- Include sovereign IG, local-government IG, financial HY, multi-netting-set
  counterparty, IMM discount factor 1.0, non-IMM discount factor, invalid EAD,
  missing risk weight, and missing maturity cases.
- Add fixture loader, expected outputs, and manifest.

**Acceptance criteria:**

- Fixture result is deterministic across supported Python versions.
- Expected outputs cover stand-alone, counterparty, and total reduced BA-CVA.
- Fixture docs explain each regulatory case and citation id.

**Tests/checks:** `tests/test_ba_cva_fixture_workflow.py`, determinism test.

**Maps to:** CVA-NFR-005, CVA-NFR-006.

## Issue 9: Implement hedge eligibility contracts and validation

**Goal:** Represent eligible and ineligible CVA hedges without applying capital
benefit yet.

**Scope:**

- Add `hedges.py` eligibility checks and lineage records.
- Support BA-CVA hedge instrument types (MAR50.18–MAR50.19) and SA-CVA whole-
  transaction eligibility (MAR50.37–MAR50.39).
- Support internal vs external flags and curvature/default/RRAO back-to-back
  evidence requirements (MAR50.11(5)).
- Record CCS vs RCS assignment for credit-spread hedges (MAR50.44).
- Reject split instruments and ineligible types with reason codes.

**Acceptance criteria:**

- Eligible single-name CDS with direct reference passes validation.
- Ineligible tranched credit derivative is rejected.
- Internal hedge without back-to-back evidence is marked ineligible for SA-CVA
  hedge sensitivities.
- No hedge capital benefit is applied in this issue.

**Tests/checks:** `tests/test_hedges.py`, `tests/test_unsupported_features.py`.

**Maps to:** CVA-FUNC-004, CVA-FUNC-007, CVA-BOUNDARY-006.

## Issue 10: Implement SA-CVA weighted sensitivity calculation

**Goal:** Convert canonical CVA and hedge sensitivities into weighted records.

**Scope:**

- Add `weighted_sensitivity.py`.
- Compute `WS_k^CVA`, `WS_k^Hdg`, and net `WS_k = WS_k^CVA − WS_k^Hdg`
  (MAR50.51–MAR50.52).
- Sum duplicate portfolio risk-factor keys deterministically before weighting.
- Include only eligible hedge rows in hedge-weighted amounts.
- Preserve gross CVA, gross hedge, and net values.
- Keep aggregation and public SA-CVA API unsupported until Issue 12.

**Acceptance criteria:**

- Supported GIRR delta rows produce weighted sensitivities with stable ids.
- Missing risk weights fail explicitly.
- Ineligible hedge rows do not reduce net weighted sensitivity unless explicitly
  excluded with audit note.
- Reduced BA-CVA behavior is unchanged.

**Tests/checks:** `tests/test_weighted_sensitivity.py`.

**Maps to:** CVA-FUNC-012.

## Issue 11: Implement SA-CVA shared aggregation engine

**Goal:** Produce bucket and risk-class capital using reusable primitives.

**Scope:**

- Add `aggregation.py`.
- Implement intra-bucket `K_b` with ρ_kl and hedging disallowance `R = 0.01`
  (MAR50.53(1)).
- Implement inter-bucket aggregation with γ_bc, `S_b` floor/cap, and `m_CVA`
  (MAR50.53(2)–(3)).
- Preserve correlation evidence and branch metadata.
- Keep public SA-CVA API unsupported until Issue 12.

**Acceptance criteria:**

- Bucket totals reconcile to weighted sensitivities used.
- `S_b` floor/cap behavior matches cited formula for fixture inputs.
- Aggregation order is deterministic.
- Hedging disallowance term prevents perfect hedge recognition in test cases.

**Tests/checks:** `tests/test_aggregation.py`.

**Maps to:** CVA-FUNC-013, CVA-FUNC-014.

## Issue 12: Deliver the first SA-CVA GIRR delta public API slice

**Goal:** Add SA-CVA capital for GIRR delta alongside existing reduced BA-CVA.

**Scope:**

- Add `sa_cva.py` orchestration and `risk_classes/girr.py`.
- Wire validation, eligibility, weighting, aggregation, and total SA-CVA result
  for **GIRR delta scope** in this historical issue.
- Sum delta risk classes per MAR50.43; total SA-CVA equals GIRR delta for this
  slice.
- Extend public API to accept method = SA-CVA with GIRR delta sensitivities.
- Keep GIRR vega (MAR50.58), non-GIRR classes, and other vega paths failing
  explicitly until Issues 14–18 and 26–27.

**Acceptance criteria:**

- `calculate_cva_capital` returns `CvaCapitalResult` for supported SA-CVA GIRR
  delta inputs.
- Result includes pre- and post-`m_CVA` risk-class totals, bucket records, and
  CVA/HDG/NET sensitivity lineage.
- SA-CVA total reconciles to GIRR delta capital.
- Reduced BA-CVA behavior is unchanged.

**Tests/checks:** `tests/test_sa_cva.py`, `tests/test_public_api.py`,
`tests/risk_classes/test_girr.py`.

**Maps to:** CVA-FUNC-001, CVA-FUNC-011, CVA-FUNC-015, CVA-FUNC-023.

## Issue 13: Add synthetic SA-CVA GIRR delta validation fixture

**Goal:** Prove the SA-CVA engine on a hand-worked GIRR delta case.

**Scope:**

- Add `tests/fixtures/sa_cva_girr_delta_v1/`.
- Include single-currency bucket, multi-bucket currency pair, CVA-only, CVA+hedge
  offset, ineligible hedge rejected, and missing risk-weight cases.
- Document positive-CVA sign convention (MAR50.32(1), MAR50.52 footnote).

**Acceptance criteria:**

- Fixture results are deterministic.
- Expected outputs cover weighted sensitivities, buckets, risk-class total, and
  post-multiplier capital.
- Hedge offset case shows gross CVA, gross hedge, and net amounts separately.

**Tests/checks:** fixture workflow test and determinism test.

**Maps to:** CVA-NFR-005, CVA-NFR-006.

## Issue 14: Implement SA-CVA FX delta path

**Goal:** Add cited FX delta support through the shared SA-CVA engine.

**Scope:**

- Add `risk_classes/fx.py`.
- Add MAR50.59–MAR50.61 bucket definitions, delta risk weights, and γ_bc = 0.6.
- Support reporting-currency leg decomposition for non-reporting pairs.
- Reuse shared weighting and aggregation primitives.
- Keep FX vega (MAR50.62) unsupported until Issue 27.

**Acceptance criteria:**

- FX delta fixtures reconcile by bucket and risk class.
- SA-CVA total sums GIRR and FX delta capitals.
- FX vega requests fail explicitly.
- GIRR behavior is unchanged.

**Tests/checks:** `tests/risk_classes/test_fx.py`.

**Maps to:** CVA-FUNC-016.

## Issue 15: Implement SA-CVA counterparty credit spread (CCS) path

**Goal:** Add cited CCS delta support; no CCS vega in this issue.

**Scope:**

- Add `risk_classes/ccs.py`.
- Add MAR50.63–MAR50.65 buckets 1–7, risk weights, ρ_kl, and γ_bc tables.
- Enforce no vega capital for CCS (MAR50.45, MAR50.63).
- Keep qualified-index bucket 8 unsupported until Issue 20.

**Acceptance criteria:**

- CCS delta fixtures reconcile by bucket and risk class.
- CCS vega requests fail explicitly.
- Existing SA-CVA classes are unchanged.

**Tests/checks:** `tests/risk_classes/test_ccs.py`.

**Maps to:** CVA-FUNC-017.

## Issue 16: Implement SA-CVA reference credit spread (RCS) path

**Goal:** Add cited RCS delta and vega support.

**Scope:**

- Add `risk_classes/rcs.py`.
- Add MAR50.66–MAR50.69 bucket structure, risk weights, γ_bc, and vega weight
  formula.
- Apply divide-by-2 cross-quality γ_bc rule (MAR50.67(2)).

**Acceptance criteria:**

- RCS delta and vega fixtures reconcile separately and sum into SA-CVA total.
- Cross-quality bucket pairs use halved correlations in test cases.
- CCS behavior is unchanged.

**Tests/checks:** `tests/risk_classes/test_rcs.py`.

**Maps to:** CVA-FUNC-018.

## Issue 17: Implement SA-CVA equity path

**Goal:** Add cited equity delta and vega support.

**Scope:**

- Add `risk_classes/equity.py`.
- Add MAR50.70–MAR50.73 bucket structure, market-cap metadata hooks, delta risk
  weights, vega `RW_σ` scalars, and γ_bc rules.
- Keep qualified-index buckets 12–13 unsupported until Issue 20 unless simple
  single-name fixtures can pass without index option.

**Acceptance criteria:**

- Equity delta and vega fixtures reconcile by bucket.
- Bucket 11 cross-bucket γ_bc = 0% behavior is tested.
- Existing SA-CVA classes are unchanged.

**Tests/checks:** `tests/risk_classes/test_equity.py`.

**Maps to:** CVA-FUNC-019.

## Issue 18: Implement SA-CVA commodity path

**Goal:** Add cited commodity delta and vega support.

**Scope:**

- Add `risk_classes/commodity.py`.
- Add MAR50.74–MAR50.77 bucket definitions, risk weights, γ_bc, and vega weights.
- Complete SA-CVA delta and vega sum across all six/five risk classes.

**Acceptance criteria:**

- Commodity delta and vega fixtures reconcile.
- Total SA-CVA equals sum of all supported delta and vega risk-class capitals
  (MAR50.42).
- Existing SA-CVA classes are unchanged.

**Tests/checks:** `tests/risk_classes/test_commodity.py`, `tests/test_sa_cva.py`.

**Maps to:** CVA-FUNC-020.

## Issue 19: Implement BA-CVA full version with hedge recognition

**Goal:** Add MAR50.17–MAR50.26 full BA-CVA on top of reduced BA-CVA.

**Scope:**

- Extend `ba_cva.py` with `K_hedged`, `SNH_c`, `IH`, `HMA_c`, and β floor.
- Apply Table 2 hedge-counterparty correlations (MAR50.26).
- Apply index hedge RW 0.7 scalar (MAR50.24).
- Always compute reduced BA-CVA alongside full result.
- Integrate eligible hedge records from Issue 9.

**Acceptance criteria:**

- Full BA-CVA never falls below `β · K_reduced`.
- Direct-reference hedge reduces capital; misaligned indirect hedge triggers
  `HMA_c`.
- Ineligible hedge records produce zero hedge benefit with cited reason.
- SA-CVA behavior is unchanged.

**Tests/checks:** `tests/test_ba_cva_full.py`.

**Maps to:** CVA-FUNC-010.

## Issue 20: Implement qualified-index option for CCS, RCS, and equity

**Goal:** Add MAR50.50 index-bucket treatment where profile permits.

**Scope:**

- Extend CCS, RCS, and equity modules with qualified-index risk factors.
- Support look-through vs index-bucket routing and >75% sector concentration
  rule.
- Add index fixtures for at least one class.

**Acceptance criteria:**

- Qualified index assigned to index bucket avoids constituent sensitivity
  requirement where criteria are met.
- Non-qualified index without look-through fails closed.
- Single-name and index paths reconcile to cited examples.

**Tests/checks:** `tests/test_qualified_index.py`,
`tests/risk_classes/test_ccs.py`, `tests/risk_classes/test_equity.py`.

**Maps to:** CVA-FUNC-021.

## Issue 21: Implement mixed-method carve-out assembly

**Goal:** Support SA-CVA with BA-CVA fallback for carved-out netting sets.

**Scope:**

- Extend `capital.py` to run SA-CVA and reduced/full BA-CVA components in one
  public result.
- Prevent double-counting of hedges across methods.
- Preserve component lineage in audit records.

**Acceptance criteria:**

- Carve-out fixture runs SA-CVA on in-scope sensitivities and BA-CVA on carved
  netting sets.
- Total equals sum of supported components with explicit component breakdown.
- Incomplete carve-out evidence fails closed.

**Tests/checks:** `tests/test_mixed_method.py`.

**Maps to:** CVA-FUNC-022.

## Issue 22: Add optional CRIF/vendor-to-canonical CVA adapter

**Goal:** Convert external sensitivity and exposure rows into canonical records
without dataframe runtime dependencies.

**Scope:**

- Add `crif.py` with standard-library mapping.
- Map counterparty, netting-set, hedge, and SA-CVA sensitivity columns.
- Record source column lineage and sign-convention mapping.

**Acceptance criteria:**

- Adapter does not import `pandas`.
- Adapter output uses canonical package records only.
- Ambiguous CVA/HDG tagging or sign conventions are rejected or flagged in
  lineage.

**Tests/checks:** `tests/test_crif.py`.

**Maps to:** CVA-FUNC-026.

## Issue 23: Add orchestration handoff for CVA output

**Goal:** Define how `frtb-orchestration` consumes `CvaCapitalResult`.

**Scope:**

- Add orchestration contract types or adapters only after CVA result shape is
  stable.
- Keep top-of-house aggregation explicit about BA-CVA vs SA-CVA components.
- Add unimplemented aggregation error where required suite inputs are missing.

**Acceptance criteria:**

- Orchestration can recognise a CVA package result.
- CVA remains separate from SA composition (SBM + DRC + RRAO).
- No orchestration imports leak into CVA kernels.

**Tests/checks:** orchestration package tests.

**Maps to:** CVA-BOUNDARY-001.

## Issue 24: Add performance and replay controls

**Goal:** Verify deterministic behaviour and practical runtime at synthetic
scale.

**Scope:**

- Add benchmark script or test marker for large BA-CVA and SA-CVA fixtures.
- Add replay hash checks for audit outputs.
- Document target scale (10k netting sets / 100k sensitivities) and observed
  runtime in package performance docs.

**Acceptance criteria:**

- Large fixtures run without dataframe runtime dependencies.
- Hash checks detect output ordering or numeric drift.
- Performance docs are updated.

**Tests/checks:** targeted benchmark command, replay tests.

**Maps to:** CVA-NFR-001, CVA-NFR-007.

## Issue 25: Add attribution and impact assessment

**Goal:** Add optional analytical attribution and change-impact outputs after
core CVA is stable.

**Scope:**

- Implement `attribution.py` for analytical Euler contribution on supported
  stable SA-CVA and BA-CVA branches.
- Implement `impact.py` for baseline-vs-candidate capital deltas.
- Reconcile contribution records where exact reconciliation is valid; report
  residuals for sqrt/floor/cap branches.
- Label finite-difference impact separately from analytical marginal
  contribution.

**Acceptance criteria:**

- Analytical contributions sum to total within tolerance for supported
  fixtures.
- Unsupported formulas, branch changes, floors, and zero denominators report
  explicit method/residual metadata.
- Capital totals do not change when attribution or impact is requested.

**Tests/checks:** `tests/test_attribution.py`, `tests/test_impact.py`.

**Maps to:** CVA-FUNC-025, ADR 0012.

## Issue 26: Implement SA-CVA GIRR vega path

**Goal:** Complete the interest-rate SA-CVA class with cited vega support.

**Scope:**

- Extend `risk_classes/girr.py` with MAR50.58 vega factors.
- Require `volatility_input` on sensitivity rows or explicit profile defaults.
- Apply `RW_k = RW_σ · σ_k` with cited `RW_σ`.

**Acceptance criteria:**

- GIRR vega fixtures reconcile by bucket and risk class.
- SA-CVA total sums GIRR delta and GIRR vega with other supported classes.
- Missing `volatility_input` fails validation where required.

**Tests/checks:** `tests/risk_classes/test_girr.py`.

**Maps to:** CVA-FUNC-015, CVA-NFR-004.

## Issue 27: Implement SA-CVA FX vega path

**Goal:** Add cited FX vega support deferred from Issue 14.

**Scope:**

- Extend `risk_classes/fx.py` with MAR50.62 vega factors.
- Require `volatility_input` where prescribed by the profile.

**Acceptance criteria:**

- FX vega fixtures reconcile by bucket and risk class.
- FX delta behavior is unchanged.

**Tests/checks:** `tests/risk_classes/test_fx.py`.

**Maps to:** CVA-FUNC-016.

## Issue dependency overview

```text
Issue 1 (docs)
    -> Issue 2 (models)
        -> Issue 3 (profile)
            -> Issue 4 (scope)
                -> Issue 5 (BA stand-alone)
                    -> Issue 6 (BA reduced agg)
                        -> Issue 7 (public BA API + audit)
                            -> Issue 8 (BA fixture)
            -> Issue 9 (hedges)
                -> Issue 10 (SA weighting)
                    -> Issue 11 (SA aggregation)
                        -> Issue 12 (SA-CVA GIRR delta API)
                            -> Issue 13 (GIRR fixture)
                            -> Issues 14–18 (remaining risk classes)
                            -> Issue 26 (GIRR vega) after Issue 12
                            -> Issue 27 (FX vega) after Issue 14
                            -> Issue 19 (BA full) after Issue 8 + 9
                            -> Issue 20 (qualified index) after 15 + 17
                            -> Issue 21 (mixed method) after 7 + 12
        -> Issue 22 (CRIF) after canonical runtime stable
        -> Issue 23 (orchestration) after Issue 7 or 12
        -> Issue 24 (performance) after Issue 8 or 13
        -> Issue 25 (attribution) after core capital stable
```

## Deferred / explicitly out of scope for v1 issues

These remain documented in
[REGULATORY_REQUIREMENTS.md](REGULATORY_REQUIREMENTS.md) but are not separate v1
implementation issues unless a profile mapping ADR lands first:

- regulatory CVA exposure simulation and sensitivity generation (MAR50.31–MAR50.36);
- accounting CVA production;
- materiality-threshold 100% CCR alternative (MAR50.9) beyond fail-closed gate;
- U.S. NPR 2.0 and CRR3 comparison profiles beyond Basel MAR50 first slice;
- supervisor-mandated `m_CVA` override workflows;
- live hedge-management and desk-governance workflows.
