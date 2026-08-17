# OPENCODE.md — Utility ERP execution & skill routing for OpenCode

This repository uses `AGENTS.md` and `skills/` as the canonical routing and skill execution system for OpenCode agents.

Important:
- `skills/` is authoritative.
- `.opencode/skills/` is a generated tool-compatibility mirror and must never contain independent business rules.

Please refer to:
- [AGENTS.md](AGENTS.md) for source-of-truth hierarchy, routing tables, and engineering guardrails.
- `skills/<skill-name>/SKILL.md` (or `.opencode/skills/<skill-name>/SKILL.md`) for domain-specific execution discipline.
- `docs/DOCUMENT_INDEX.md` as the canonical documentation entry point.
