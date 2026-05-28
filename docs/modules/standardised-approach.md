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

## Implementation Boundaries

There is no `frtb-sa` package. Shared SA concepts belong in one of three
places:

- `frtb-common`: rule profiles, citations, calculation context, sign
  conventions, validation errors, audit-record primitives, and generic
  aggregation math.
- Component packages: `frtb-sbm`, `frtb-drc`, and `frtb-rrao` own their
  canonical inputs, calculation kernels, fixtures, and component audit records.
- `frtb-orchestration`: composed SA total, IMA fallback routing, run manifests,
  reporting adapters, and cross-component reconciliation.

Fallback is explicit. If `frtb-ima` emits a non-eligible desk signal,
orchestration routes that desk to the SA component stack. If a component cannot
calculate an input or regulatory feature, it raises an explicit unsupported
feature error or returns a typed fallback-required status; it must not emit zero
capital or an empty successful result silently.

The build order should keep the component boundaries visible:

1. Create `frtb-common` primitives for rule profiles, citations, calculation
   context, audit metadata, validation errors, and shared numerical helpers.
2. Add `frtb-sbm` with canonical sensitivity inputs and one cited end-to-end
   vertical slice for a risk class and risk measure.
3. Add `frtb-drc` with a non-securitisation JTD and bucket-capital vertical
   slice.
4. Add `frtb-rrao` with residual-risk classification and additive capital.
5. Add `frtb-cva` after counterparty exposure and hedge contracts are agreed.
6. Add `frtb-orchestration` once at least two capital packages produce typed,
   audited results.

This taxonomy is recorded in
[ADR 0010](../decisions/0010-standardised-approach-component-taxonomy.md).
