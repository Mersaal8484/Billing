---
name: utility-operations
description: Use for Utility ERP service orders, work orders, inspections, installations, alarms, meter replacement workflows, operational states, and field usability.
---

# Utility operations

Apply this skill to field workflows, operational state machines, buttons, statusbars, and technician or supervisor usability.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/OPERATIONAL_UI_UX_ARCHITECTURE.md`
- `docs/SRS.md`
- `docs/UAT_PLAN.md`

## Workflow rules

1. Inspect the model transition methods and views together; do not secure a workflow only in XML.
2. Make the form state readonly and expose only valid workflow buttons. Disable direct statusbar editing when transitions are guarded.
3. Keep terminal states visible, including `error`, `partial`, `failed`, and `cancelled` where the model supports them.
4. Confirm any action that creates real stock or financial effects and explain the effect in user language.
5. Test valid transitions, invalid transitions, role restrictions, duplicate clicks, and terminal-state visibility.

Avoid changing architecture or adding a new operational model for a view-only usability issue.
