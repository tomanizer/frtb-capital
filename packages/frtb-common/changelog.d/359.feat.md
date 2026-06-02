Add the shared `ComponentResultHandoff` standardised-component orchestration
handoff contract, with `StandardisedComponent` and `ComponentHandoffError`.
Each SA component projects its result onto this neutral, validated shape so
orchestration never couples to component-internal result fields. See ADR 0029.
