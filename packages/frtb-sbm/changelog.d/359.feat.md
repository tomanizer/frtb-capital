`to_orchestration_handoff` now returns the shared
`frtb_common.ComponentResultHandoff` instead of the package-local
`SbmOrchestrationHandoff`, which is removed. The adapter is now exported from
the package's public API. See ADR 0029.
