# CLAUDE.md — frtb-common

Review `frtb-common` as the suite foundation package.

Reject changes that create dependency cycles, pull model-specific behavior into
shared code prematurely, or add runtime dependencies without an ADR. Shared
types should be small, stable, and neutral across IMA, SBM, DRC, RRAO, CVA, and
orchestration.
