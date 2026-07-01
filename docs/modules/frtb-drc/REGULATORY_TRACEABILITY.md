# frtb-drc Regulatory Traceability

This document is the implemented-maturity traceability entrypoint for
`frtb-drc`. It summarizes where regulatory mechanics are mapped to code,
fixtures, and tests. It is not legal advice and does not present outputs as
final regulatory capital.

For a plain-English description of supported paths, evidence, support boxes,
and fail-closed behavior, see
[`REGULATORY_SUPPORT_EVIDENCE.md`](REGULATORY_SUPPORT_EVIDENCE.md).

## Coverage Summary

| Requirement area | Regulatory anchors | Code refs | Evidence |
| --- | --- | --- | --- |
| Gross and net JTD | Basel MAR22.9-MAR22.18; proposed U.S. section `__.210(b)`; CRR3 Articles 325w, 325x, 325z, 325ab, and 325ac; PRA Market Risk Part Articles 325w, 325x, 325z, 325ab, and 325ac | `gross_jtd.py`, `maturity.py`, `netting.py`, `kernel/nonsec.py`, `kernel/securitisation.py`, `kernel/ctp.py` | `test_drc_gross_jtd.py`, `test_drc_maturity.py`, `test_drc_netting.py`, `test_drc_securitisation.py`, `test_drc_ctp.py` |
| Bucket, risk weight, HBR, and category capital | Basel MAR22.19-MAR22.47; proposed U.S. section `__.210(b)-(d)`; CRR3 Articles 325y, 325aa, and 325ad; PRA Market Risk Part Articles 325y, 325aa, and 325ad | `capital.py`, `reference_data.py`, `kernel/nonsec.py`, `kernel/securitisation.py`, `kernel/ctp.py` | `test_drc_capital.py`, `test_drc_reference_data.py`, `test_drc_securitisation.py`, `test_drc_ctp.py` |
| Profile support and fail-closed guards | `PROFILE_SUPPORT_MATRIX.md`; CRR3 Articles 325w-325ad; PRA Market Risk Part Articles 325v-325ad | `regimes.py`, `regime_citations_eu_pra.py`, `validation.py`, `batch_validation.py` | `test_drc_regimes.py`, `test_drc_public_api.py` |
| Arrow and batch handoff | ADR 0023 tabular handoff boundary | `adapters/arrow.py`, `adapters/positions.py`, `batch.py`, `batch_validation.py` | `test_drc_arrow_batch.py`, `tests/fixtures/handoff/` |
| Attribution and reconciliation | ADR 0012 capital impact attribution | `attribution.py`, `assembly/result.py`, `audit.py` | `test_drc_attribution.py`, `test_drc_capital.py` |

## Profile Evidence

All known DRC rule profiles in `drc_profile_support_matrix()` are supported for
non-securitisation, securitisation non-CTP, and CTP:

- `US_NPR_2_0`: `drc_nonsec_v1`, `drc_nonsec_v2`,
  `drc_sec_nonctp_v1`, and `drc_ctp_v1`.
- `BASEL_MAR22`: Basel non-securitisation tests plus
  `drc_basel_sec_nonctp_v1` and `drc_basel_ctp_v1`.
- `EU_CRR3`: `drc_eu_nonsec_v1`, `drc_eu_sec_nonctp_v1`, and
  `drc_eu_ctp_v1`.
- `PRA_UK_CRR`: `drc_pra_nonsec_v1`, `drc_pra_sec_nonctp_v1`, and
  `drc_pra_ctp_v1`.

The machine-readable crosswalk is
[`docs/regulatory/crosswalk/frtb-drc.yml`](../../regulatory/crosswalk/frtb-drc.yml).
The runtime-readable support matrix is
[`PROFILE_SUPPORT_MATRIX.md`](PROFILE_SUPPORT_MATRIX.md).
