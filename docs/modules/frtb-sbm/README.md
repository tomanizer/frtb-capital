# frtb-sbm

`frtb-sbm` is the Standardised Approach sensitivities-based method package.

## Package Status

- Package directory: `packages/frtb-sbm`
- Import name: `frtb_sbm`
- Implementation status: partial runtime — BASEL_MAR21 delta, vega, and
  curvature paths implemented under audit across all seven SBM risk classes
- Validation status: deterministic fixture, audit, replay, and public API tests available

The package is importable and exposes `calculate_sbm_capital` for supported
Basel MAR21 delta, vega, and curvature canonical inputs. Row-wise,
package-owned batch, and Arrow handoff paths are available for the supported
matrix. Unsupported profiles and unmapped sub-features fail closed.

## Package-Local Documentation

- [Regulatory traceability](../../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md)
- [Regulatory assumptions](../../../packages/frtb-sbm/docs/REGULATORY_ASSUMPTIONS.md)
- [Regulatory sources manifest](../../../packages/frtb-sbm/docs/regulatory_sources.yml)
- [Package README](../../../packages/frtb-sbm/README.md)

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

Follow-on issues #160, #161, #166, #169, #226, #244, and the later
vectorisation sprint are reconciled in the support matrix and closed-issue audit
inside
[`packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`](../../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md).
