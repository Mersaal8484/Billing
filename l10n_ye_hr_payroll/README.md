# Yemeni Payroll Localization (l10n_ye_hr_payroll)

Fully compliant Odoo 16 module for **Yemeni Labor Law No. 5 of 1995**, Social Security regulations, and the Yemeni Income Tax (Wage/Salary Tax) law.

---

## Features

### 1. Working Calendars
- **Yemen Standard (48h)**: Saturday–Thursday, 8h/day, Friday off
- **Yemen Admin (40h)**: Sunday–Thursday, 8h/day, Friday–Saturday off
- Auto-linked to contract via Structure Type (YE country detection)

### 2. Work Entry Types
7 work entry types for attendance, overtime, and leave tracking:
| Code | Type | Purpose |
|------|------|---------|
| `WORK100` | Attendance | Standard working hours |
| `OT_DAY` | Overtime | Daylight OT (1.5x) |
| `OT_NIGHT` | Overtime | Nighttime OT (2.0x) |
| `LEAVE100` | Leave | Annual leave |
| `LEAVE110` | Leave | Sick leave |
| `LEAVE90` | Leave | Unpaid leave |
| `LEAVE120` | Leave | Eid holiday |
| `LEAVE125` | Leave | Public holiday |

### 3. Salary Rules (13 Rules)
| # | Code | Description | Sign |
|---|------|-------------|------|
| 1 | `BASIC` | Basic salary from `contract.wage` | + |
| 2 | `HOUSING_ALW` | Housing allowance (fixed, insured) | + |
| 3 | `TRANSPORT_ALW` | Transport allowance (fixed, insured) | + |
| 4 | `OTHER_ALW` | Variable allowance (non-insured) | + |
| 5 | `OT_DAY` | Daylight overtime at 1.5x hourly rate | + |
| 6 | `OT_NIGHT` | Nighttime overtime at 2.0x hourly rate | + |
| 7 | `GROSS` | Gross = BASIC + ALW | + |
| 8 | `EMP_INS` | Employee social insurance 6% (with min/max caps) | – |
| 9 | `TAX` | Progressive income tax (0%/10%/15%/20%) | – |
| 10 | `UNPAID_DED` | Unpaid leave deduction | – |
| 11 | `NET` | Net salary payable | + |
| 12 | `COMPANY_INS` | Employer social insurance 9% (accounting only) | + |
| 13 | `EOS_PROV` | End-of-Service provision accrual (accounting only) | + |

### 4. Social Insurance (Configurable)
- Employee rate (default 6%) and Employer rate (default 9%)
- Configurable **minimum base** and **maximum base** caps
- Insurable base = Basic + Housing Allowance + Transport Allowance
- Accounts configurable per company (Settings → Payroll)

### 5. Progressive Income Tax
- Configurable via dedicated `ye.tax.bracket` model
- Default brackets (Yemeni law):
  - 0% on first 10,000 YER (exempt)
  - 10% on 10,001 – 30,000 YER
  - 15% on 30,001 – 60,000 YER
  - 20% on amounts above 60,000 YER
- Tax = Gross – Statutory Exemption – Employee Insurance

### 6. End-of-Service Provision (EOS)
- Configurable formula via `ye.eos.rule` model
- Default: 1 month salary per year of service (accrued monthly as `wage / 12`)
- Accounting-only (no impact on net pay)

### 7. Global Time Offs (Fixed Holidays)
Pre-loaded national holidays:
- May 1 (Labor Day)
- May 22 (Unity Day)
- September 26 (Revolution Day)
- October 14 (Revolution Day)
- November 30 (Independence Day)

> **Note**: Lunar Eid holidays (Eid al-Fitr, Eid al-Adha) must be added annually by the HR Manager via *Technical → Resource → Calendar Leaves*.

### 8. Annual Leave Accrual (30 days/year)
Functional setup guide included for accruing 2.5 days/month via Odoo's Accrual Plan system.

### 9. Full Accounting Integration
- Payslip journal entries with configurable debit/credit accounts per rule
- Contribution registers for Social Insurance Authority and Tax Authority
- Accounting-only rules for employer costs (COMPANY_INS, EOS_PROV)

---

## Dependencies

| Module | Purpose |
|--------|---------|
| `om_hr_payroll` | Odoo 16 HR Payroll (Community) |
| `om_hr_payroll_account` | HR Payroll Accounting |
| `hr_contract` | Employee contracts |
| `hr_work_entry_contract` | Work entry generation |
| `hr_holidays` | Leave management |

---

## Installation

```bash
python odoo-bin -i l10n_ye_hr_payroll -d <database_name> \
  --addons-path=addons,custom_addons
```

Or via Odoo UI: **Apps → Search "Yemeni Payroll Localization" → Install**

---

## Post-Install Configuration

### Step 1: Accounting Accounts
Go to **Payroll → Configuration → Settings** and configure:
- Social Insurance Payable Account
- Social Insurance Expense Account
- Tax Payable Account
- EOS Provision Liability Account
- EOS Expense Account
- Insurance rate, caps, exemption amount

### Step 2: Tax Brackets
Go to **Payroll → Configuration → Yemeni Tax Brackets** → Review/modify the 4 default brackets.

### Step 3: EOS Rules
Go to **Payroll → Configuration → EOS Provision Rules** → Define formulas (default: 1 month/year).

### Step 4: Salary Rule Accounts
Go to **Payroll → Configuration → Salary Rules** → For each rule, set the Accounting tab:
- **BASIC, HOUSING_ALW, TRANSPORT_ALW, OTHER_ALW, OT_DAY, OT_NIGHT, GROSS, NET**: Debit = Salary Expense → Credit = Employee Payable
- **EMP_INS**: Debit = Employee Payable → Credit = Insurance Payable
- **TAX**: Debit = Employee Payable → Credit = Tax Payable
- **UNPAID_DED**: Debit = Employee Payable → Credit = Salary Expense (reversal)
- **COMPANY_INS**: Debit = Insurance Expense → Credit = Insurance Payable
- **EOS_PROV**: Debit = EOS Expense → Credit = EOS Provision Liability

### Step 5: Accrual Plan
Go to **Employees → Configuration → Time Off → Accrual Plans**:
- Create plan "Annual Leave (2.5 days/month)" → Level: 2.5 days, Monthly frequency
- Assign to employees via allocation (type = Accrual)

### Step 6: Employee Contracts
Open each contract and set: allowances, social insurance number, EOS rule.

---

## Testing Scenarios

| Scenario | Wage | Allowances | OT | Unpaid | Expected Net |
|----------|------|-----------|----|--------|-------------|
| A (Low) | 9,000 | 0 | 0 | 0 | 9,000 (no tax, no insurance) |
| B (Mid) | 25,000 | 5,000 | 10h day | 0 | Compute insurance on 30k, tax on (30k - 10k - 1.8k) = 18.2k × 10% = 1,820 |
| C (High) | 80,000 | 15,000 | 0 | 2 days | Insurance on 95k (max capped), tax at 20% above 50k |

---

## Module Statistics
- **22 files**, ~1,004 lines of code
- **13 salary rules** with production Python compute
- **2 calendar templates**
- **7 work entry types**
- **5 global holidays**
- **5 model extensions** (hr_contract, res_company, res_config_settings, ye_tax_bracket, ye_eos_rule)

---

## License
LGPL-3
