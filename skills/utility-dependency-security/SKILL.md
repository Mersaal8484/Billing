---
name: utility-dependency-security
description: Use when changing, reviewing, installing, upgrading, or troubleshooting Python/Odoo or Dart/Flutter dependencies, lockfiles, build tooling, secrets, package sources, or supply-chain controls.
---

# Utility dependency security

Audit dependency and build changes without treating a scanner result as a complete security review. This skill is adapted from open-source AppSec workflows and is deliberately read-only by default.

## Read first

- `AGENTS.md`
- `requirements.txt`
- `mobile/meter_reading_app/pubspec.yaml`
- `mobile/meter_reading_app/pubspec.lock`
- Relevant Odoo `__manifest__.py` files
- CI, Docker, deployment, and secret-management files when present

## Rules

- Do not install packages, run arbitrary post-install scripts, or change lockfiles merely to investigate a dependency. Ask for approval before networked installation or remediation.
- Prefer pinned or bounded versions, trusted registries, lockfile review, license compatibility, and reproducible builds. Flag unexpected source URLs, git dependencies, local path overrides, typosquatting signals, and unexplained transitive changes.
- Scan Python and Dart ecosystems with an approved tool when available (`pip-audit`, OSV tooling, or the ecosystem's native audit command); record tool version, database date, scope, and unavailable checks.
- Never put credentials in requirements, `pubspec`, CI logs, sample configuration, mobile assets, or generated reports.
- Separate vulnerable direct dependencies, vulnerable transitive dependencies, reachability, exploitability, and remediation urgency. Do not upgrade a financial or Odoo core dependency without compatibility tests.

## Workflow

1. Compare the dependency diff with the last trusted revision and identify who owns each package and runtime surface.
2. Inspect package metadata, hashes or lockfile entries, release provenance, licenses, and supported Python/Dart/Odoo versions.
3. Run bounded offline or approved audit commands, then manually inspect high-impact packages used by authentication, HTTP, media, SQLite/Drift, payments, or build/release tooling.
4. Check secrets, CI permissions, artifact provenance, and post-install/build hooks for exfiltration or persistence risk.
5. Produce findings with package, version, evidence, affected path, exploitability, compatibility impact, and safe remediation options.
6. Validate any approved upgrade with focused Odoo tests or Flutter analysis/tests before declaring the dependency change safe.
