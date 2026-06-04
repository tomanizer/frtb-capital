# Assumptions And Limitations

## Implemented Scope

The current capital-producing scope is:

- U.S. NPR 2.0 non-securitisation, securitisation non-CTP, and CTP row/batch
  paths;
- Basel MAR22 non-securitisation row/batch paths using MAR22.12,
  MAR22.15-MAR22.18, MAR22.22, and MAR22.24;
- Basel MAR22 securitisation non-CTP row/batch paths using MAR22.31-MAR22.35
  and typed MAR22.34 evidence;
- Basel MAR22 CTP row/batch paths using MAR22.36-MAR22.45 and typed MAR22.42
  evidence;
- EU CRR3 non-securitisation row/batch paths using Article 325w, Article 325x,
  Article 325y, and ECAI/CQS mapping evidence;
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

- EU CRR3 securitisation non-CTP and CTP paths pending Articles 325z-325ad and
  related securitisation/CTP mappings;
- PRA UK CRR DRC paths pending PRA PS1/26 Chapter 3 and Appendix 1 mappings;
- internal derivation of banking-book securitisation risk weights;
- final regulatory reporting and firm-level capital consolidation.

## Validation Limits

Validation evidence uses synthetic fixtures and deterministic tests. It proves
that the committed mechanics are reproducible for supported inputs, but it does
not establish production model approval, source-data quality, legal
interpretation, or supervisory acceptance.
