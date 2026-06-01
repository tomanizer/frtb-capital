# SBM regulatory assumptions and implementation boundaries

This document records source-cited implementation decisions for `frtb-sbm`.
For a bidirectional code/regulation map, see
[`REGULATORY_TRACEABILITY.md`](REGULATORY_TRACEABILITY.md). For link-only source
metadata, see [`regulatory_sources.yml`](regulatory_sources.yml).

`frtb-sbm` delivers a partial runtime slice for GIRR delta/vega, FX delta,
equity delta, commodity delta, CSR delta, and curvature capital under cited
Basel MAR21 mechanics.
No document or test in this package should describe outputs as final regulatory
capital.

## Phase-1 basis

The first capital-producing slices target canonical inputs for:

1. Basel MAR21 GIRR delta and vega mechanics, including bucket assignment,
   risk weights, intra-bucket aggregation, inter-bucket aggregation, and
   correlation scenarios.
2. Basel MAR21 FX, equity, commodity, and CSR delta mechanics on the shared
   aggregation engine.
3. Basel MAR21.96-MAR21.101 curvature mechanics through the row-wise public API,
   with CVR+/CVR- branch selection and squared curvature correlations.
   FX curvature rows that require the MAR21.98 1.5 scalar identify that treatment
   explicitly through `FX_CURVATURE_SCALAR_1_5_FLAG` and a two-currency
   `qualifier`.
4. U.S. NPR 2.0 proposed standardized non-default capital requirement, section
   V.A.7.a, as a comparison profile where explicitly supported.
5. Explicit fail-closed behavior for unsupported risk-class, risk-measure, or
   curvature sub-feature combinations until their own cited issues land.

The package treats the U.S. NPR 2.0 profile as proposed-rule material. Any
future final-rule change must update citations, profiles, fixtures, and expected
results in the same PR that changes behavior.

## Risk-factor assignment boundary

Risk-factor and bucket assignment is an upstream responsibility. The package
accepts caller-supplied canonical `SbmSensitivity` records with explicit bucket
and qualifier fields. Adapter modules may translate source-system fields into
canonical enums, but they must record source column lineage and mapping
warnings.

This boundary comes from the need to apply Basel MAR21.8 and section V.A.7.a
steps one and two deterministically. Unsupported or ambiguous mapping evidence
must fail before capital is calculated.

## Profile-driven parameters

Risk weights, bucket definitions, tenor sets, liquidity horizons, intra-bucket
correlations, inter-bucket correlations, scenario labels, and support flags
belong in versioned rule profiles and reference-data helpers (SBM-DEC-003).
Calculation kernels receive typed values and must not branch on hard-coded
regulator names.

Every rule-driven quantity must carry a citation id linked to a paragraph,
article, section, or table in the active profile.

## Aggregation boundary

Intra-bucket and inter-bucket aggregation are shared primitives reused across
risk classes (SBM-DEC-004). GIRR delta phase 1 exercises:

- weighted sensitivity calculation with cited risk weights;
- intra-bucket `Kb` calculation with pairwise correlation evidence;
- low, medium, and high correlation scenario totals;
- profile-prescribed scenario selection for the final risk-class capital.

GIRR vega liquidity-horizon scaling and curvature up/down branch logic are
implemented for the supported Basel paths. High-volume curvature batch capital
remains outside the current runtime path; the GIRR Arrow/batch curvature handoff
is validation-only.

## Fail-closed unsupported scope

Any requested path without cited rule mapping and deterministic test evidence
must raise an explicit unsupported-feature or input error. The package must not
emit zero, empty, or placeholder capital for unsupported risk classes, risk
measures, buckets, or profile features (SBM-BOUNDARY-003).

## CNH/CNY mapping (ADR 0017)

Basel MAR21 treats onshore/offshore renminbi differently across risk classes:

| Risk class | CNY | CNH | Regulatory basis |
| --- | --- | --- | --- |
| GIRR delta/vega | Bucket `8` | Bucket `17` (separate bucket) | MAR21.41; MAR21.8(c) separate curves |
| FX delta | Bucket `CNY` | Normalised to `CNY` bucket | MAR21.14(4); MAR21.88 specified pairs |

Callers must supply GIRR sensitivities with the curve denomination matching the
canonical bucket currency. FX inputs may use `CNH`; `normalise_fx_delta_currency_code`
maps to `CNY` before bucket lookup.

## CSR securitisation reference tables

The CSR securitisation **CTP** and **non-CTP** reference tables
(`csr_sec_ctp_reference_data.py`, `csr_sec_nonctp_reference_data.py`) are
present and parameter-complete. Their BASEL_MAR21 delta and curvature paths are
capital-producing, while unsupported profiles and unmapped sub-features still
fail closed. The tables were cross-checked against the Basel
MAR21 consolidated text on 2026-05-31 and confirmed correct:

| Table | Basel source | Verification outcome |
| --- | --- | --- |
| CSR sec **CTP** delta risk weights, buckets 1–16 | MAR21.59 (Table 6) | Match exactly: IG `4/4/8/5/4/3/2/6%`, HY `13/13/16/10/12/12/12/13%`. |
| CSR sec **non-CTP** senior-IG weights, buckets 1–8 | MAR21.71 | Match exactly: `0.9/1.5/2.0/2.0/0.8/1.2/1.2/1.4%`. |
| CSR sec **non-CTP** non-senior / non-IG weights | MAR21.71 | `_NON_SENIOR_MULTIPLIER = 1.25` and `_HIGH_YIELD_MULTIPLIER = 1.75` are the **literal regulatory derivation**, not an approximation. MAR21.71 gives the worked example "the risk weight for bucket 17 is equal to 1.75 × 0.9% = 1.575%". |

**Note for future audits:** the `×1.25` / `×1.75` multipliers in
`csr_sec_nonctp_reference_data.py` are prescribed by MAR21.71 itself. They are
not a modelling shortcut and do not need re-derivation. Delta and row-wise
curvature aggregation/capital assembly are implemented for these risk classes;
remaining work is high-volume curvature handoff coverage and broader regulatory
profile coverage.

## Audit and orchestration boundary

The first successful `SbmCapitalResult` must already include stable ids, profile
and input hashes, scenario metadata, and reconciliation records before
orchestration consumes it (SBM-DEC-007). SA composition (SBM + DRC + RRAO)
belongs in `frtb-orchestration`, not in this package.

## Synthetic fixtures only

Phase-1 tests and examples use synthetic canonical fixtures only. No proprietary
market data or adapter-specific conventions are used in the core runtime path.
