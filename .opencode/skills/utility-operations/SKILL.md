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

## Dependent geographic selection

For operational configuration forms, keep related selectors cascading according to the actual model relation: `recurring_rule_type → region → area → zone → route`, `region → area → zone → substation`, and `substation → feeder → transformer → route`; use `utility.subscriber.category → utility.subscriber` where subscriber classification is present. The dropdown domain must filter live choices, an onchange must clear invalid existing children, and a model constraint must reject an incompatible hierarchy or cadence mismatch. This UX rule does not replace authorization checks.

The geographic `utility.region(type='zone')` and `utility.transformer` are distinct representations of the same operational location and must be linked one-to-one through `zone_region_id` and `transformer_origin_id`. Keep the link reciprocal, prevent duplicate use of either record, and preserve both records during migration or deletion workflows.

For an installation or connection, apply the phase compatibility chain: `utility.meter.model.phase → utility.meter`, then `utility.connection.type.phase → subscriber meter`, `utility.transformer.phase → transformer meter`, or `utility.feeder.phase → feeder meter`. Use live domains, onchange cleanup, and server constraints together; a feeder needs an explicit phase and must not be treated as inherently three-phase.

Avoid changing architecture or adding a new operational model for a view-only usability issue.
