# frtb-drc workable issue breakdown

These are implementation-ready issue drafts. They are scoped so each can be a
reviewable PR. Cross-cutting changes to `frtb-common` or orchestration should
reference an ADR when they change shared contracts.

## Issue 1: Add DRC model documentation and traceability skeleton

**Goal:** Create the documentation pack that future DRC implementation PRs keep
current.

**Scope:**

- Add package-local `docs/REGULATORY_TRACEABILITY.md`,
  `docs/REGULATORY_ASSUMPTIONS.md`, and `docs/regulatory_sources.yml` under
  `packages/frtb-drc/`.
- Add model documentation front door under `docs/modules/frtb-drc/`.
- Cross-link module docs, package README, and requirements registry.

**Acceptance criteria:**

- Documentation distinguishes scaffold, planned, partial, and implemented
  status.
- No document presents DRC outputs as final regulatory capital.
- All source links point to primary regulatory sources or clearly marked
  implementation references.

**Tests/checks:** docs link check if available; existing package scaffold tests.

## Issue 2: Implement DRC data models and validation errors

**Goal:** Add frozen package-local data structures without capital calculation.

**Scope:**

- Add `data_models.py` with DRC enums and frozen dataclasses.
- Add `validation.py` with `DrcInputError`, invariant checks, and normalisation
  helpers.
- Keep `calculate_drc_capital` failing until the first capital slice lands.

**Acceptance criteria:**

- Public models cover `DrcPosition`, `GrossJtd`, `MaturityScaledJtd`, `NetJtd`,
  `HedgeBenefitRatio`, `BucketDrc`, `CategoryDrc`, and `DrcCapitalResult`.
- Invalid enum, missing identity, missing lineage, non-finite amount, negative
  maturity, and implicit direction paths fail deterministically.
- No sibling package imports.

**Tests/checks:** `tests/test_drc_data_models.py`, `tests/test_drc_validation.py`.

## Issue 3: Add DRC rule-profile and reference-data layer

**Goal:** Implement cited profile lookup for the first U.S. NPR
non-securitisation slice.

**Scope:**

- Add `regimes.py` and `reference_data.py`.
- Add U.S. NPR 2.0 profile id, source publication metadata, LGD table, maturity
  policy, non-securitisation bucket definitions, and risk-weight entries needed
  by fixtures.
- Add profile hash generation.
- Explicitly mark securitisation non-CTP and CTP unsupported.

**Acceptance criteria:**

- Every table entry has a citation id.
- Missing lookup keys raise a package input error.
- Profile hash is deterministic.

**Tests/checks:** `tests/test_drc_reference_data.py`, `tests/test_drc_regimes.py`.

## Issue 4: Implement non-securitisation gross JTD

**Goal:** Calculate gross JTD for non-securitisation positions.

**Scope:**

- Add `gross_jtd.py`.
- Apply cited LGD and P&L/notional mechanics.
- Preserve LGD source, direction, citation ids, and source lineage.
- Reject securitisation and CTP until their modules are implemented.

**Acceptance criteria:**

- Long default-risk examples produce gross long JTD.
- Short default-risk examples produce gross short JTD.
- Zero-LGD recovery-unlinked instruments produce zero gross JTD with cited
  reason.
- Defaulted positions use the defaulted LGD treatment.
- Credit derivative examples use the reference exposure LGD.

**Tests/checks:** `tests/test_drc_gross_jtd.py`,
`tests/test_drc_regimes.py`.

## Issue 5: Implement maturity scaling

**Goal:** Apply maturity weighting before netting.

**Scope:**

- Add `maturity.py`.
- Apply three-month floor, below-one-year scaling, and no scaling at or above
  one year for the selected profile.
- Preserve unscaled and scaled JTD.

**Acceptance criteria:**

- Maturity below three months floors to three months.
- Maturity between three months and one year scales linearly.
- Maturity one year or greater is unscaled.
- Invalid maturity fails before calculation.

**Tests/checks:** `tests/test_drc_maturity.py`.

## Issue 6: Implement same-obligor seniority-aware netting

**Goal:** Aggregate gross JTD into permitted non-securitisation net JTD.

**Scope:**

- Add `netting.py`.
- Group by profile, risk class, bucket, obligor, and seniority layer.
- Offset long and short exposures only where seniority and maturity rules
  permit.
- Record rejected offsets.

**Acceptance criteria:**

- Same-obligor eligible long/short offsets net correctly.
- Cross-obligor offsets are rejected.
- Cross-bucket offsets are rejected.
- Seniority-ineligible offsets are rejected with reason codes.
- Netting records reconcile to scaled gross JTD.

**Tests/checks:** `tests/test_drc_netting.py`.

## Issue 7: Implement HBR and non-securitisation bucket capital

**Goal:** Produce bucket and category DRC for non-securitisation positions.

**Scope:**

- Add capital functions for HBR, risk-weighting, bucket capital, floors, and
  category total.
- Keep the public API limited to non-securitisation until audit result work is
  complete.

**Acceptance criteria:**

- HBR uses aggregate net long and net short amounts.
- Risk-weighted long and short components are visible in results.
- Bucket floors apply where required.
- Bucket totals sum to category total.
- Category total equals non-securitisation DRC for the first slice.

**Tests/checks:** `tests/test_drc_capital.py`.

## Issue 8: Add public DRC run API and audit records

**Goal:** Replace scaffold failure for supported non-securitisation runs with a
real `DrcCapitalResult`.

**Scope:**

- Wire validation, profile lookup, gross JTD, maturity, netting, and capital.
- Add `audit.py` for deterministic result serialization, input hash, profile
  hash, and reconciliation checks.
- Keep unsupported category requests failing explicitly.

**Acceptance criteria:**

- `calculate_drc_capital` returns frozen `DrcCapitalResult` for supported
  non-securitisation inputs.
- Result includes rule-profile hash, input hash, citations, category totals,
  bucket totals, and warnings.
- Reconciliation errors fail tests.

**Tests/checks:** `tests/test_drc_public_api.py`, `tests/test_drc_audit.py`,
`tests/test_drc_replay.py`.

## Issue 9: Add synthetic non-securitisation validation fixture

**Goal:** Provide a deterministic fixture pack comparable to IMA's committed
capital-run fixture, scaled down for DRC.

**Scope:**

- Add `tests/fixtures/drc_nonsec_v1/`.
- Include long-only, short-only, eligible offset, ineligible seniority offset,
  below-three-month maturity, below-one-year maturity, defaulted issuer,
  covered bond, PSE/GSE, and zero-LGD cases.
- Add fixture loader and expected outputs.

**Acceptance criteria:**

- Fixture result is deterministic across supported Python versions.
- Expected outputs cover gross, scaled, net, bucket, category, and total result.
- Fixture docs explain each regulatory case and citation id.

**Tests/checks:** fixture workflow test and determinism test.

## Issue 10: Add optional CRIF-to-canonical DRC adapter

**Goal:** Convert CRIF-shaped default-risk rows into canonical DRC positions
without adding dataframe runtime dependencies.

**Scope:**

- Add `crif.py` with standard-library mapping from mappings/records.
- Record source column lineage.
- Reject ambiguous sign conventions.

**Acceptance criteria:**

- Adapter does not import `pandas`.
- Adapter output is canonical `DrcPosition`.
- Mapping warnings and rejected rows are auditable.

**Tests/checks:** `tests/test_drc_crif.py`.

## Issue 11: Implement securitisation non-CTP data model and fail-closed profile

**Goal:** Prepare securitisation non-CTP contracts without calculating capital.

**Scope:**

- Add tranche metadata dataclasses.
- Add cited bucket dimensions and validation.
- Add unsupported-feature tests for missing risk-weight mappings and
  incomplete tranche inputs.

**Acceptance criteria:**

- Securitisation positions validate identity and tranche metadata.
- Capital calculation remains unsupported until risk weights and formulas land.
- Errors are specific enough for follow-up implementation.

**Tests/checks:** `tests/test_drc_securitisation.py`,
`tests/test_drc_regimes.py`.

## Issue 12: Implement securitisation non-CTP capital

**Goal:** Add the cited securitisation non-CTP DRC path.

**Scope:**

- Implement tranche-level gross exposure where required.
- Implement permitted offsetting/replication rules.
- Add securitisation bucket assignment and risk-weight lookups.
- Add fair-value cap where profile permits it.

**Acceptance criteria:**

- Securitisation non-CTP fixtures cover asset class, region, other bucket,
  fair-value cap, and rejected offset cases.
- Category total reconciles to bucket totals.
- Non-securitisation behavior is unchanged.

**Tests/checks:** `tests/test_drc_securitisation.py`.

## Issue 13: Implement CTP data model and unsupported gates

**Goal:** Prepare CTP contracts and explicit unsupported behavior.

**Scope:**

- Add CTP portfolio membership, index/series, and tranche component metadata.
- Add validation for required decomposition inputs.
- Keep capital unsupported until CTP aggregation is implemented.

**Acceptance criteria:**

- CTP inputs can be represented and validated.
- Missing decomposition evidence produces deterministic errors.
- No placeholder CTP capital can be emitted.

**Tests/checks:** `tests/test_drc_ctp.py`,
`tests/test_drc_regimes.py`.

## Issue 14: Implement CTP capital

**Goal:** Add CTP DRC for cited profile paths.

**Scope:**

- Implement CTP gross default exposure, decomposition/replication, CTP HBR,
  bucket capital, and category aggregation.
- Add CTP fixture pack.

**Acceptance criteria:**

- CTP bucket and category totals reconcile.
- CTP aggregation does not reuse non-securitisation logic where citations
  require CTP-specific treatment.
- Non-CTP paths are unchanged.

**Tests/checks:** `tests/test_drc_ctp.py`.

## Issue 15: Add orchestration handoff for DRC output

**Goal:** Define how `frtb-orchestration` consumes `DrcCapitalResult`.

**Scope:**

- Add orchestration contract types or adapters only after DRC result shape is
  stable.
- Do not compose SA total until SBM and RRAO have compatible outputs.
- Add explicit unimplemented aggregation error where required components are
  missing.

**Acceptance criteria:**

- Orchestration can recognise a DRC package result.
- SA aggregation still fails explicitly until all required component outputs
  exist.
- No DRC imports from orchestration.

**Tests/checks:** orchestration package tests.

## Issue 16: Add performance and replay controls

**Goal:** Verify deterministic behavior and practical runtime at synthetic
scale.

**Scope:**

- Add benchmark script or test marker for large non-securitisation fixtures.
- Add replay hash checks for audit outputs.
- Document target scale and observed runtime.

**Acceptance criteria:**

- Large fixture runs without dataframe runtime dependencies.
- Hash checks detect output ordering or numeric drift.
- Performance docs are updated.

**Tests/checks:** targeted benchmark command, replay tests.

## Issue 17: Add attribution and impact assessment

**Goal:** Add analytical attribution now and keep change-impact outputs as a
separate later slice after core DRC is stable.

**Scope:**

- Implement `attribution.py` for analytical Euler contribution on supported
  stable DRC branches.
- Implement `impact.py` for baseline-vs-candidate capital deltas in a later
  issue.
- Reconcile contribution records to bucket, category, and total DRC where the
  active branch permits exact reconciliation.
- Label finite-difference impact separately from analytical marginal
  contribution.
- Document unsupported attribution paths and residual reasons.

**Acceptance criteria:**

- Analytical contributions sum to total within tolerance for all supported
  fixtures.
- Unsupported formulas, branch changes, floors, and zero denominators report
  explicit method/residual metadata.
- Capital totals do not change when attribution is emitted or impact is later
  requested.

**Tests/checks to add with this issue:** `tests/test_drc_attribution.py`.
Future impact work should add `tests/test_drc_impact.py`.
