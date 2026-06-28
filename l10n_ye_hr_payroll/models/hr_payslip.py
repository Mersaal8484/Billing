from odoo import api, fields, models, _

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        for slip in self:
            slip._assign_default_salary_rule_accounts()
        return super(HrPayslip, self).action_payslip_done()

    def _assign_default_salary_rule_accounts(self):
        structure = self.env.ref('l10n_ye_hr_payroll.ye_structure_base', raise_if_not_found=False)
        if not structure:
            return

        Account = self.env['account.account']
        company_id = self.company_id.id

        # 1. Search for Expense Account (e.g. Salary Expenses 630000)
        expense_account = Account.search([('code', '=', '630000'), ('company_id', '=', company_id)], limit=1)
        if not expense_account:
            expense_account = Account.search([('account_type', '=', 'expense'), ('company_id', '=', company_id)], limit=1)

        # 2. Search for Payable Account (e.g. Account Payable 211000)
        payable_account = Account.search([('code', '=', '211000'), ('company_id', '=', company_id)], limit=1)
        if not payable_account:
            payable_account = Account.search([('account_type', '=', 'liability_payable'), ('company_id', '=', company_id)], limit=1)

        # 3. Search for Tax Payable Account (e.g. Tax Payable 252000)
        tax_payable_account = Account.search([('code', '=', '252000'), ('company_id', '=', company_id)], limit=1)
        if not tax_payable_account:
            tax_payable_account = Account.search([
                ('account_type', '=', 'liability_current'),
                ('name', 'ilike', 'Tax'),
                ('company_id', '=', company_id)
            ], limit=1)
            if not tax_payable_account:
                tax_payable_account = payable_account

        # 4. Search for Bank Account (e.g. Bank 101404)
        bank_account = Account.search([('code', '=', '101404'), ('company_id', '=', company_id)], limit=1)
        if not bank_account:
            bank_account = Account.search([('account_type', '=', 'asset_cash'), ('company_id', '=', company_id)], limit=1)
            if not bank_account:
                bank_account = Account.search([('account_type', '=', 'asset_current'), ('company_id', '=', company_id)], limit=1)

        # Map accounts to rules
        for rule in structure.rule_ids:
            vals = {}
            
            # Clear accounts for GROSS to prevent double counting
            if rule.code == 'GROSS':
                vals['account_debit'] = False
                vals['account_credit'] = False
            else:
                # 1. Earnings (Positive rules: BASIC, Allowances, OT)
                if rule.code in ['BASIC', 'HOUSING_ALW', 'TRANSPORT_ALW', 'OTHER_ALW', 'OT_DAY', 'OT_NIGHT']:
                    vals['account_debit'] = expense_account.id if expense_account else False
                    vals['account_credit'] = payable_account.id if payable_account else False
                
                # 2. Tax Deduction (Negative rule: TAX)
                # We want: Debit Employee Payable (211000) and Credit Tax Payable (252000)
                # Since amount is negative, debit and credit accounts are swapped:
                elif rule.code == 'TAX':
                    vals['account_debit'] = tax_payable_account.id if tax_payable_account else False
                    vals['account_credit'] = payable_account.id if payable_account else False
                
                # 3. Social Insurance Deduction (Negative rule: EMP_INS)
                # We want: Debit Employee Payable (211000) and Credit Current Liabilities (201000)
                # Swap due to negative amount:
                elif rule.code == 'EMP_INS':
                    # Search for 201000 Current Liabilities
                    liabilities_account = Account.search([('code', '=', '201000'), ('company_id', '=', company_id)], limit=1)
                    if not liabilities_account:
                        liabilities_account = Account.search([('account_type', '=', 'liability_current'), ('company_id', '=', company_id)], limit=1)
                    vals['account_debit'] = liabilities_account.id if liabilities_account else payable_account.id
                    vals['account_credit'] = payable_account.id if payable_account else False
                
                # 4. Unpaid Leave Deduction (Negative rule: UNPAID_DED)
                # We want: Debit Employee Payable (211000) and Credit Salary Expenses (630000)
                # Swap due to negative amount:
                elif rule.code == 'UNPAID_DED':
                    vals['account_debit'] = expense_account.id if expense_account else False
                    vals['account_credit'] = payable_account.id if payable_account else False
                
                # 5. Net Salary Payment (Positive rule: NET)
                # We want: Debit Employee Payable (211000) and Credit Bank (101404)
                elif rule.code == 'NET':
                    vals['account_debit'] = payable_account.id if payable_account else False
                    vals['account_credit'] = bank_account.id if bank_account else False
            
            # Write changes if they are different from current values
            current_debit = rule.account_debit.id if rule.account_debit else False
            current_credit = rule.account_credit.id if rule.account_credit else False
            
            new_debit = vals.get('account_debit', current_debit)
            new_credit = vals.get('account_credit', current_credit)
            
            if new_debit != current_debit or new_credit != current_credit:
                rule.write({
                    'account_debit': new_debit,
                    'account_credit': new_credit
                })
