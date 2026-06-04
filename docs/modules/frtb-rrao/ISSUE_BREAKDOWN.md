# frtb-rrao workable issue breakdown

These were the implementation-ready issue drafts for the v1 delivery sequence.
They are retained as historical planning evidence; the active implementation
status is now tracked in [`MODEL_DOCUMENTATION.md`](MODEL_DOCUMENTATION.md) and
[`BASEL_FRTB_RRAO.yml`](../../../packages/frtb-rrao/docs/requirements/BASEL_FRTB_RRAO.yml).
Cross-cutting changes to `frtb-common` or orchestration should still reference
an ADR when they change shared contracts.

## Issue 1: Add RRAO model documentation and traceability skeleton

**Goal:** Create the documentation pack that future RRAO implementation PRs keep
current.

**Scope:**

- Add package-local `docs/REGULATORY_TRACEABILITY.md`,
  `docs/REGULATORY_ASSUMPTIONS.md`, and `docs/regulatory_sources.yml` under
  `packages/frtb-rrao/`.
- Add model documentation front door under `docs/modules/frtb-rrao/`.
- Cross-link module docs, package README, and requirements registry.

**Acceptance criteria:**

- Documentation distinguishes scaffold, planned, partial, implemented,
  excluded, and unsupported status.
- No document presents RRAO outputs as final regulatory capital.
- All source links point to primary regulatory sources or clearly marked
  implementation references.

**Tests/checks:** docs link check if available; existing package scaffold tests.

## Issue 2: Implement RRAO data models and validation errors

**Goal:** Add frozen package-local data structures without capital calculation.

**Scope:**

- Add `data_models.py` with RRAO enums and frozen dataclasses.
- Add `validation.py` with `RraoInputError`, invariant checks, and
  normalisation helpers.
- Keep `calculate_rrao_capital` failing until the first capital slice lands.

**Acceptance criteria:**

- Public models cover `RraoPosition`, `RraoClassificationDecision`,
  `RraoCapitalLine`, `RraoSubtotal`, and `RraoCapitalResult`.
- Invalid enum, missing identity, missing lineage, duplicate position id,
  non-finite notional, negative notional, missing evidence, and unsupported
  classification paths fail deterministically.
- No sibling package imports.

**Tests/checks:** `tests/test_data_models.py`, `tests/test_validation.py`.

## Issue 3: Add RRAO rule-profile and reference-data layer

**Goal:** Implement cited profile lookup for the first U.S. NPR 2.0 and Basel
MAR23 canonical-input slice.

**Scope:**

- Add `regimes.py` and `reference_data.py`.
- Add U.S. NPR 2.0 proposed section `__.211` profile id, source publication
  metadata, supported classification evidence, exclusion reason table, and risk
  weights.
- Add Basel MAR23 profile id, publication metadata, supported classification
  evidence, exclusions, and risk weights.
- Add profile hash generation.
- Explicitly mark EU CRR3 and PRA paths unsupported until mapped; EU CRR3 is
  mapped by Issue 10.

**Acceptance criteria:**

- Every table entry has a citation id.
- Missing lookup keys raise a package input error.
- Profile hash is deterministic.
- Unsupported profiles fail before calculation.

**Tests/checks:** `tests/test_reference_data.py`, `tests/test_regimes.py`.

## Issue 4: Implement classification and exclusion decisions

**Goal:** Convert validated positions into cited classification decisions.

**Scope:**

- Add `classification.py`.
- Support exotic, other residual risk, supervisor-directed inclusion, and cited
  exclusions for the first U.S. NPR/Basel slice.
- Preserve reason codes, exclusion evidence ids, and citation ids.
- Reject investment-fund inclusion and unmapped jurisdiction-specific paths
  until explicitly implemented.

**Acceptance criteria:**

- Exotic examples classify to 1.0% treatment.
- Other residual-risk examples classify to 0.1% treatment.
- Supervisor-directed positions require directive evidence.
- Exclusions produce zero-capital decisions with cited reasons.
- Unsupported classification evidence raises explicit errors.

**Tests/checks:** `tests/test_classification.py`,
`tests/test_exclusions.py`, `tests/test_unsupported_features.py`.

## Issue 5: Implement RRAO line add-ons and subtotals

**Goal:** Calculate additive line capital and deterministic explain subtotals.

**Scope:**

- Add `capital.py`.
- Calculate `gross_effective_notional * risk_weight`.
- Aggregate deterministic subtotals by classification, evidence type, desk, and
  legal entity.
- Keep the public API limited until audit result work is complete.

**Acceptance criteria:**

- 1.0% exotic and 0.1% other residual-risk lines calculate correctly.
- Excluded lines have zero add-on and remain visible.
- Subtotals reconcile to line add-ons.
- No offsetting, diversification, or maturity scaling is applied.

**Tests/checks:** `tests/test_capital.py`.

## Issue 6: Add public RRAO run API and audit records

**Goal:** Replace scaffold failure for supported canonical runs with a real
`RraoCapitalResult`.

**Scope:**

- Wire validation, profile lookup, classification, exclusion, line add-ons, and
  subtotals.
- Add `audit.py` for deterministic result serialization, input hash, profile
  hash, and reconciliation checks.
- Keep unsupported category/profile requests failing explicitly.

**Acceptance criteria:**

- `calculate_rrao_capital` returns frozen `RraoCapitalResult` for supported
  canonical inputs.
- Result includes rule-profile hash, input hash, citations, line records,
  excluded records, subtotals, and warnings.
- Reconciliation errors fail tests.

**Tests/checks:** `tests/test_public_api.py`, `tests/test_audit.py`,
`tests/test_replay.py`.

## Issue 7: Add synthetic RRAO v1 validation fixture

**Goal:** Provide a deterministic fixture pack comparable to the package's
first capital-producing result shape.

**Scope:**

- Add `tests/fixtures/rrao_v1/`.
- Include longevity, weather, natural disaster, gap risk, correlation risk,
  behavioural risk, supervisor-directed inclusion, listed exclusion, clearable
  exclusion, plain-option exclusion, exact back-to-back exclusion, government or
  GSE exclusion, fallback-capital exclusion, and invalid evidence cases.
- Add fixture loader and expected outputs.

**Acceptance criteria:**

- Fixture result is deterministic across supported Python versions.
- Expected outputs cover classification, exclusions, line add-ons, subtotals,
  and total result.
- Fixture docs explain each regulatory case and citation id.

**Tests/checks:** fixture workflow test and determinism test.

## Issue 8: Add optional CRIF/FNet-to-canonical RRAO adapter

**Goal:** Convert CRIF/FNet-shaped residual-risk rows into canonical RRAO
positions without adding dataframe runtime dependencies.

**Scope:**

- Add `crif.py` with standard-library mapping from mappings/records.
- Support CRIF-style `RRAO_1_PERCENT` and `RRAO_01_PERCENT` risk types or FNet
  `Bucket=Exotic` / `Bucket=Non-Exotic` shapes where evidence is sufficient.
- Record source column lineage.
- Reject ambiguous classification or notional conventions.

**Acceptance criteria:**

- Adapter does not import `pandas`.
- Adapter output is canonical `RraoPosition`.
- Mapping warnings and rejected rows are auditable.

**Tests/checks:** `tests/test_crif.py`.

## Issue 9: Add investment-fund inclusion path

**Goal:** Implement proposed U.S. section `__.211(a)(3)` investment-fund
inclusion once the input contract is explicit.

**Scope:**

- Add investment-fund exposure descriptors.
- Validate proposed section `__.205(e)(3)(iii)` linkage fields.
- Add classification and fixture coverage for included exposure portions.

**Acceptance criteria:**

- Investment-fund inclusion cannot be triggered without cited evidence.
- Included portions receive the cited risk-weight treatment.
- Unsupported or partial investment-fund inputs fail explicitly.

**Tests/checks:** `tests/test_investment_fund.py`,
`tests/test_unsupported_features.py`.

## Issue 10: Add EU CRR3 / Delegated Regulation 2022/2328 profile

**Goal:** Add EU comparison profile mapping for Article 325u and Delegated
Regulation (EU) 2022/2328.

**Scope:**

- Map Article 1 exotic underlyings.
- Map Article 2 Annex instrument list.
- Map Article 3 risks that do not by themselves presume residual-risk
  treatment.
- Add EU-specific fixture pack.

**Acceptance criteria:**

- EU profile cites Article 325u and Delegated Regulation 2022/2328 Articles
  1-3 and Annex entries.
- EU classification differs from U.S. profile only where citations require it.
- U.S. and Basel fixture results remain unchanged.

**Tests/checks:** `tests/test_eu_profile.py`.

## Issue 11: Add orchestration handoff for RRAO output

**Goal:** Define how `frtb-orchestration` consumes `RraoCapitalResult`.

**Scope:**

- Add orchestration contract types or adapters only after RRAO result shape is
  stable.
- Do not compose SA total until SBM and DRC have compatible outputs.
- Add explicit unimplemented aggregation error where required components are
  missing.

**Acceptance criteria:**

- Orchestration can recognise an RRAO package result.
- SA aggregation still fails explicitly until all required component outputs
  exist.
- No RRAO imports from orchestration.

**Tests/checks:** orchestration package tests.

**Status:** Implemented by the orchestration-side RRAO result handoff. SA
aggregation still fails explicitly until SBM and DRC outputs are compatible.

## Issue 12: Add performance and replay controls

**Goal:** Verify deterministic behavior and practical runtime at synthetic
scale.

**Scope:**

- Add benchmark script or test marker for large RRAO fixtures.
- Add replay hash checks for audit outputs.
- Document target scale and observed runtime.

**Acceptance criteria:**

- Large fixture runs without dataframe runtime dependencies.
- Hash checks detect output ordering or numeric drift.
- Performance docs are updated.

**Tests/checks:** targeted benchmark command, replay tests.

**Status:** Implemented with `make rrao-benchmark`, deterministic audit payload
hashes, ordering-drift checks, and performance documentation.

## Issue 13: Add additive allocation/report helpers

**Goal:** Add optional explain helpers after core RRAO is stable.

**Scope:**

- Implement line, desk, legal-entity, and evidence-type contribution reports.
- Reconcile allocation to total RRAO.
- Document unsupported allocation paths.

**Acceptance criteria:**

- Allocation sums to total exactly for all supported fixtures.
- Unsupported report dimensions fail explicitly.
- Capital totals do not change when allocation is requested.

**Tests/checks:** `tests/test_allocation.py`.

**Status:** Implemented with additive line, desk, legal-entity, and
evidence-type allocation reports, reconciliation checks, and fail-closed
unsupported-dimension handling.
