---
name: utility-frontend-owl
description: Use when changing Odoo 16 backend JavaScript, OWL components, client actions, field widgets, templates, asset bundles, responsive layouts, scrolling, frontend services, or RTL/Arabic UX in Utility ERP.
---

# Utility Odoo OWL frontend

Use Odoo 16 frontend conventions for the existing Utility ERP components. Keep UI behavior aligned with server-side permissions, workflow actions, API contracts, and the repository's Arabic/RTL requirements.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/OPERATIONAL_UI_UX_ARCHITECTURE.md`
- `docs/SRS.md`
- `docs/UAT_PLAN.md`
- `skills/utility-operations/SKILL.md`
- `skills/utility-security-scope/SKILL.md`
- `skills/odoo-framework-best-practices/SKILL.md`
- Relevant module `__manifest__.py` asset block and existing `static/src/` component/template files

## Current project patterns

- Odoo 16 assets are declared in `web.assets_backend` in module manifests.
- Existing OWL surfaces include the Utility dashboard, barcode camera field, reading review action, image lightbox, rejection dialog, and media image field.
- Preserve `/** @odoo-module **/`, Odoo module imports, registry categories, `standardFieldProps`, and existing template names unless a migration is explicitly required.
- Treat Chart.js and `html5-qrcode` as explicit asset dependencies; do not replace or duplicate vendor libraries casually.

## Rules

- Keep business authorization and state transitions on the server. A hidden button, disabled control, or client-side state is not a security boundary.
- Use `useService("orm")`, `useService("rpc")`, `useService("action")`, `useService("notification")`, and OWL lifecycle hooks consistently with Odoo 16.
- Keep component state local and minimal; cancel or ignore stale async results when filters, dialogs, or actions change context.
- Show loading, empty, error, retry, disabled, and terminal workflow states. Never swallow an exception or report success before the server confirms it.
- Use `_t()` for user-facing strings, Arabic/RTL-friendly layout and keyboard behavior, and accessible labels/focus handling.
- Keep asset order deterministic and update manifest/template registration together. Avoid inline scripts, global variables, direct DOM mutation, and unbounded event listeners.
- Confirm destructive or financial/stock-affecting actions and reflect server responses, not optimistic assumptions. Refresh stale records after mutations where necessary.

## Responsive layout and scrolling

- Design mobile-first with Bootstrap/Odoo utility classes and module SCSS; use breakpoints for toolbar wrapping, card grids, tables, dialogs, and side panels instead of fixed desktop widths.
- In a flex column layout, give the intended scrolling child `min-height: 0`; choose one primary vertical scroll owner and avoid accidental nested scroll containers.
- Keep tables usable on narrow screens with deliberate horizontal overflow, readable headers, stable columns, and a non-scrolling action area where required.
- Use `position: sticky` only with a documented scroll owner and stacking context. Verify dropdowns, modals, popovers, and sticky headers do not clip each other.
- Auto-scroll only when the user is already near the bottom or explicitly requested it. Never yank the viewport while the user is reading older records; expose a translated “new items”/“go to latest” action when needed.
- For paginated or infinite lists, keep server-side limits, stable ordering, deduplication, loading/error/retry states, and an end-of-list state. Preserve the scroll anchor when prepending or replacing data.
- If using `useRef`, `onMounted`, `onPatched`, timers, or `IntersectionObserver`, clean them up in `onWillUnmount` and guard against stale component state.
- Respect `prefers-reduced-motion`; keep smooth scrolling and animated transitions optional, short, and non-essential.

## Interaction and accessibility

- Give dialogs a focus target, keyboard Escape behavior, sensible focus return, visible focus state, and `aria-label`/`aria-live` text where status changes asynchronously.
- Keep touch targets usable on small screens, preserve keyboard navigation, and make icons with actions have text or accessible labels.
- Test Arabic/RTL with long labels, mixed Arabic/Latin identifiers, numeric values, mirrored navigation, and both narrow and wide viewports.

## Frontend performance

- Debounce search and filters, avoid repeated ORM/RPC calls, render bounded pages, lazy-load images, and do not create charts or observers on every patch.
- Destroy Chart.js instances, remove global listeners, clear timers, disconnect observers, and release object URLs when a component unmounts or its data changes.
- Prefer CSS transforms and layout primitives over forced synchronous layout. Measure before optimizing; do not trade correctness or accessibility for a micro-optimization.

## Visual design system

- Use Odoo 16's native backend language and Bootstrap utilities as the base. Borrow Material Design principles—clear hierarchy, semantic color, predictable spacing, elevation, motion, and accessibility—without replacing Odoo's components with a separate design system.
- Define semantic design tokens at the component/module root or SCSS variables: `surface`, `surface-muted`, `text`, `text-muted`, `border`, `primary`, `info`, `success`, `warning`, `danger`, focus ring, radius, shadow, and spacing. Reuse tokens instead of inventing one-off hex values, font sizes, shadows, or radii in templates.
- Prefer Bootstrap/Odoo classes and CSS custom properties where supported. Keep fallbacks for the actual Odoo 16 asset environment; do not assume Bootstrap 5.3-only utilities or color-mode APIs are available.
- Use color semantically and consistently: primary for navigation/normal actions, info for neutral context, success for confirmed/approved, warning for review/attention, danger for rejection/failure, and neutral tones for surfaces and disabled states. Never communicate state by color alone; include text, icon, shape, or status label.
- Check text, icon, border, and focus contrast against their actual background. Target WCAG AA contrast, preserve visible focus, and avoid low-contrast muted text on light cards.
- Keep one typography scale per surface: Cairo (with system fallbacks) for Arabic, a readable body size, a small number of heading sizes, consistent line-height, and at most two weights for normal UI. Do not use font size, bold, or uppercase as the only status signal.
- Use a spacing rhythm based on Bootstrap's rem utilities (prefer `p-*`, `m-*`, `gap-*`, and responsive variants). Align cards, toolbar controls, table cells, and modal sections to the same rhythm; avoid arbitrary inline pixel spacing.
- Keep component geometry consistent: shared button heights, input heights, icon sizes, border radius, border weight, and shadow levels. Use stronger elevation only for dialogs, popovers, and temporary focus—not for every card.
- Establish states for every interactive component: default, hover, focus-visible, active, disabled, loading, success, warning, error, and empty. Each state must remain legible in RTL and narrow layouts.
- Prefer a small documented palette and token names over ad-hoc gradients, excessive shadows, decorative animation, or mixing unrelated visual libraries. Extract existing inline styles into scoped SCSS when the component is materially changed.

## Design validation

- Review each new screen against a known pattern: Odoo control panel/list/form for ERP navigation, Bootstrap grid/forms/tables/modals for layout, and Material-style hierarchy and state feedback for custom dashboards.
- Validate a visual matrix: Arabic and mixed Arabic/Latin content, long labels, large numbers, empty/loading/error/success states, keyboard focus, narrow phone-like width, tablet, desktop, and high zoom.
- Check consistency with neighboring Odoo screens before introducing a new color, font, card treatment, icon family, radius, or interaction pattern.
- Treat screenshots as visual evidence only. Verify behavior, permissions, server state, and responsive interaction separately.

## Workflow

1. Trace the XML template, component/action registration, asset manifest, server method/controller, ACL/record rules, and tests before editing.
2. Define the component contract: props, services, state, events, server response/error shape, lifecycle cleanup, and RTL behavior.
3. Implement the narrowest component change using existing Odoo 16 patterns. Keep backend validation authoritative.
4. Add or update frontend tests when the harness exists; otherwise add focused server/UAT coverage and document unavailable browser evidence.
5. Validate asset loading, template names, action/field registry resolution, loading/error/empty states, keyboard and RTL behavior, duplicate-click/retry behavior, responsive breakpoints, scroll ownership, focus behavior, visual tokens, contrast, and component states.
6. Test at minimum: narrow phone-like width, tablet width, normal desktop, long Arabic text, mixed identifiers, large numbers, high zoom, empty data, slow data, large page, and a user scrolled away from the latest item.
7. Compare the result with adjacent Odoo/Bootstrap patterns, then run focused Odoo module tests and static checks; report runtime browser/device evidence separately from source inspection.

## Do not confuse versions

Do not apply Odoo 17/18 conventions such as changed view syntax or newer OWL APIs to this Odoo 16 project without an explicit migration decision.
