# Capital Navigator specification guide

The Capital Navigator docs are split into one product north star and focused
implementation contracts. Read them in this order when planning or reviewing
dashboard work.

## Reading Order

| Step | Document | Use for |
| --- | --- | --- |
| 1 | [`UX_AUDIT_AND_INTERACTION_CONTRACT.md`](UX_AUDIT_AND_INTERACTION_CONTRACT.md) | Product goals, analyst workflows, interaction principles, modes, and screen anatomy. |
| 2 | [`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md) | Binding `NavigatorState`, URL, cache-key, reset, loading, cancellation, and stale-evidence rules. |
| 3 | [`RESULT_STORE_DATA_CONTRACT.md`](RESULT_STORE_DATA_CONTRACT.md) | Browser/adapter boundary over `frtb-result-store`, endpoint and mart mapping, IDs, artifacts, and no-data states. |
| 4 | [`CAPITAL_AND_MOVEMENT_SEMANTICS.md`](CAPITAL_AND_MOVEMENT_SEMANTICS.md) | Capital, hierarchy, movement, attribution, display-only subtotal, and unavailable-state semantics. |
| 5 | [`MODE_WIREFRAMES.md`](MODE_WIREFRAMES.md) | Buildable low-fidelity shell, mode, inspector, pivot, and AI drawer screen anatomy. |
| 6 | [`IMPLEMENTATION_SLICES.md`](IMPLEMENTATION_SLICES.md) | PR-sized delivery sequence, dependencies, likely files, fixture needs, tests, validation, and non-goals. |
| 7 | [`AI_EXPLANATION_CONTRACT.md`](AI_EXPLANATION_CONTRACT.md) | Governed AI explanation trigger points, request/response schema, snapshot dependency, evidence refs, redaction, caching, and refusal tests. |

## Ownership

- The UX contract remains the product north star. It should describe why the
  Navigator exists, which workflows matter, and how the experience should feel.
- Companion specs are binding for implementation details. Do not duplicate their
  full schemas or tables in the UX contract.
- Runtime dashboard features and result-store API changes are outside this spec
  split. Implementation work should follow
  [`IMPLEMENTATION_SLICES.md`](IMPLEMENTATION_SLICES.md).

## Related Issues

- Split epic: #1106
- Result-store delivery epic: #1105
- State/routing spec: #1107
- Result-store data contract: #1108
- Capital and movement semantics: #1109
- Mode wireframes: #1110
- Implementation slices: #1111
- Governed AI explanation contract: #1112
- Index and UX cleanup: #1113
