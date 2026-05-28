# Regulatory Traceability — FRTB DRC

**Status:** Baseline for Issue #25. Expanded per subsequent issues #26–#32.

## Purpose

Cross-reference between `frtb-drc` code and the regulatory sources it implements
(Basel MAR22, U.S. NPR 2.0, CRR3, PRA). This is a traceability map for auditors
and validators, not a compliance claim.

## Code-to-Regulation (Issue #25 baseline)

| Module / Symbol                  | Regulatory Topic                          | Primary Source                          | Status     | Notes |
|----------------------------------|-------------------------------------------|-----------------------------------------|------------|-------|
| `data_models.Seniority`          | Seniority definitions for netting         | Basel MAR22.11–22.12                    | Implemented | Matches reference Zinc mapping |
| `data_models.CreditQuality` (IG/SG/SSG) | FRB/NPR 2.0 credit quality buckets   | NPR 2.0 Appendix (FRB final)            | Implemented | Explicit 2-tuple RW lookup |
| `data_models.Position`           | JTD exposure definition (long/short)      | Basel MAR22.8–22.10                     | Implemented | Frozen, validated, audit `.as_dict()` |
| `reference_data.get_risk_weight` (FRB path) | NON_US_SOVEREIGNS / PSE_GSE_DEBT RW | NPR 2.0 FRB table + MAR22.16         | Implemented | Exact match to drc_common tables |
| `reference_data.get_risk_weight` (BCBS/CRR) | CQS / rating RW table                | Basel MAR22.15–22.17, CRR3 Annex        | Implemented | UNRATED=15%, DEFAULTED=100% |
| `reference_data.load_reference_data` + overrides | Jurisdiction-specific parameters | MAR22.3, NPR policy layer            | Implemented | Supports future YAML seeds |

## Regulation-to-Code

| Regulatory Paragraph (selected) | Topic                              | Code Entry Point                  | Verification |
|---------------------------------|------------------------------------|-----------------------------------|--------------|
| Basel MAR22.8–22.14            | JTD gross, netting by seniority   | `jtd.py` (pending #26)           | Basel examples in tests |
| Basel MAR22.15–22.20           | Non-sec risk weights & buckets    | `reference_data.py`              | `test_data_models.py` exact values |
| Basel MAR22.21–22.39           | Bucket aggregation & DRC formula  | `aggregation.py` (pending #27)   | Hand calc + reference vectors |
| U.S. NPR 2.0 __.212 + App.     | FRB buckets (NON_US_SOVEREIGNS etc.) + IG/SG/SSG | `reference_data.FRB_DRC_JS_RW` | `get_risk_weight(..., RulesVersion.FRB)` |
| CRR3 Art 325ba–325bk           | EU DRC under FRTB SA              | `regimes.py` (future) + tables   | Policy profile tests |

## Source Register

| Family     | Document / Version                          | URL / Citation |
|------------|---------------------------------------------|----------------|
| Basel      | MAR22 (Default risk capital requirement)    | Basel Framework, January 2019 consolidated |
| U.S. NPR   | 91 FR 14952 (27 Mar 2026), Category I/II trading | Federal Register |
| EU         | CRR3 (Regulation (EU) 2024/1623)            | OJ L, 2024 |
| UK         | PRA SS 1/23, CRR rules                      | Bank of England |

## Material Change Note

Any change to a value in `FRB_DRC_JS_RW`, `BCBS_DRC_JS_RW`, LGD defaults, or
the `get_risk_weight` algorithm is a **material change** per the suite
material-change policy (see root `docs/decisions/000X-material-change-policy.md`
when created). Requires ADR + model owner sign-off.

---

**End of baseline traceability for #25.** Expanded as issues #26–#32 land.
