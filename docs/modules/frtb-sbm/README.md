# frtb-sbm

`frtb-sbm` is the Standardised Approach sensitivities-based method package.

## Package Status

- Package directory: `packages/frtb-sbm`
- Import name: `frtb_sbm`
- Implementation status: scaffolded; phase-1 GIRR delta slice in progress (#151)
- Validation status: not started

The package is importable and exposes a public calculation boundary, but
`calculate_sbm_capital` raises an explicit unimplemented-component error until
the cited GIRR delta vertical slice is wired through the public API.

Phase 1 explicitly leaves vega, curvature, CSR, equity, commodity, FX, and
securitisation paths as fail-closed unsupported features.

## Package-Local Documentation

- [Regulatory traceability](../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md)
- [Regulatory assumptions](../../packages/frtb-sbm/docs/REGULATORY_ASSUMPTIONS.md)
- [Regulatory sources manifest](../../packages/frtb-sbm/docs/regulatory_sources.yml)
- [Package README](../../packages/frtb-sbm/README.md)

## Planning Documents

- [Product requirements](PRD.md)
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Detailed requirements](DETAILED_REQUIREMENTS.md)
- [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and plan](DECISIONS_AND_PLAN.md)
- [Issue breakdown](ISSUE_BREAKDOWN.md)
- [Workable requirements](requirements/BASEL_FRTB_SBM.yml)

## Phase-1 Issue Tracker

Parent: [#151](https://github.com/tomanizer/frtb-capital/issues/151)

1. #152 — model documentation and traceability skeleton
2. #153 — canonical data models and validation gates
3. #154 — cited rule profile and GIRR delta reference data
4. #155 — GIRR delta weighted sensitivities
5. #156 — shared intra-bucket aggregation
6. #157 — inter-bucket aggregation and scenario selection
7. #158 — public GIRR delta capital API
8. #159 — audit/replay records and synthetic GIRR fixtures
