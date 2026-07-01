# PRA UK CRR CSR SBM mapping

## Purpose

This map records the PRA UK CRR source and field semantics needed before any
`PRA_UK_CRR` CSR runtime gate opens. It is planning evidence only: CSR
non-securitisation, CSR securitisation non-CTP, and CSR securitisation CTP
remain unsupported fail-closed until a follow-on implementation adds
profile-owned reference data and deterministic fixtures.

Primary source: PRA PS1/26 Appendix 1 / PRA2026/1, Market Risk: Advanced
Standardised Approach (CRR) Part, effective 2027-01-01.

## Runtime status

| Cell family | Delta | Vega | Curvature |
| --- | --- | --- | --- |
| CSR non-securitisation | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |
| CSR securitisation non-CTP | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |
| CSR securitisation CTP | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |

## Source map

| PRA topic | Exact source anchor | Existing canonical fields |
| --- | --- | --- |
| CSR non-securitisation risk factors | Article 325m | `risk_class=CSR_NONSEC`, `bucket`, `qualifier` as issuer/name, `risk_factor` as credit-spread curve or bond/CDS spread axis, `tenor` |
| CSR securitisation non-CTP risk factors | Article 325n | `risk_class=CSR_SEC_NONCTP`, `bucket`, `qualifier` as tranche or securitisation name, `risk_factor` as credit-spread curve, `tenor` |
| CSR securitisation CTP risk factors | Article 325n | `risk_class=CSR_SEC_CTP`, `bucket`, `qualifier` as underlying name or index decomposition key, `risk_factor` as credit-spread curve, `tenor` |
| CSR non-securitisation buckets and risk weights | Article 325ah | Profile-owned PRA bucket ids, sector/quality labels, and delta risk weights |
| CSR non-securitisation intra-bucket correlations | Article 325ai | Issuer/name, tenor, basis, and other-sector absolute-weight behavior |
| CSR non-securitisation inter-bucket correlations | Article 325aj | Cross-bucket correlation matrix and other-bucket treatment |
| CSR securitisation CTP buckets, weights, and correlations | Articles 325ak-325al | Correlation-trading bucket ids, underlying-name decomposition evidence, and inter-bucket correlations |
| CSR securitisation non-CTP buckets, weights, and correlations | Articles 325am-325ao | Tranche/bucket ids, credit quality/sector labels, other-sector behavior, and inter-bucket correlations |
| Vega overlays for CSR cells | Article 325ax and Article 325s | Option tenor, liquidity horizon, and non-GIRR vega correlation axes |
| Curvature overlays for CSR cells | Article 325ax and Articles 325g-325h | CVR+/CVR- branch evidence, highest delta risk weight, squared delta-correlation treatment, and scenario selection |

## Fixture plan

Each implementation PR must add one deterministic fixture pack per opened cell:

| First candidate fixture | Scope |
| --- | --- |
| `csr_nonsec_delta_pra_uk_crr_v1` | Two issuers across at least two PRA CSR non-sec buckets, including tenor and basis evidence |
| `csr_sec_nonctp_delta_pra_uk_crr_v1` | Two tranches across non-CTP buckets with tranche evidence in `qualifier` |
| `csr_sec_ctp_delta_pra_uk_crr_v1` | CTP positions with underlying-name or decomposition evidence |
| `csr_nonsec_vega_pra_uk_crr_v1` | CSR non-sec option-tenor and issuer evidence; only after delta source data is profile-owned |
| `csr_nonsec_curvature_pra_uk_crr_v1` | CSR non-sec up/down shocks, branch records, and squared correlation evidence |

## Fail-closed cases

PRA CSR implementation must reject, before capital emission:

- missing issuer/name, tranche, or underlying-name evidence;
- missing CTP decomposition evidence;
- missing tenor or option-tenor evidence where required by the selected measure;
- unsupported option or volatility treatment;
- Basel/EU citation ids in `PRA_UK_CRR` reference data, audit records, or fixtures;
- existing Basel CSR limitations until each limitation has a PRA-owned citation
  and fixture-backed behavior.

## Implementation checklist

- Add profile-owned `pra_uk_crr_*` citation ids for the exact cell.
- Add PRA-owned reference data instead of falling back to Basel MAR21 or EU CRR3
  citation ids.
- Open only the delivered `PRA_UK_CRR` CSR gate in `validation/context.py` and
  `regimes.py`.
- Preserve `PRA_UK_CRR` profile id, PRA citation ids, and profile hash in row,
  batch, and Arrow outputs.
- Keep package maturity at `partial_runtime` until a separate maturity issue
  proves broader coverage.
