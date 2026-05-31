# Intended Use

## Model Purpose

`frtb-drc` is the Default Risk Charge component in the `frtb-capital` monorepo.
It assembles standardised default-risk capital from prepared issuer and position
inputs for the supported non-securitisation path.

The package is an ex-post capital layer. It does not source market data, assign
internal ratings, perform issuer aggregation upstream of the public API, or
produce firm-level capital consolidation.

## Intended Users

Quantitative developers, credit-risk methodology teams, model validators, and
engineering reviewers evaluating jump-to-default mechanics, netting,
reconciliation, and audit lineage for a FRTB DRC-style prototype.

## Supported Scope (current)

The public API supports cited **non-securitisation DRC** with:

- gross jump-to-default inputs and maturity scaling;
- issuer netting and bucket/category aggregation;
- deterministic reconciliation and audit metadata;
- explicit fail-closed behaviour for unsupported securitisation non-CTP and CTP
  paths.

Regulatory anchors for the supported path are recorded in
[`REGULATORY_REQUIREMENTS.md`](../REGULATORY_REQUIREMENTS.md) and
[`requirements/BASEL_FRTB_DRC.yml`](../requirements/BASEL_FRTB_DRC.yml).

## Out of Scope

- final regulatory capital or supervisory reporting;
- securitisation non-CTP and correlation-trading portfolio DRC until separately
  implemented with cited requirements and fixtures;
- silent fallback when required inputs or regulatory features are unsupported.

## Prototype Caution

Outputs are deterministic model-validation evidence for supported inputs. They
are not final regulatory capital and do not substitute for independent model
validation, legal interpretation, or supervisory approval.
