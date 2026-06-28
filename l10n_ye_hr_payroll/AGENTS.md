# Repository Guidelines

## Project Structure & Module Organization
This repository is a single Odoo addon named `l10n_ye_hr_payroll`.

- `__manifest__.py`: addon metadata and dependency list.
- `models/`: Python models and business logic, split by feature (`hr_contract.py`, `ye_tax_bracket.py`, etc.).
- `data/`: XML records loaded on install, including payroll rules, calendars, leave types, and tax brackets.
- `views/`: XML UI definitions for contracts, settings, and configuration models.
- `security/`: access control rules in `ir.model.access.csv`.
- `static/`: frontend assets if they are added later.

## Build, Test, and Development Commands
There is no local build system in this repo; development is done through Odoo.

- `python odoo-bin -d <db> -i l10n_ye_hr_payroll --addons-path=...` installs the module into a database.
- `python odoo-bin -d <db> -u l10n_ye_hr_payroll --addons-path=...` upgrades the module after changes.
- `python odoo-bin -d <db> --test-enable -u l10n_ye_hr_payroll --addons-path=...` runs Odoo tests when test cases exist.

## Coding Style & Naming Conventions
Follow standard Odoo conventions and PEP 8 for Python.

- Use 4-space indentation in Python files.
- Keep model filenames and XML IDs in `snake_case`.
- Name XML records and external IDs descriptively, for example `ye_tax_bracket_default`.
- Keep view inheritance and data files small and feature-focused.

## Testing Guidelines
No automated tests are currently present. When adding them, place Odoo test cases under a dedicated `tests/` directory and name files clearly, such as `test_hr_contract.py`.

Validate changes by upgrading the module and checking the affected payroll flows in Odoo, especially contract computation, leave deductions, tax brackets, and EOS rules.

## Commit & Pull Request Guidelines
No git history is available in this workspace, so no project-specific commit pattern can be confirmed. Use short imperative commits such as `Add EOS rule validation`.

Pull requests should include:

- a concise description of the functional change,
- the affected Odoo version and module scope,
- screenshots for view changes,
- notes about any data updates or upgrade steps.

## Configuration Notes
This addon depends on `hr_contract`, `hr_work_entry_contract`, `om_hr_payroll`, `om_hr_payroll_account`, and `hr_holidays`. Verify those modules are installed before testing payroll behavior.
