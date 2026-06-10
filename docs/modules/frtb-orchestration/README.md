# frtb-orchestration

`frtb-orchestration` is the suite-level capital aggregation package.

## Package Status

- Package directory: `packages/frtb-orchestration`
- Import name: `frtb_orchestration`
- Implementation status: implemented; SA arithmetic, IMA summary contract, CVA
  summary contract, and suite aggregation (`IMA + SA + CVA`) are all
  implemented.
- Validation status: pending independent model validation

## Architecture

This is the only package allowed to depend on multiple capital component
packages. It owns the cross-component boundary and implements:

- Composed SA capital from `frtb-sbm + frtb-drc + frtb-rrao` via
  `compose_standardised_approach_capital`.
- IMA summary contract (`ImaCapitalSummary`) and duck-typed recogniser
  (`recognise_ima_summary`) for consuming IMA audit log shapes.
- CVA summary contract (`CvaCapitalSummary`) and duck-typed recogniser
  (`recognise_cva_summary`) for consuming CVA capital result shapes.
- Top-of-house suite capital aggregation (`calculate_suite_capital`):
  `IMA + SA + CVA` with cross-component validation of calculation date,
  base currency, and regulatory jurisdiction family.
- Attribution-ready branch metadata and fallback counts are preserved through
  component summaries so unsupported or residual branches remain explainable
  after suite aggregation.

## Public API

The stable top-level integration surface is defined in
[PUBLIC_API.md](PUBLIC_API.md). The examples below show the primary suite
capital workflow.

### `calculate_suite_capital`

```python
from frtb_orchestration import (
    ImaCapitalSummary,
    SuiteCapitalResult,
    calculate_suite_capital,
    compose_standardised_approach_capital,
    recognise_cva_summary,
    recognise_ima_summary,
)

suite_result: SuiteCapitalResult = calculate_suite_capital(
    ima_summary=ima_summary,        # ImaCapitalSummary
    sa_result=sa_result,            # StandardisedApproachCapitalResult
    cva_summary=cva_summary,        # CvaCapitalSummary
    run_id="suite-run-2026-03-31",  # optional
)
```

All three component inputs must share the same `calculation_date`,
`base_currency`, and regulatory jurisdiction family (Basel, US NPR, or EU
CRR3). Mixed-family inputs raise `OrchestrationInputError`. Missing or
incorrectly typed inputs also raise `OrchestrationInputError`.

### `ImaCapitalSummary`

Construct directly from IMA capital run outputs:

```python
from frtb_orchestration import ImaCapitalSummary

ima_summary = ImaCapitalSummary(
    package_name="frtb-ima",
    run_id="ima-run-001",
    calculation_date=date(2026, 3, 31),
    base_currency="USD",
    profile_id="FED_NPR_2_0",        # or "ECB_CRR3", "PRA_UK_CRR"
    total_ima_capital=1_234_567.89,
    ima_eligible_desk_count=4,
    sa_fallback_desk_count=1,
    policy_hash="<sha256>",
    input_hash="<sha256>",
    citations=("MAR31.25",),
)
```

Or use `recognise_ima_summary` to duck-type from a `CapitalRunAuditLog`-shaped
object that carries `run_id`, `as_of_date`/`calculation_date`, `base_currency`,
`regime`/`profile_id`, `total_market_risk_capital`/`total_ima_capital`,
`policy_hash`, `inputs_hash`/`input_hash`.

### SA composition

`compose_standardised_approach_capital` accepts `ComponentCapitalSummary`
objects from SBM, DRC, and RRAO via their `to_component_summary` adapters.
Components must share jurisdiction family, calculation date, and base currency.
See ADR 0022 and ADR 0029.

### CVA handoff

`recognise_cva_summary` accepts the public `CvaCapitalResult` from
`calculate_cva_capital` and returns a `CvaCapitalSummary` for
top-of-house use.

### Suite jurisdiction family

`suite_jurisdiction_family(profile_id)` maps any recognised IMA regime,
SA profile, or CVA profile string to a canonical family label (`"BASEL"`,
`"US_NPR"`, or `"EU_CRR3"`). Components from different families cannot be
composed into a single suite result.

### Teaching notebook

The runnable notebook
[`packages/frtb-orchestration/notebooks/00_suite_aggregation.ipynb`](../../../packages/frtb-orchestration/notebooks/00_suite_aggregation.ipynb)
shows the summary handoff path with Mermaid suite flow, synthetic
`ComponentCapitalSummary`, `ImaCapitalSummary`, and `CvaCapitalSummary` inputs,
SA composition, top-of-house suite aggregation, attribution report construction,
and mixed-jurisdiction rejection.

Run it through the root notebook target or directly:

```bash
MPLBACKEND=Agg IPYTHONDIR=$PWD/.pytest_cache/ipython uv run --with pytest,nbmake --directory packages/frtb-orchestration pytest --nbmake notebooks
```

### Result-store handoff

`SuiteCapitalResult` and `StandardisedApproachCapitalResult` carry stable run
identity, component summaries, branch metadata, source citations, input hashes,
and fallback counts that can be converted into result-store nodes, measures,
lineage refs, and attribution records. Orchestration does not write storage
artifacts directly; callers hand completed suite results to
`frtb-result-store` adapters after component calculations finish.

See the result-store demo
[`packages/frtb-result-store/examples/run_demo.py`](../../../packages/frtb-result-store/examples/run_demo.py)
for a runnable synthetic `ResultBundle` write/read pattern after suite capital
has been calculated.

## Validation Evidence

- All 70 orchestration tests pass (`make check`).
- Import-boundary AST test enforces no sibling capital-package imports in
  production source (`test_orchestration_runtime_does_not_import_sibling_packages`).
- End-to-end fixture covers: IMA-eligible path, SA fallback route, SBM + DRC +
  RRAO subtotals, CVA component, deterministic total reconciliation, and stable
  expected-output hash across two independent runs.
- `SuiteCapitalResult.__post_init__` enforces `total_capital == ima + sa + cva`
  to within `rel_tol=1e-12`.
- `make notebooks-check` smoke-tests the orchestration suite aggregation
  teaching notebook.

## Limitations

- `validation_status` remains `PENDING`; no independent model validation has
  been performed against a supervisory or vendor benchmark.
- Suite capital is additive (`IMA + SA + CVA`); multipliers, floors, and the
  60-day look-back required by MAR10.1 are applied in the owning component
  packages before producing their summaries.
- IMA `CapitalRunAuditLog` does not expose `base_currency` or
  `total_market_risk_capital` directly; users must supply these when calling
  `recognise_ima_summary`, or construct `ImaCapitalSummary` directly.
- Orchestration records unsupported and residual branch metadata supplied by
  components; it does not convert those branches into exact Euler
  decomposition when the component marked that method unsupported.

## Arrow Boundary

Orchestration accepts Arrow-backed data at suite input boundaries before data
is routed to component-owned public adapters. Once a component has calculated
capital, orchestration consumes public audited result or summary shapes only
(`ComponentCapitalSummary`, `CvaCapitalSummary`, `ImaCapitalSummary`). It must
not import or coordinate private package batch modules.

IMA scenario cubes remain NumPy-native inside `frtb-ima`; orchestration routes
IMA eligibility and result summaries, not scenario-cube internals. SA component
Arrow input tables are owned by their packages, and orchestration must not
bypass their validation or batch builders.
