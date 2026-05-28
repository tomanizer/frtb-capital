# Standardised Approach Composition

The Standardised Approach is a regulatory composition, not a standalone
workspace package.

Basel MAR20.4 defines market-risk Standardised Approach capital as the sum of:

- sensitivities-based method capital;
- default risk capital; and
- residual risk add-on.

The suite therefore represents SA through three planned component packages:

| SA component | Package | Documentation |
| --- | --- | --- |
| Sensitivities-based method | `frtb-sbm` | [frtb-sbm](frtb-sbm/REGULATORY_REQUIREMENTS.md) |
| Default risk charge | `frtb-drc` | [frtb-drc](frtb-drc/REGULATORY_REQUIREMENTS.md) |
| Residual risk add-on | `frtb-rrao` | [frtb-rrao](frtb-rrao/REGULATORY_REQUIREMENTS.md) |

`frtb-orchestration` owns the composed SA total:

```text
SA capital = SBM capital + DRC capital + RRAO capital
```

The same component stack is also the fallback route when a desk is not
IMA-eligible. The component packages own their own calculations and audit
records; orchestration owns routing, aggregation, and cross-component
reconciliation.

This taxonomy is recorded in
[ADR 0010](../decisions/0010-standardised-approach-component-taxonomy.md).
