# frtb-drc Regulatory Assumptions

This document records the assumptions that bound the implemented `frtb-drc`
runtime. It complements `REGULATORY_TRACEABILITY.md` and the model
documentation pack. Outputs remain synthetic engineering and validation
evidence, not final regulatory capital.

## Data Assumptions

- Upstream systems provide canonical DRC positions with stable position ids,
  source lineage, legal entity, desk, issuer/tranche/index identifiers, default
  direction, maturity, currency, and profile-specific credit attributes.
- FX rates are supplied through `DrcCalculationContext` for non-base-currency
  rows; missing rates fail validation.
- Banking-book securitisation risk weights are supplied as typed
  `DrcRiskWeightEvidence` where Basel MAR22, EU CRR3, or PRA UK CRR mechanics
  require them. The package does not derive those weights internally.
- Fair-value-cap and offset/decomposition evidence is supplied explicitly for
  profile paths that require complete evidence. Missing or stale evidence fails
  closed.

## Runtime Assumptions

- `US_NPR_2_0`, `BASEL_MAR22`, `EU_CRR3`, and `PRA_UK_CRR` support
  non-securitisation, securitisation non-CTP, and CTP DRC row/batch paths.
- Unsupported future profiles or unmapped risk classes must raise explicit
  `UnsupportedRegulatoryFeatureError` or `DrcInputError`; they must not emit
  zero, Basel-default, EU-default, or PRA-default placeholder capital.
- Row results may contain multiple DRC classes in one `DrcCapitalResult`.
  Arrow/batch ingress remains class-specific, and mixed-class Arrow tables fail
  closed before calculation.
- Attribution records explain the committed capital result. Stable branches use
  analytical records; floors, missing lineage, zero denominators, profile
  changes, or unsupported branch shapes emit explicit residual or unsupported
  records that reconcile to total DRC.

## Validation Assumptions

- Regression fixtures are synthetic and deterministic.
- Fixture evidence proves repo-owned mechanics and citation propagation for
  supported inputs; it does not prove production source-data quality,
  supervisory approval, legal interpretation, or firm-level regulatory
  submission readiness.
