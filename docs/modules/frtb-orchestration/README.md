# frtb-orchestration

`frtb-orchestration` is the scaffolded suite-level aggregation package.

## Package Status

- Package directory: `packages/frtb-orchestration`
- Import name: `frtb_orchestration`
- Implementation status: scaffolded; aggregation not implemented
- Validation status: not started

This is the only package allowed to depend on multiple capital component
packages. It will own:

- composed SA capital from `frtb-sbm + frtb-drc + frtb-rrao`;
- IMA fallback routing when a desk is not model-eligible;
- top-of-the-house aggregation and cross-component reconciliation.

`calculate_suite_capital` raises an explicit unimplemented-component error until
component packages produce typed, audited outputs.
