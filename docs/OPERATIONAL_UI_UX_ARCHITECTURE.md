# Operational UI/UX Architecture

**Repository:** `AbdulrhmanBashammmakh/utility_erp`
**Reviewed SHA:** `51e8dba5c47ed8ff9d1485b519e1b1586cb30522`
**Documentation Version:** 2.1
**Status:** CURRENT V1 operational contract

## 1. Purpose

The UI exposes the correct business path while the backend remains authoritative. UI restrictions improve usability and reduce mistakes; they do not replace ACLs, record rules, server-side validation, or accounting controls.

## 2. Personas

Administrator, Supervisor, Technician, Meter Reader, Billing User, Accounting User, and Management/Auditor. Visibility and actions should reflect the least privilege required by the underlying mutation.

## 3. UI safety principles

- Business transitions use named action buttons.
- Controlled statusbars are non-clickable and state fields inside forms are readonly.
- Historical financial evidence becomes readonly after approval/application.
- Sensitive or destructive actions are permission-aware and require confirmation where justified.
- Technical fields remain out of routine operational screens.
- Standard Odoo list, form, search, statusbar, smart-button, and chatter patterns are preferred.

## 4. Core navigation

```text
Customer → Meter → Reading → Bill (sale.order) → Accounting Invoice (account.move)
                                             ↘ Payment (account.payment)
                                                  → Allocation/Reconciliation

Meter → Stock/Serial → Installation → Replacement → Reading
                                  ↘ Alarm → Service Order → Work Order
```

Bill, Accounting Invoice, and Payment are distinct concepts and records.

## 5. Reading UX

Reading state is visible and compatible with V1: `draft`, `under_review`, `approved`, `queued`, `billed`, `error`. Billing-owned commercial fields remain in the Billing extension. Review/rejection and correction paths must preserve historical evidence.

## 6. Reading Batch UX

The batch form presents upload metadata, `total_readings`, `processed_count`, `error_count`, `image_count`, and `progress_percent`. The lifecycle statusbar shows `uploaded`, `processing`, `done`, `partial`, and `error`. The list opens with active batches by default and provides a needs-attention filter; terminal history remains discoverable by clearing the filter.

## 7. Operations UX

Service Orders, Work Orders, Installations, and Inspections use named lifecycle actions. Work Order, Installation, Inspection, and Alarm screens expose meaningful terminal/error paths. Alarm operations prioritize open/attention records, critical/emergency filters, today filters, and grouping by state/severity/type/assignee. Operational lists provide useful state, responsible person, date, customer, and type filters.

## 8. Billing UX

The Bill form distinguishes commercial billing from accounting. Smart buttons navigate to Accounting Invoices, Payments, Billing Adjustments, and reading components. Payment registration starts from the bill and carries the selected utility invoice context.

## 9. Write-off UX

```text
draft (editable) → approved (financial/reference fields readonly)
                  → applied (final, Credit Note smart button)
```

The applied message makes the financial finality visible. The statusbar is non-clickable. Billing Manager/Admin role ownership is explained in the form; server-side rules remain authoritative.

## 10. Inventory UX

Meter replacement requires explicit confirmation before immediate execution because it moves stock and changes meter lifecycle using old/new meter and closing/opening reading context. The UI is an operational safety layer over standard stock truth, not a second inventory ledger.

## 11. Search and default filters

Current filters include active/attention Reading Batches, attention and critical/emergency Alarms, scheduled/unsuccessful Inspections, pending/failed Installations, open Work Orders, open Service Orders, and practical date/group-by options. No undocumented filter should be treated as available.

## 12. Smart button policy

Smart buttons are reserved for actual drill-downs: related accounting invoices, payments, adjustments, reading components, Credit Notes, stock movements, and review workspaces. Counts are shown where they materially help daily operations.

## 13. Permission UX

UI groups mirror the sensitivity of the mutation. Sensitive wizards do not grant generic internal-user access; server-side `AccessError` checks protect important actions where implemented. UI hiding is not a security boundary.

## 14. Arabic terminology

Use Customer/Subscriber consistently by business context; Bill = utility commercial `sale.order`; Accounting Invoice = `account.move`; Payment = `account.payment`; Payment Allocation = explicit allocation/reconciliation; Service Order is orchestration, Work Order is field execution; Write-off is الإعفاء/التسوية according to accepted terminology.

## 15. UAT expectations

UAT verifies action-only transitions, readonly final evidence, confirmation on high-impact operations, correct smart-button targets, role-aware visibility, filters that surface operational attention, and Arabic messages. UI success does not imply server-side or runtime proof.

**TARGET / DEFERRED:** richer dashboards, large-scale responsive media delivery, and any UI dependent on future horizontal/Temporal infrastructure.
