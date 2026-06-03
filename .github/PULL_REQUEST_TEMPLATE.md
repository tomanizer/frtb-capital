## Summary

- 

## Closes

<!-- List every issue closed by this PR. GitHub only closes issues named here,
     not checkboxes inside a parent issue body. When closing a parent/phase
     issue, list every delivered sub-issue explicitly:
     Closes #N, #N, #N
     Closes #N  (parent) -->

## Affected Packages

- [ ] Suite-only documentation/governance
- [ ] `packages/frtb-ima`
- [ ] `packages/frtb-sbm`
- [ ] `packages/frtb-drc`
- [ ] `packages/frtb-rrao`
- [ ] `packages/frtb-cva`
- [ ] `packages/frtb-orchestration`
- [ ] `packages/frtb-common`

## Wrapper / Adapter / Facade Review

- [ ] This PR does not add wrappers, adapters, facades, or pass-through helper layers.
- [ ] This PR adds wrappers, adapters, facades, or pass-through helper layers and explains the protected contract boundary below.

Protected contract boundary:

<!-- If the second box is checked, name the caller/callee boundary, external
     API boundary, IO/handoff boundary, or compatibility boundary that makes the
     wrapper necessary. If no boundary exists, remove the wrapper. -->

## Public API Review

- [ ] This PR does not add, remove, or change public exports or documented public entrypoints.
- [ ] This PR adds, removes, or changes public exports or documented public entrypoints and includes tests/docs for the public contract.

Public API changes:

<!-- Name changed top-level imports, calculation entrypoints, documented public
     functions/classes, and compatibility impact. If there is no external
     consumer contract, keep the symbol private. -->

## Material Change Review

- [ ] I checked [ADR 0005](docs/decisions/0005-material-change-policy.md) and this PR is not material.
- [ ] This PR is material and links the required ADR below.

ADR:

Numerical formula, regulatory threshold, policy default, fixture output, model
boundary, public API, or audit-record semantic changes require ADR review before
merge.

## Verification

- [ ] `make check`
- [ ] Other:
