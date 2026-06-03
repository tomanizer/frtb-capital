# Assumptions And Limitations

## Implemented Scope

The current capital-producing scope is:

- U.S. NPR 2.0 non-securitisation, securitisation non-CTP, and CTP row/batch
  paths;
- Basel MAR22 non-securitisation row/batch paths using MAR22.12,
  MAR22.15-MAR22.18, MAR22.22, and MAR22.24;
- class-specific Arrow batches for non-securitisation, securitisation non-CTP,
  and CTP under ADR 0023.

## Required Evidence Inputs

The package requires upstream evidence where the regulatory mechanics depend on
source-system facts:

- FX rates for non-base-currency rows;
- securitisation non-CTP risk weights, fair-value cap eligibility, and
  offset-group evidence where applicable;
- CTP risk weights and replication-group evidence where applicable.

Missing evidence fails validation or raises `UnsupportedRegulatoryFeatureError`
before capital is emitted.

## Unsupported Scope

The following paths remain unsupported and fail closed:

- Basel MAR22 CTP pending MAR22.42 decomposition and risk-weight mappings;
- EU CRR3 DRC paths pending Article 325w and related CQS/RTS mappings;
- PRA UK CRR DRC paths pending PRA PS1/26 Chapter 3 and Appendix 1 mappings;
- internal derivation of banking-book securitisation risk weights;
- final regulatory reporting and firm-level capital consolidation.

## Validation Limits

Validation evidence uses synthetic fixtures and deterministic tests. It proves
that the committed mechanics are reproducible for supported inputs, but it does
not establish production model approval, source-data quality, legal
interpretation, or supervisory acceptance.
