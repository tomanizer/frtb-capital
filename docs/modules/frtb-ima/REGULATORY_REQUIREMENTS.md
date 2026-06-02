# FRTB-IMA Regulatory Requirements

This suite-level page points to the authoritative regulatory requirement
evidence for the implemented `frtb-ima` package.

IMA has executable code, tests, notebooks, and a package-local requirement
registry. The package-local files remain authoritative because tests validate
them directly. SBM, DRC, RRAO, and CVA are sibling packages with their own
requirement evidence; IMA docs should reference them only for package-boundary
and orchestration context.

## Authoritative Evidence

| Evidence | Location |
| --- | --- |
| Requirement registry | [`NPR_2_0_MARKET_RISK.yml`](../../../packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml) |
| Code-to-regulation map | [`REGULATORY_TRACEABILITY.md`](../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md) |
| Regulatory assumptions | [`REGULATORY_ASSUMPTIONS.md`](../../../packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md) |
| Regulatory source manifest | [`regulatory_sources.yml`](../../../packages/frtb-ima/docs/regulatory_sources.yml) |
| Model documentation pack | [`model_documentation/`](model_documentation/README.md) |

## Scope

IMA covers model-eligible desk capital mechanics, including RFET, PLA,
backtesting, expected shortfall, liquidity-horizon adjusted ES, IMCC, NMRF/SES,
and capital assembly. It does not implement SA component fallback capital,
CVA capital, market-data sourcing, or pricing engines.

`frtb-orchestration` owns the handoff between IMA eligibility outputs and the
SA fallback stack.
