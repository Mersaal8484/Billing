---
name: utility-release-gate
description: Use for Utility ERP static gate reviews, runtime evidence, UAT readiness, release traceability, P0/P1/P2 classification, and go-live decisions.
---

# Utility release gate

Apply this skill to release reviews and evidence reports. Separate verified facts from recommendations and deferred debt.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/ARCHITECTURE_DECISION_LOG.md`
- `docs/UAT_PLAN.md`
- `docs/GO_LIVE_RUNBOOK.md`
- `docs/RELEASE_TRACEABILITY_MATRIX.md`

## Gate discipline

- Keep four evidence classes separate: Static Evidence, Runtime Evidence, UAT Evidence, and Load/Profiling Evidence. CI status is reported alongside them, not substituted for them.
- Do not claim a gate passes from a test file, a UI button, or an empty CI status alone.
- Treat `statuses: []` as missing runtime/CI proof, never as passing evidence.
- Classify findings as P0, P1, P2, or P3 with a precise scope and evidence path.
- Treat performance findings such as N+1 as debt until profiling establishes production impact.
- Keep release blockers separate from optional cleanup and architecture proposals.

## Workflow

1. Establish the exact HEAD and baseline being reviewed.
2. Inspect the changed-file scope, source-of-truth boundaries, security, accounting, inventory, APIs, workflows, and UX.
3. Run proportional static checks and focused tests; record unavailable runtime or CI evidence explicitly.
4. Update traceability and produce a concise verdict with remaining risks, owners, and next gate.
