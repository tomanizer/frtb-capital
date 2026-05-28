# FRTB CVA Product Requirements Document (PRD) v1.0

**packages/frtb-cva**

**Version:** 1.0  
**Date:** 2026-05-28  
**Status:** Draft for Implementation  
**Owner:** FRTB Capital Suite Team  
**Related Issues:** #29 (CVA Requirements) and chained coding issues 1–8

## 1. Executive Summary

This PRD defines the scope and requirements for the standalone `frtb-cva` package implementing the Credit Valuation Adjustment (CVA) capital charge under FRTB.

**Primary regulatory focus:** U.S. NPR 2.0 (BA-CVA as the default approach for most banks, with important exemptions for client-facing cleared derivatives).

The package will support:
- Basic Approach CVA (BA-CVA)
- Standardized Approach CVA (SA-CVA)
- Jurisdiction-specific policy adapters (US NPR, PRA UK, ECB/CRR3)
- Full audit-grade results and regulatory traceability

Out of scope (per ADR 0003): firm-level aggregation, IMA/DRC interaction floors, raw market data, pricing engines.

## 2. Regulatory Basis (Exact Citations)

- **Basel**: MAR50 (CVA risk)
- **U.S. NPR 2.0**: Federal Register 2026-05959, sections on CVA risk charge and client clearing exemption
- **UK PRA**: PS17/23 and PS9/24
- **EU CRR3**: Regulation (EU) 2024/1623, Articles on CVA

## 3. Scope and 8-Issue Roadmap

The work will be delivered via 8 focused GitHub issues (modeled exactly on successful DRC pattern):

1. Core Data Models + Enums (PositionCVA, Counterparty, enums for Approach/Quality)
2. BA-CVA Calculator + Hedging Benefit
3. SA-CVA Sensitivities + Bucket Aggregation
4. Jurisdiction Policy Adapter (US_NPR exemptions primary)
5. CRIF/Input Loading + Data Contracts for CVA
6. Capital Results, Audit Records, Logging
7. Synthetic Demo Data + Examples
8. Tests, README, REGULATORY_TRACEABILITY, Workspace Integration

## 4. Data Model Requirements

Frozen dataclasses in `data_models.py` (exact parallel to frtb-drc):

- `CVAApproach` (BA_CVA, SA_CVA)
- `CounterpartyCVA`
- `NettingSetCVA`
- `CVAPosition` (with EAD, MTM, spread sensitivities, hedge flags)
- `CVACapitalResult` (total, by counterparty, by hedge, breakdowns)

All support `.as_dict()` for audit.

## 5. Functional Requirements (Selected)

- `compute_ba_cva(positions, hedges, policy)` → BA-CVA capital + full decomposition
- `compute_sa_cva(sensitivities, policy)` → SA-CVA capital
- `apply_us_npr_exemptions(positions)` – client-facing cleared derivatives
- Jurisdiction policy objects with explicit UnsupportedRegulatoryFeatureError for AA-CVA

## 6. Acceptance Criteria

- All 8 issues closed
- BA-CVA and SA-CVA calculations match regulatory examples
- 85%+ coverage, deterministic tests
- `make check` clean from workspace root
- Full REGULATORY_TRACEABILITY.md with MAR50 + NPR 2.0 paragraph mapping
- No new runtime dependencies

## 7. Non-Functional & Engineering Requirements

Identical to frtb-drc and frtb-ima:
- numpy only
- Frozen dataclasses + pure functions
- Explicit citations instead of "working assumptions"
- Synthetic data only
- Audit records compatible with frtb-orchestration

## 8. Risks & Next Steps

Material change (LGD/RW tables or formulas) will require ADR.

After this PR merges, the 8 coding issues will be opened on the `feature/frtb-cva-requirements` branch model.

---

**Approval:** Proceed to detailed coding issues once this PR is merged.