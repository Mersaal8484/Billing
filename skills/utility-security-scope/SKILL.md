---
name: utility-security-scope
description: Use for Utility ERP groups, ACLs, record rules, user scope, region and area isolation, API ownership checks, sudo boundaries, and security regression review.
---

# Utility security scope

Apply this skill to security changes or reviews. Read the current implementation before designing rules.

## Read first

- `docs/DOCUMENT_INDEX.md`
- `docs/CURRENT_V1_IMPLEMENTATION_BASELINE.md`
- `docs/ARCHITECTURE_DECISION_LOG.md`
- `docs/ORGANIZATIONAL_SECURITY_AND_DATA_ISOLATION.md`
- `docs/SECURITY_MATRIX.md`
- `docs/SRS.md` and `docs/UAT_PLAN.md` when the workflow is user-facing

## Non-negotiable model

- Role-based access comes first; geographic data scope is a separate layer.
- In `utility.region`, `type='region'` is Region, `type='area'` is the organizational Branch, and `type='zone'` is a lower zone. Do not invent a separate branch model or a security group per geography.
- Effective access is `Role Permissions ∩ Company Scope ∩ Organizational Scope`.
- A user with an empty restricted assignment must not receive unrestricted access by accident.
- UI visibility is usability only; ACLs, record rules, and server-side checks are the boundary.
- Do not use broad accounting record rules that break invoice, payment, or reconciliation usability.

## Workflow

1. Audit groups, ACLs, record rules, `res.users` assignments, and every relevant `sudo()` path.
2. Define the mutation and read scope separately, including API ownership and company scope.
3. Enforce sensitive workflow actions server-side and keep UI restrictions aligned.
4. Add negative and positive permission tests, including empty-scope behavior and cross-area denial.
5. Report any incomplete organizational isolation as a documented gap, not as a passing security claim.
