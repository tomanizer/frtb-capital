# U.S. NPR 2.0 CSR SBM Mapping

This document maps the U.S. NPR 2.0 credit-spread-risk SBM cells before any CSR
runtime gate is opened. It is proposed-rule comparison material only. The
runtime support matrix remains unchanged by this document: all `US_NPR_2_0`
CSR cells remain unsupported fail-closed until a later fixture-backed
implementation PR adds the specific cell.

Source anchor: Federal Register 91 FR 14952, March 27, 2026, section V.A.7.a,
especially proposed sections `ll.206`, `ll.208`, and `ll.209`.

## Source Anchors

| Area | Proposed-rule source | Local use |
| --- | --- | --- |
| CSR delta sensitivity definition | 91 FR 15215, proposed `ll.207(b)(2)` | All three CSR families use a one-basis-point credit-spread shift. |
| CSR reporting currency | 91 FR 15215, proposed `ll.207(a)(8)` | Use existing `SbmCalculationContext.reporting_currency`; no base-currency CSR mode. |
| CSR non-securitization risk factors | 91 FR 15217, proposed `ll.208(c)` | Issuer credit-spread curve plus tenor for delta; option maturity for vega; issuer spread curve for curvature. |
| CSR securitization non-CTP risk factors | 91 FR 15217, proposed `ll.208(d)` | Tranche credit-spread curve plus tranche tenor for delta; option maturity for vega; tranche spread curve for curvature. |
| CSR correlation trading risk factors | 91 FR 15217, proposed `ll.208(e)` | Underlying-name credit-spread curve plus underlying-name tenor for delta; option maturity for vega; underlying-name spread curve for curvature. |
| CSR non-securitization delta buckets and correlations | 91 FR 15220-15222, proposed `ll.209(b)(2)` | Mirror Basel CSR non-sec tables only with profile-owned NPR citation ids and fixtures. |
| CSR correlation trading delta buckets and correlations | 91 FR 15222-15225, proposed `ll.209(b)(3)` | Mirror Basel CSR CTP bucket and correlation mechanics with profile-owned NPR citation ids and decomposition evidence. |
| CSR securitization non-CTP delta buckets and correlations | 91 FR 15225-15227, proposed `ll.209(b)(4)` | Mirror Basel CSR sec non-CTP tables only with profile-owned NPR citation ids and fixtures. |
| Generic vega aggregation | 91 FR 15212-15214, proposed `ll.206(c)` | Use existing non-GIRR vega kernel shape after adding CSR profile-owned vega citations. |
| Generic curvature aggregation | 91 FR 15214-15215, proposed `ll.206(d)` | Use existing curvature kernel only after adding CSR profile-owned curvature citations and fixtures. |

## Citation Id Plan

Add these identifiers to `reference_citations_us_npr.py` before opening any
CSR runtime gate. The suffixes deliberately mirror the existing Basel CSR
citation split so audit payloads can prove that no `BASEL_MAR21` citation was
reused for a `US_NPR_2_0` output.

| CSR family | Required citation ids |
| --- | --- |
| Non-securitization | `us_npr_91_fr_14952_va7a_csr_nonsec_delta_factors`, `us_npr_91_fr_14952_va7a_csr_nonsec_delta_buckets`, `us_npr_91_fr_14952_va7a_csr_nonsec_delta_weights`, `us_npr_91_fr_14952_va7a_csr_nonsec_delta_intra`, `us_npr_91_fr_14952_va7a_csr_nonsec_delta_index_intra`, `us_npr_91_fr_14952_va7a_csr_nonsec_delta_other_sector`, `us_npr_91_fr_14952_va7a_csr_nonsec_delta_inter`, `us_npr_91_fr_14952_va7a_csr_nonsec_vega_factors`, `us_npr_91_fr_14952_va7a_csr_nonsec_vega_lh_rw`, `us_npr_91_fr_14952_va7a_csr_nonsec_vega_intra`, `us_npr_91_fr_14952_va7a_csr_nonsec_vega_inter`, `us_npr_91_fr_14952_va7a_csr_nonsec_curvature_factors`, `us_npr_91_fr_14952_va7a_csr_nonsec_curvature_shocks`, `us_npr_91_fr_14952_va7a_csr_nonsec_curvature_intra`, `us_npr_91_fr_14952_va7a_csr_nonsec_curvature_inter`. |
| Securitization non-CTP | `us_npr_91_fr_14952_va7a_csr_sec_nonctp_delta_factors`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_delta_buckets`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_delta_weights`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_delta_intra`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_delta_other_sector`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_delta_inter`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_vega_factors`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_vega_lh_rw`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_vega_intra`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_vega_inter`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_curvature_factors`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_curvature_shocks`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_curvature_intra`, `us_npr_91_fr_14952_va7a_csr_sec_nonctp_curvature_inter`. |
| Correlation trading positions | `us_npr_91_fr_14952_va7a_csr_sec_ctp_delta_factors`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_delta_buckets`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_delta_weights`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_delta_intra`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_delta_inter`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_decomposition`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_vega_factors`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_vega_lh_rw`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_vega_intra`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_vega_inter`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_curvature_factors`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_curvature_shocks`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_curvature_intra`, `us_npr_91_fr_14952_va7a_csr_sec_ctp_curvature_inter`. |

## Canonical Field Mapping

| U.S. NPR concept | Existing canonical field | Required treatment |
| --- | --- | --- |
| Issuer credit-spread curve for CSR non-sec | `SbmSensitivity.qualifier` | Store a stable issuer id. The same issuer id is used for name correlation and for curvature curve identity. |
| Non-sec bond/CDS spread curve | `SbmSensitivity.risk_factor` | Keep existing `BOND` and `CDS` values. Delta intra-bucket basis correlation distinguishes same/different curve. Curvature must ignore bond-CDS basis for the same issuer under proposed `ll.208(c)(3)`. |
| Non-sec tenor | `SbmSensitivity.tenor` | Use the existing CSR tenor set: `6m`, `1y`, `3y`, `5y`, `10y`. |
| Non-sec bucket | `SbmSensitivity.bucket` | Mirror the current CSR non-sec bucket ids and other-sector absolute aggregation with NPR citations. |
| Securitization non-CTP tranche credit-spread curve | `SbmSensitivity.qualifier` | Store a stable tranche id, not the underlying-name id. |
| Securitization non-CTP tranche tenor | `SbmSensitivity.tenor` | Use the current CSR sec non-CTP tenor set. |
| Securitization non-CTP bond/CDS spread curve | `SbmSensitivity.risk_factor` | Keep existing `BOND` and `CDS`; curvature must ignore bond-CDS basis for the same tranche under proposed `ll.208(d)(3)`. |
| Securitization non-CTP bucket | `SbmSensitivity.bucket` | Mirror current 25-bucket non-CTP table, including bucket 25 other sector and zero inter-bucket gamma. |
| Correlation trading underlying-name spread curve | `SbmSensitivity.qualifier` | Store the underlying-name id for decomposed or single-name CTP rows. For index-level rows, the qualifier must identify the index or bespoke CTP bucket and decomposition flags must state whether single-name decomposition evidence exists. |
| Correlation trading tenor of underlying name | `SbmSensitivity.tenor` | Use the current CSR CTP tenor set. |
| Correlation trading bond/CDS spread curve | `SbmSensitivity.risk_factor` | Keep existing `BOND` and `CDS`; curvature must use the underlying-name spread curve under proposed `ll.208(e)(3)`. |
| Correlation trading bucket | `SbmSensitivity.bucket` | Mirror current CSR CTP 1-16 buckets. Index buckets 17 and 18 remain forbidden for CTP runtime rows. |
| CTP decomposition evidence | `SbmSensitivity.mapping_citation_ids` | Keep `index_ctp_decomposition_required` and `index_ctp_decomposition_evidence`; add the NPR decomposition citation id when evidence is present. |
| Vega option maturity | `SbmSensitivity.option_tenor` | Use `6m`, `1y`, `3y`, `5y`, `10y` for CSR vega cells. Missing option tenor remains fail-closed. |
| Curvature shocks | `up_shock_amount`, `down_shock_amount` | Use existing curvature row contract. Unsupported optionality or missing shock data remains fail-closed. |

## Mirrorable Basel Tables

These tables can be mirrored numerically for a `US_NPR_2_0` comparison slice
only when the mirrored data carries NPR-owned citation ids and the profile hash
includes the NPR payload:

- CSR non-sec delta buckets, risk weights, name/tenor/basis correlations,
  bucket 18 absolute aggregation, and cross-bucket gamma.
- CSR sec non-CTP delta buckets, senior/non-senior/high-yield multipliers,
  tranche/tenor/basis correlations, bucket 25 absolute aggregation, and zero
  inter-bucket gamma.
- CSR CTP delta buckets, risk weights, underlying-name/tenor/basis
  correlations, and CSR non-sec style inter-bucket gamma.
- Non-GIRR vega option-tenor and expiry-correlation mechanics, subject to CSR
  family-specific profile-owned citation ids.
- Curvature scenario selection, shock scaling, branch metadata, and
  aggregation mechanics, subject to CSR family-specific profile-owned citation
  ids and the curvature source requirements above.

## NPR-Specific Divergences And Ambiguities

- Proposed `ll.208(c)(3)` and `ll.208(d)(3)` require curvature to ignore the
  bond-CDS basis for the same issuer or tranche. Any first CSR curvature PR must
  add a fixture where `BOND` and `CDS` rows for the same qualifier collapse to a
  single curve for curvature.
- Proposed `ll.208(e)` makes CTP risk factors underlying-name based. Index or
  bespoke CTP inputs must therefore either be decomposed to underlying names or
  fail closed with explicit decomposition evidence requirements.
- Proposed `ll.209(b)(3)` assigns bespoke correlation trading positions to an
  index bucket when substantially similar to an index, otherwise to a bucket of
  their own. The current canonical bucket field can carry the assigned bucket,
  but runtime must not infer substantial similarity; the adapter must provide it.
- Securitization non-CTP sector assignment depends on market convention and
  structural features. Runtime should treat bucket assignment as an input
  contract and fail closed for unknown bucket ids rather than deriving sectors.
- Vega treatment for CSR families should use option maturity, not delta tenor.
  Fixtures must include different option tenors to prove the vega path is not
  accidentally using `tenor`.
- All U.S. NPR CSR cells remain proposed-rule comparison outputs, not final
  regulatory capital.

## Fixture Plan

| Cell | Positive fixture | Required fail-closed cases |
| --- | --- | --- |
| CSR non-sec delta | `csr_nonsec_delta_us_npr_v1`: IG and high-yield issuer rows, same issuer `BOND`/`CDS` basis pair, different tenor pair, bucket 18 absolute aggregation, cross-bucket gamma. | Duplicate id; invalid bucket; missing qualifier; missing tenor; invalid `risk_factor`; stale Basel citation in serialized output. |
| CSR non-sec vega | `csr_nonsec_vega_us_npr_v1`: two issuer buckets and two option tenors, no delta-tenor dependency. | Missing `option_tenor`; unsupported curvature row; invalid bucket; Basel citation leakage. |
| CSR non-sec curvature | `csr_nonsec_curvature_us_npr_v1`: same issuer `BOND`/`CDS` rows proving basis is ignored, high/low branch selection, cross-bucket aggregation. | Missing shock amount; unsupported repo/equity-style risk factor; Basel citation leakage. |
| CSR sec non-CTP delta | `csr_sec_nonctp_delta_us_npr_v1`: senior IG and non-senior/high-yield tranche rows, bucket 25 absolute aggregation, zero inter-bucket gamma. | Missing tranche qualifier; invalid bucket; missing tenor; invalid `risk_factor`; Basel citation leakage. |
| CSR sec non-CTP vega | `csr_sec_nonctp_vega_us_npr_v1`: two tranche buckets and two option tenors. | Missing `option_tenor`; invalid bucket; missing tranche qualifier; Basel citation leakage. |
| CSR sec non-CTP curvature | `csr_sec_nonctp_curvature_us_npr_v1`: same tranche `BOND`/`CDS` rows proving basis is ignored, branch metadata, bucket 25 behavior. | Missing shock amount; missing tranche qualifier; Basel citation leakage. |
| CSR sec CTP delta | `csr_sec_ctp_delta_us_npr_v1`: decomposed underlying-name rows, forbidden index bucket check, CTP decomposition evidence flag. | Missing decomposition evidence; bucket 17/18 row; missing underlying-name qualifier; invalid tenor; Basel citation leakage. |
| CSR sec CTP vega | `csr_sec_ctp_vega_us_npr_v1`: decomposed underlying-name rows with two option tenors. | Missing option tenor; missing decomposition evidence for index-origin row; Basel citation leakage. |
| CSR sec CTP curvature | `csr_sec_ctp_curvature_us_npr_v1`: underlying-name curvature rows with branch metadata and decomposition evidence. | Missing shock amount; missing decomposition evidence; forbidden index buckets; Basel citation leakage. |

## Implementation Order

1. CSR non-sec delta: smallest surface because existing Basel runtime already
   has complete row, batch, and Arrow coverage.
2. CSR sec non-CTP delta: similar delta mechanics but needs tranche-specific
   fixture evidence and bucket 25 coverage.
3. CSR sec CTP delta: depends on decomposition evidence and forbidden index
   bucket tests.
4. CSR vega cells: add after all three delta families have profile-owned
   bucket payloads.
5. CSR curvature cells: add last because basis-ignoring behavior and branch
   metadata need separate fixtures per family.

Each implementation PR must update `PROFILE_SUPPORTED_MEASURES`,
`validation/context.py`, `reference_payload.py`, `REGULATORY_TRACEABILITY.md`,
and the relevant expected-output manifests for the specific cell only.
