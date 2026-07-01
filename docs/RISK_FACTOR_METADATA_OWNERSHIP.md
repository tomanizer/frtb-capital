# Risk-Factor Metadata Ownership

This suite treats risk-factor metadata as a governed read model, not as
calculation logic embedded in capital kernels.

## Ownership

- `frtb-common` owns only stable value primitives such as `RiskFactorId`,
  mapping-version tokens, bucket IDs, tenor, currency, and opaque risk-class or
  risk-type codes.
- `frtb-result-store` owns canonical synthetic metadata snapshots, mapping
  versions, lineage rows, RFET/IMA evidence states, and read APIs for Navigator
  or future OLAP adapters.
- Component packages consume calculation-ready attributes supplied by upstream
  adapters and preserve stable IDs/provenance in material result or audit
  records. They must not import `frtb_result_store`, query canonical metadata,
  or infer enterprise reference data.
- `frtb-orchestration` composes risk-factor-aware aggregate and evidence views
  over resolved component/result-store rows. It must emit explicit `no_data` or
  `unsupported` states when exact contribution or evidence rows do not exist.
- Dashboard/Navigator views consume result-store-backed APIs. Browser code must
  not infer regulatory risk class, bucket, modellability, liquidity horizon, or
  RFET status.

## Validation Expectations

- Risk-factor IDs are stable within a run/snapshot and duplicates are rejected
  by result-store validation.
- Mapping versions propagate from metadata snapshots into component audit rows
  wherever the component consumes supplied risk-factor metadata.
- Missing RFET, UPL, CRIF, stress-vector, or contribution datasets are displayed
  as explicit `no_data` or `unsupported` states, never fabricated values.
- Component tests should keep metadata propagation assertions separate from
  capital-number assertions unless the same fixture naturally covers both.
- Frontend tests or manual verification should exercise risk-factor selection
  and at least one no-data state when the Navigator surface changes.
