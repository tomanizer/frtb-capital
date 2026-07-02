# FRTB dashboard compatibility shims

The active FRTB Navigator application package lives under
[`packages/frtb-navigator`](../../packages/frtb-navigator). This directory keeps
the old `tools.frtb_dashboard` Python import path and runner as temporary
compatibility shims.

Use the new commands for active development:

```bash
uv run frtb-navigator --port 8766
cd packages/frtb-navigator/frontend && npm install && npm run build
```
