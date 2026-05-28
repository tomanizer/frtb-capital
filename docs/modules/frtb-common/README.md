# frtb-common

`frtb-common` is the scaffolded shared foundation package for the
`frtb-capital` workspace.

## Package Status

- Package directory: `packages/frtb-common`
- Import name: `frtb_common`
- Implementation status: scaffolded shared primitives
- Validation status: not started

Current runtime contents are deliberately small: package status metadata and
explicit unsupported/unimplemented exception types. Broader extraction of audit,
calendar, sign-convention, policy, and scenario primitives from `frtb-ima` is a
separate workstream.

`frtb-common` must not import from capital component packages.
