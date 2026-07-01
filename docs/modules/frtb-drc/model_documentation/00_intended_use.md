# Intended Use

## Model Purpose

`frtb-drc` is the Default Risk Charge component in the `frtb-capital` monorepo.
It assembles standardised default-risk capital from prepared issuer, tranche,
and position inputs for the supported non-securitisation, securitisation
non-CTP, and CTP row paths.

The package is an ex-post capital layer. It does not source market data, assign
internal ratings, perform issuer aggregation upstream of the public API, or
produce firm-level capital consolidation.

## Intended Users

Quantitative developers, credit-risk methodology teams, model validators, and
engineering reviewers evaluating jump-to-default mechanics, netting,
reconciliation, and audit lineage for a FRTB DRC-style prototype.

## Supported Scope (current)

The public API supports cited **non-securitisation DRC**, **securitisation
non-CTP DRC**, and **CTP DRC** row paths with:

- gross jump-to-default inputs and maturity scaling;
- issuer, tranche, explicit replication-group netting, and bucket/category
  aggregation;
- deterministic reconciliation and audit metadata;
- analytical, residual, or unsupported attribution records that reconcile to
  total DRC without changing the capital number;
- explicit fail-closed behaviour when required upstream risk weights,
  same-pool/same-tranche identity, or replication/decomposition evidence is
  missing.

Supported profile coverage is:

- `US_NPR_2_0`: non-securitisation, securitisation non-CTP, and CTP row and
  batch paths, with securitisation/CTP risk weights supplied as cited
  `DrcRiskWeightEvidence` inputs or legacy low-level run-scoped maps.
- `BASEL_MAR22`: non-securitisation row and batch paths using MAR22.12 LGD,
  MAR22.15-MAR22.18 maturity weighting, MAR22.22 buckets, and MAR22.24
  letter-grade risk weights; securitisation non-CTP row and batch paths using
  MAR22.31 bucket mappings, MAR22.34 typed banking-book securitisation
  risk-weight evidence, MAR22.34 fair-value cap evidence, and MAR22.35
  category aggregation; CTP row and batch paths using MAR22.36-MAR22.45 and
  typed MAR22.42 banking-book securitisation risk-weight evidence.
- `EU_CRR3`: non-securitisation row and batch paths using Article 325w
  gross JTD/LGD, Article 325x netting and maturity weighting, Article 325y
  bucket/risk-weight/HBR/category mechanics, and ECAI/CQS mapping evidence;
  securitisation non-CTP row and batch paths using Article 325z, Article
  325aa, typed banking-book securitisation risk-weight evidence,
  fair-value-cap evidence, and explicit offset-group evidence; CTP row and
  batch paths using Article 325ab, Article 325ac, Article 325ad, typed
  banking-book securitisation risk-weight evidence, decomposition evidence, and
  explicit offset-group evidence.
- PRA UK CRR non-securitisation row and batch paths using Article 325w,
  Article 325x, Article 325y, and deterministic fixture evidence.
- PRA UK CRR securitisation non-CTP row and batch paths using Article 325z,
  Article 325aa, typed risk-weight, fair-value-cap, offset, and deterministic
  fixture evidence.
- PRA UK CRR CTP row and batch paths using Article 325ab, Article 325ac,
  Article 325ad, typed risk-weight, decomposition, offset, and deterministic
  fixture evidence.

Known fail-closed profile paths for the current rule-profile matrix are:

- None for the known DRC rule profiles listed in
  [`PROFILE_SUPPORT_MATRIX.md`](../PROFILE_SUPPORT_MATRIX.md).

Regulatory anchors for the supported path are recorded in
[`REGULATORY_REQUIREMENTS.md`](../REGULATORY_REQUIREMENTS.md) and
[`BASEL_FRTB_DRC.yml`](../../../../packages/frtb-drc/docs/requirements/BASEL_FRTB_DRC.yml).

## Out of Scope

- final regulatory capital or supervisory reporting;
- internal derivation of banking-book securitisation risk weights;
- inferred securitisation fair-value caps without typed evidence and profile
  permission;
- treating baseline-vs-candidate impact analysis as regulatory capital,
  marginal contribution, or supervisory reporting;
- silent fallback when required inputs or regulatory features are unsupported.

## Prototype Caution

Outputs are deterministic model-validation evidence for supported inputs. They
are not final regulatory capital and do not substitute for independent model
validation, legal interpretation, or supervisory approval.
