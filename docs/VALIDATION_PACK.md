# Validation Packs

This suite-level page points reviewers to package-specific validation bundles.
Package evidence remains close to the package that owns the calculation model.

## FRTB-IMA

- Formal model documentation pack:
  [`FRTB-IMA model documentation pack`](modules/frtb-ima/model_documentation/README.md)
- Package validation-pack build instructions:
  [`packages/frtb-ima/docs/VALIDATION_PACK.md`](../packages/frtb-ima/docs/VALIDATION_PACK.md)
- Deterministic validation notebooks:
  [`packages/frtb-ima/notebooks/`](../packages/frtb-ima/notebooks/)

The `frtb-ima` validation pack is built from the committed synthetic
`capital_run_v1` fixture. It is not a regulatory report and does not present
final regulatory capital.

## Challenger Models

- Suite challenger register:
  [`docs/validation/challenger_models.yml`](validation/challenger_models.yml)

Challenger implementations are used as independent reconciliation references.
They are not regulatory sources, and their licenses determine whether they may be
run as black-box benchmarks, inspected, copied, or linked.

## Component Evidence Index

Package validation evidence is tracked by maturity status rather than by an
old scaffold/implemented split. Current public status is canonical in
[`docs/quality/package_maturity.toml`](quality/package_maturity.toml) and the
generated [`docs/quality/PACKAGE_STATUS.md`](quality/PACKAGE_STATUS.md).

| Package | Current evidence home |
| --- | --- |
| `frtb-common` | Shared regulatory and status helpers are covered by `packages/frtb-common/tests/` and the maturity registry. |
| `frtb-sbm` | Runtime traceability, assumptions, and source manifests live under [`packages/frtb-sbm/docs/`](../packages/frtb-sbm/docs/); suite model docs live under [`docs/modules/frtb-sbm/`](modules/frtb-sbm/). |
| `frtb-drc` | Runtime status, support matrix, model documentation, and traceability are linked from [`docs/modules/frtb-drc/README.md`](modules/frtb-drc/README.md). |
| `frtb-rrao` | Model documentation, package-local traceability, performance, allocation, and mutation evidence are linked from [`docs/modules/frtb-rrao/README.md`](modules/frtb-rrao/README.md). |
| `frtb-cva` | Runtime traceability, assumptions, and source manifests live under [`packages/frtb-cva/docs/`](../packages/frtb-cva/docs/); suite model docs live under [`docs/modules/frtb-cva/`](modules/frtb-cva/). |
| `frtb-orchestration` | Suite arithmetic, SA composition, IMA/CVA handoffs, and end-to-end fixture evidence are summarized in [`docs/modules/frtb-orchestration/README.md`](modules/frtb-orchestration/README.md). |
| `frtb-result-store` | Storage contracts, backend acceptance, public API, and durability evidence are linked from [`docs/modules/frtb-result-store/README.md`](modules/frtb-result-store/README.md). |

Formal validation packs should be added or promoted only when the owning
package has real fixture, comparator, model documentation, and monitoring
evidence. Do not use placeholder validation-pack pages as maturity evidence.
