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
- explicit fail-closed behaviour when required upstream risk weights,
  same-pool/same-tranche identity, or replication/decomposition evidence is
  missing.

Regulatory anchors for the supported path are recorded in
[`REGULATORY_REQUIREMENTS.md`](../REGULATORY_REQUIREMENTS.md) and
[`requirements/BASEL_FRTB_DRC.yml`](../requirements/BASEL_FRTB_DRC.yml).

## Out of Scope

- final regulatory capital or supervisory reporting;
- internal derivation of banking-book securitisation risk weights;
- optional securitisation fair-value caps until a cited control and input
  contract are implemented;
- silent fallback when required inputs or regulatory features are unsupported.

## Prototype Caution

Outputs are deterministic model-validation evidence for supported inputs. They
are not final regulatory capital and do not substitute for independent model
validation, legal interpretation, or supervisory approval.
