# frtb-common

`frtb-common` is the scaffolded shared foundation package for the
`frtb-capital` workspace.

## Package Status

- Package directory: `packages/frtb-common`
- Import name: `frtb_common`
- Implementation status: shared primitives
- Validation status: unit-tested shared handoff and CRIF normalization helpers

Current runtime contents are deliberately small: package status metadata,
explicit unsupported/unimplemented exception types, Arrow-backed tabular
handoff primitives, and package-neutral CRIF-to-Arrow normalization. The CRIF
helpers own source-column discovery, alias normalization, primitive coercion,
accepted/rejected partitioning, diagnostics, metadata, and source hashes.
Capital packages still own RiskType mapping and regulatory validation.

`frtb-common` must not import from capital component packages.
