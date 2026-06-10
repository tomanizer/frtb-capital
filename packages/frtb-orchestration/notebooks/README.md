# frtb-orchestration notebooks

These notebooks teach the suite-level integration contract for synthetic engineering and validation evidence. They are not final regulatory capital, regulatory submissions, legal opinions, or supervisory approvals.

## Notebook index

| Notebook | Purpose | Public contracts |
| --- | --- | --- |
| [00_suite_aggregation.ipynb](00_suite_aggregation.ipynb) | Compose Standardised Approach capital from component summaries, aggregate IMA + SA + CVA, build a suite attribution report, and show jurisdiction mismatch rejection. | `ComponentCapitalSummary`, `ImaCapitalSummary`, `CvaCapitalSummary`, `compose_standardised_approach_capital`, `calculate_suite_capital`, `build_suite_attribution_report` |

## Raw inputs your upstream must emit

For the summary handoff path, orchestration expects public component outputs that have already passed package-owned validation:

- `frtb_common.ComponentCapitalSummary` for SBM, DRC, and RRAO;
- `frtb_orchestration.ImaCapitalSummary` for IMA;
- `frtb_orchestration.CvaCapitalSummary` for CVA;
- `frtb_common.contribution_bundle.ComponentContributionBundle` for attribution handoff.

For Arrow ingress before component calculation, use `CapitalRunManifest` and `run_standardised_approach_from_manifest`; the component packages still own validation of their table schemas.

## Run

From the repository root:

```bash
MPLBACKEND=Agg IPYTHONDIR=$PWD/.pytest_cache/ipython uv run --with pytest,nbmake --directory packages/frtb-orchestration pytest --nbmake notebooks
```

The root `make notebooks-check` target includes this smoke test.

## See Also

- [Package README](../README.md)
- [Suite module README](../../../docs/modules/frtb-orchestration/README.md)
- [Public API](../../../docs/modules/frtb-orchestration/PUBLIC_API.md)
- [Client integration guide](../../../docs/CLIENT_INTEGRATION.md)
- [Visuals and diagrams guidance](../../../docs/visuals.md)
