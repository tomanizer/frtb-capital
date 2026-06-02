`compose_standardised_approach_capital` now consumes the shared
`frtb_common.ComponentResultHandoff` for each component (`sbm_handoff`,
`drc_handoff`, `rrao_handoff`) and validates the component slot before the
jurisdiction-family guard. The duck-typing `recognise_sbm_result`,
`recognise_drc_result`, and `recognise_rrao_result` helpers are **removed**;
orchestration consumes the typed handoff only. `ComponentResultHandoff` and
`StandardisedComponent` now come from `frtb_common`. See ADR 0029.
