# frtb-common

Shared primitives for the `frtb-capital` workspace.

This scaffold exists so capital-component packages can depend on a concrete
foundation package before the shared abstractions are fully extracted from
`frtb-ima`. It is intentionally small: broad migration of IMA-local utilities is
tracked separately and should not be mixed into scaffold work.

Current contents:

- explicit unsupported/unimplemented exception types;
- immutable package metadata for scaffold status;
- implementation and validation status enums.

The package performs no capital calculation.
