# Attribution Maturity Gates

The package maturity registry includes an optional `attribution_status` field for
capital-producing and orchestration packages. The field makes attribution claims
auditable without forcing packages to fake unsupported methods.

## Status Values

- `documentation_only`: the package has an `ATTRIBUTION.md` guide that states
  current support and limitations, but does not claim runtime attribution
  evidence.
- `allocation_only`: the package can allocate or explain completed capital with
  additive records, but does not project the full shared attribution contract.
- `shared_projection`: the package projects completed capital results into
  shared `CapitalContribution` records and includes reconciliation plus
  unsupported-branch evidence.
- `full_bundle`: the package or orchestration layer can produce or consume a
  component/suite bundle compatible with the shared reconciliation contract.

## Evidence Rules

Capital and orchestration packages must declare an attribution status and keep a
package-local `ATTRIBUTION.md`. Non-capital infrastructure packages should not
set `attribution_status` unless they become capital-producing.

Runtime attribution claims require package-local tests in
`docs/quality/package_maturity.toml`:

- `attribution`: core attribution helper or projection behavior.
- `attribution-reconciliation`: contribution plus residual totals reconcile to
  completed capital, including tolerance behavior.
- `attribution-unsupported-branches`: unsupported or non-Euler branches are
  explicit records or documented failures, not silent pro-rata allocation.
- `attribution-bundle`: full-bundle compatibility for packages that claim it.

Placeholder evidence such as `test_placeholder` or tests that only assert `True`
does not satisfy attribution gates. If a package cannot yet support a runtime
status honestly, keep `attribution_status = "documentation_only"` and describe
unsupported branches in `ATTRIBUTION.md`.
