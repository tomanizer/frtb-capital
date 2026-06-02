# frtb-sbm decisions and implementation plan

This document records the original implementation sequencing decisions for
SBM. Some early-slice implications below are intentionally historical. The
current supported BASEL_MAR21 delta, vega, and curvature matrix is maintained
in
[`packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`](../../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md).

## Decision log

### SBM-DEC-001: Start with a thin delta vertical slice

**Decision:** The first capital-producing slice should implement one shared
delta path, ideally GIRR delta first and FX delta if it falls out naturally from
the same aggregation engine.

**Reason:** Delta exercises canonical inputs, profile lookup, weighted
sensitivities, intra-bucket aggregation, inter-bucket aggregation, scenario
selection, audit hashing, and the public API without forcing curvature-specific
contracts too early.

**Implication:** Vega and curvature stay explicitly unsupported until their
canonical contracts and fixtures land.

### SBM-DEC-002: Keep canonical SBM contracts package-local initially

**Decision:** `SbmSensitivity`, `SbmRuleProfile`, and SBM-specific result types
should start in `frtb_sbm.data_models`.

**Reason:** `frtb-common` should not absorb SBM-specific buckets, qualifiers,
scenario records, or curvature structures before the package proves which parts
are truly cross-cutting.

**Implication:** Only clearly shared primitives should move to `frtb-common`
under a separate cross-package decision.

### SBM-DEC-003: Profiles own all rule-driven parameters

**Decision:** Risk weights, bucket definitions, tenor sets, liquidity horizons,
correlations, scenario labels, and support flags belong in versioned rule
profiles and reference-data helpers.

**Reason:** This keeps citations and reproducibility separate from numeric code
and aligns with the repository's rule-profile direction.

**Implication:** Calculation kernels receive typed values and must not branch on
hard-coded regulator names.

### SBM-DEC-004: Shared aggregation before broad risk-class rollout

**Decision:** Weighted sensitivity, intra-bucket aggregation, inter-bucket
aggregation, and scenario selection should be reusable primitives, not copied
per risk class.

**Reason:** GIRR, FX, equity, commodity, and CSR all depend on the same high
level SBM mechanics even when their lookup tables differ.

**Implication:** Risk-class modules should assemble inputs and choose tables, but
not re-implement the core quadratic aggregation flow.

### SBM-DEC-005: Curvature is a distinct later path

**Decision:** Curvature should be implemented after the shared delta/vega engine
and should keep its own canonical contract and aggregation path.

**Reason:** Curvature needs up/down shock inputs, branch selection, and specific
floors that should not be obscured by trying to fit it into delta or vega
shapes.

**Implication:** The first public capital slice may exclude curvature, but it
must leave room in data models and results for curvature-specific records.

### SBM-DEC-006: Fail closed for incomplete CSR securitisation support

**Decision:** CSR securitisation non-CTP and CSR securitisation CTP should exist
only as explicit unsupported gates until cited mappings, qualifiers, and
fixtures are complete.

**Reason:** These paths have additional bucket and qualifier complexity. Partial
support would violate the package's no-placeholder-capital rule.

**Implication:** Tests must assert precise unsupported errors for these paths in
early slices.

### SBM-DEC-007: Audit graph before orchestration handoff

**Decision:** The first successful `SbmCapitalResult` should already include
stable ids, profile and input hashes, scenario metadata, and reconciliation
records before orchestration consumes it.

**Reason:** Orchestration should depend only on typed, auditable package results,
not on ad hoc internal structures.

**Implication:** Audit and replay are part of the first end-to-end slice, not a
later documentation-only enhancement.

### SBM-DEC-008: Adapters follow the canonical runtime

**Decision:** CRIF and CSV adapter work should come after canonical models,
validation, rule-profile lookup, and the first capital slice are stable.

**Reason:** Adapter design is easier once the runtime contract is frozen. It
also prevents adapter-specific conventions from leaking into the capital kernel.

**Implication:** Early implementation work should use synthetic canonical
fixtures, not adapter-driven test inputs.

## Implementation sequence

1. Keep the existing scaffold entry point failing explicitly until supported
   capital slices land.
2. Add the SBM documentation pack and traceability skeleton.
3. Implement canonical data models and validation errors.
4. Implement rule-profile identity, cited reference data, and deterministic
   profile hashing.
5. Implement weighted sensitivity and vega-scaling helpers.
6. Implement shared intra-bucket and inter-bucket aggregation with scenario
   selection.
7. Deliver the first GIRR delta vertical slice through the public API.
8. Extend the shared engine to FX delta if the same primitives already cover it.
9. Add audit/replay records and deterministic synthetic fixture packs.
10. Add equity and commodity delta/vega support.
11. Add CSR non-securitisation support.
12. Add curvature-specific contracts and capital path.
13. Add CSR securitisation non-CTP and CTP once cited mappings are complete.
14. Add optional CRIF adapters and mapping warnings.
15. Add orchestration handoff, attribution, impact assessment, and performance
    controls.

## Documentation deliverables

Each implementation slice should keep these documents aligned:

- `docs/modules/frtb-sbm/DETAILED_REQUIREMENTS.md`;
- `docs/modules/frtb-sbm/REGULATORY_REQUIREMENTS.md`;
- `docs/modules/frtb-sbm/ARCHITECTURE_AND_DATA_DESIGN.md`;
- `docs/modules/frtb-sbm/DECISIONS_AND_PLAN.md`;
- `docs/modules/frtb-sbm/ISSUE_BREAKDOWN.md`;
- `docs/modules/frtb-sbm/README.md`;
- `requirements/BASEL_FRTB_SBM.yml` and any package-local regulatory
  traceability once calculation modules exist.

## First vertical slice target

The first useful release of `frtb-sbm` should be a cited GIRR delta slice with:

- canonical `SbmSensitivity` validation;
- one selected rule profile with cited GIRR buckets, tenors, risk weights, and
  correlations needed by fixtures;
- weighted sensitivity calculation;
- intra-bucket aggregation;
- inter-bucket aggregation across low/medium/high scenarios;
- frozen `SbmCapitalResult` with input and profile hashes;
- explicit unsupported behavior for vega, curvature, and non-GIRR risk classes.

If the shared engine covers FX delta cleanly, FX can join the first slice, but
GIRR remains the minimum target.

## Open design questions

1. Should `SbmRuleProfile` remain package-local for v1 or move to
   `frtb-common` before DRC and RRAO converge on a shared profile contract?
2. Should canonical tenor fields use string enums, structured tenor objects, or
   both?
3. What is the smallest cited risk-weight and correlation table subset that can
   support the first GIRR fixture without creating rework?
4. Should vega scaling live in `weighted_sensitivity.py` or a smaller dedicated
   helper module?
5. What benchmark size is useful enough for the first shared aggregation engine
   without overfitting to synthetic data shape?

These are real design questions, but they should not block the first
canonical-model and delta-slice issues.
