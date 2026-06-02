# frtb-sbm workable issue breakdown

These are implementation-ready issue drafts. They are scoped so each can be a
reviewable PR. Cross-cutting changes to `frtb-common` or orchestration should
reference an ADR when they change shared contracts.

This breakdown is historical planning material. Current support status after
the later implementation and vectorisation sprints lives in
[`packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`](../../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md).

## Issue 1: Add SBM model documentation and traceability skeleton

**Goal:** Create the documentation pack that future SBM implementation PRs keep
current.

**Scope:**

- Add package-local traceability and assumptions docs under `packages/frtb-sbm/`
  when the package grows beyond the scaffold.
- Add model-documentation front door under `docs/modules/frtb-sbm/`.
- Cross-link module docs, package README, and requirements registry.

**Acceptance criteria:**

- Documentation distinguishes scaffold, planned, partial, and implemented
  status.
- No document presents SBM outputs as final regulatory capital.
- Source links point to primary regulatory sources or clearly marked reference
  implementations.

**Tests/checks:** docs link check if available; existing scaffold tests.

## Issue 2: Implement SBM data models and validation errors

**Goal:** Add frozen package-local data structures without capital calculation.

**Scope:**

- Add `data_models.py` with SBM enums and frozen dataclasses.
- Add `validation.py` with `SbmInputError`, invariant checks, and normalisation
  helpers.
- Keep `calculate_sbm_capital` failing until the first capital slice lands.

**Acceptance criteria:**

- Public models cover `SbmSensitivity`, `WeightedSensitivity`, `BucketCapital`,
  `RiskClassCapital`, and `SbmCapitalResult`.
- Invalid enum, missing identity, duplicate sensitivity id, non-finite amount,
  missing lineage, and implicit sign paths fail deterministically.
- No sibling package imports.

**Tests/checks:** `tests/test_data_models.py`, `tests/test_validation.py`.

## Issue 3: Add SBM rule-profile and reference-data layer

**Goal:** Implement cited profile lookup for the first GIRR delta slice.

**Scope:**

- Add `regimes.py` and `reference_data.py`.
- Add one initial profile id, publication metadata, GIRR bucket definitions,
  tenor set, risk-weight entries, intra-bucket correlations, inter-bucket
  correlations, and scenario labels needed by fixtures.
- Add profile hash generation.
- Explicitly mark vega, curvature, and non-target risk classes unsupported.

**Acceptance criteria:**

- Every table entry has a citation id.
- Missing lookup keys raise a package input error.
- Profile hash is deterministic.

**Tests/checks:** `tests/test_reference_data.py`, `tests/test_regimes.py`.

## Issue 4: Implement weighted sensitivity calculation

**Goal:** Convert canonical sensitivities into cited weighted-sensitivity
records.

**Scope:**

- Add `weighted_sensitivity.py`.
- Resolve risk weights from the selected profile.
- Preserve raw amount, scaling inputs, scaled amount, and citation ids.
- Keep unsupported risk-class and measure requests failing explicitly.

**Acceptance criteria:**

- Supported GIRR delta rows produce weighted sensitivities with stable ids.
- Missing risk weights fail explicitly.
- Audit output preserves both raw and scaled values.

**Tests/checks:** `tests/test_weighted_sensitivity.py`,
`tests/test_unsupported_features.py`.

## Issue 5: Implement vega scaling helpers

**Goal:** Add cited vega-scaling support without exposing full vega capital yet.

**Scope:**

- Extend weighting helpers with liquidity-horizon or tenor-based scaling.
- Preserve unscaled and scaled amounts.
- Leave full vega capital aggregation unsupported until the shared engine is
  ready.

**Acceptance criteria:**

- Vega scaling matches cited profile values for supported fixtures.
- Unsupported vega combinations fail explicitly.
- Delta behavior is unchanged.

**Tests/checks:** `tests/test_weighted_sensitivity.py`.

## Issue 6: Implement shared intra-bucket aggregation engine

**Goal:** Produce bucket-level `Kb` and `Sb` using reusable primitives.

**Scope:**

- Add `aggregation.py` intra-bucket functions.
- Group weighted sensitivities by risk class, measure, bucket, and qualifier.
- Apply cited intra-bucket correlations and floors.
- Preserve correlation evidence in audit records.

**Acceptance criteria:**

- Bucket totals reconcile to the weighted sensitivities used.
- Floors apply where required.
- Aggregation order is deterministic.

**Tests/checks:** `tests/test_aggregation.py`.

## Issue 7: Implement shared inter-bucket aggregation and scenario selection

**Goal:** Produce risk-class capital across low, medium, and high scenarios.

**Scope:**

- Add inter-bucket aggregation helpers and scenario evaluation.
- Apply scenario-specific correlation adjustments from the profile.
- Return per-scenario totals and the selected final outcome.

**Acceptance criteria:**

- Scenario totals are visible in the result surface.
- Final scenario selection follows the active profile rule.
- Missing correlation tables fail explicitly.

**Tests/checks:** `tests/test_aggregation.py`, `tests/test_scenarios.py`.

## Issue 8: Deliver the first GIRR delta public API slice

**Goal:** Replace scaffold failure for supported GIRR delta runs with a real
`SbmCapitalResult`.

**Scope:**

- Wire validation, profile lookup, weighting, intra-bucket aggregation,
  inter-bucket aggregation, and total-result assembly.
- Keep vega, curvature, and non-GIRR requests failing explicitly.
- Return frozen package-level result objects only for supported inputs.

**Acceptance criteria:**

- `calculate_sbm_capital` returns `SbmCapitalResult` for supported GIRR delta
  inputs.
- Result includes scenario totals, selected scenario, profile hash, input hash,
  and warnings.
- Unsupported requests still fail deterministically.

**Tests/checks:** `tests/test_public_api.py`, `tests/test_replay.py`.

## Issue 9: Add audit and replay records

**Goal:** Make the first capital slice reproducible and reviewable.

**Scope:**

- Add `audit.py`.
- Serialize deterministic audit bundles with input hash, profile hash, weighted
  sensitivities, buckets, scenarios, and total result.
- Add reconciliation checks.

**Acceptance criteria:**

- Re-running the same inputs yields the same hashes and serialized order.
- Bucket and scenario totals reconcile to total SBM.
- Reconciliation failures fail tests.

**Tests/checks:** `tests/test_audit.py`, `tests/test_replay.py`.

## Issue 10: Add synthetic GIRR and FX validation fixtures

**Goal:** Provide a deterministic fixture pack that proves the shared engine on
at least two risk classes.

**Scope:**

- Add synthetic GIRR delta fixtures.
- Add at least one FX delta fixture if the first shared engine supports it.
- Include negative cases for missing lookup, unsupported measure, and duplicate
  sensitivity id.

**Acceptance criteria:**

- Fixture results are deterministic across supported Python versions.
- Expected outputs cover weighted sensitivities, bucket results, scenario totals,
  and total result.
- Fixture docs identify the cited rule cases being exercised.

**Tests/checks:** fixture workflow test and determinism test.

## Issue 11: Implement equity and commodity paths

**Goal:** Reuse the shared engine for a second family of risk classes.

**Scope:**

- Add `risk_classes/equity.py` and `risk_classes/commodity.py`.
- Add cited bucket definitions, qualifiers, weights, and correlations needed by
  fixtures.
- Reuse shared weighting and aggregation primitives.

**Acceptance criteria:**

- Equity and commodity fixtures reconcile through the shared engine.
- No duplicated aggregation algorithm is introduced.
- GIRR behavior is unchanged.

**Tests/checks:** `tests/risk_classes/test_equity.py`,
`tests/risk_classes/test_commodity.py`.

## Issue 12: Implement CSR non-securitisation path

**Goal:** Add cited CSR non-securitisation support.

**Scope:**

- Add `risk_classes/csr_nonsec.py`.
- Add issuer/sector/rating or equivalent bucket lookups.
- Support prescribed basis distinctions where required.
- Reuse shared weighting and aggregation primitives.

**Acceptance criteria:**

- CSR non-securitisation fixtures reconcile by bucket and scenario.
- Basis-specific unsupported cases fail explicitly if not yet cited.
- Existing risk classes are unchanged.

**Tests/checks:** `tests/risk_classes/test_csr_nonsec.py`.

## Issue 13: Implement curvature contracts and fail-closed gates

**Goal:** Prepare curvature support without emitting placeholder curvature
capital.

**Scope:**

- Add curvature-specific canonical inputs and validation.
- Add explicit unsupported-feature errors for incomplete up/down shock inputs.
- Keep curvature capital unsupported until the aggregation path lands.

**Acceptance criteria:**

- Curvature inputs can be represented and validated.
- Missing branch inputs fail deterministically.
- No placeholder curvature totals can be returned.

**Tests/checks:** `tests/test_curvature.py`,
`tests/test_unsupported_features.py`.

## Issue 14: Implement curvature capital path

**Goal:** Add cited curvature capital as a distinct calculation path.

**Scope:**

- Implement curvature weighting, branch selection, bucket aggregation, and
  risk-class aggregation.
- Apply curvature floors.
- Add synthetic curvature fixture packs.

**Acceptance criteria:**

- Curvature outputs preserve up/down inputs and selected branch metadata.
- Bucket and risk-class curvature totals reconcile.
- Delta and vega behavior are unchanged.

**Tests/checks:** `tests/test_curvature.py`.

## Issue 15: Implement CSR securitisation non-CTP path

**Goal:** Add cited securitisation non-CTP support once mappings are complete.

**Scope:**

- Add `risk_classes/csr_sec_nonctp.py`.
- Add securitisation bucket definitions, qualifiers, and aggregation rules.
- Keep unsupported gates for incomplete mappings.

**Acceptance criteria:**

- Supported non-CTP fixtures reconcile by bucket and scenario.
- Incomplete qualifier mappings fail explicitly.
- Non-securitisation behavior is unchanged.

**Tests/checks:** `tests/risk_classes/test_csr_sec_nonctp.py`.

## Issue 16: Implement CSR securitisation CTP path

**Goal:** Add cited securitisation CTP support once mappings are complete.

**Scope:**

- Add `risk_classes/csr_sec_ctp.py`.
- Add CTP-specific bucket and aggregation rules.
- Add explicit unsupported tests for missing decomposition evidence or profile
  support.

**Acceptance criteria:**

- Supported CTP fixtures reconcile by bucket and scenario.
- Unsupported CTP profile paths fail explicitly.
- Non-CTP behavior is unchanged.

**Tests/checks:** `tests/risk_classes/test_csr_sec_ctp.py`.

## Issue 17: Add optional CRIF adapters, orchestration handoff, and performance controls

**Goal:** Finish the package boundary around a stable SBM runtime.

**Scope:**

- Add `crif.py` mapping helpers without dataframe runtime dependencies.
- Define the typed handoff from `SbmCapitalResult` into orchestration.
- Add benchmark and replay controls for large synthetic sensitivity sets.
- Add attribution and impact placeholders after the capital graph is stable.

**Acceptance criteria:**

- Adapter output is canonical `SbmSensitivity` with lineage and mapping
  warnings.
- Orchestration can consume package-level SBM results without importing internal
  kernels.
- Replay hashes detect ordering or numeric drift.

**Tests/checks:** `tests/test_crif.py`, orchestration package tests, replay and
benchmark checks.
