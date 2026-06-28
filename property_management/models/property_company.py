from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    property_currency_id = fields.Many2one('res.currency', string='Default Contract Currency',
        default=lambda self: self.env.company.currency_id.id)
    property_rent_journal_id = fields.Many2one('account.journal', string='Default Rent Journal',
        default=lambda self: self._default_rent_journal())
    property_deposit_journal_id = fields.Many2one('account.journal', string='Default Deposit Journal',
        default=lambda self: self._default_deposit_journal())
    property_maintenance_journal_id = fields.Many2one('account.journal', string='Default Maintenance Journal',
        default=lambda self: self._default_maintenance_journal())
    property_cash_journal_id = fields.Many2one('account.journal', string='Default Cash Journal',
        default=lambda self: self._default_cash_journal())
    property_bank_journal_id = fields.Many2one('account.journal', string='Default Bank Journal',
        default=lambda self: self._default_bank_journal())
    property_receivable_account_id = fields.Many2one('account.account', string='Default Receivable Account',
        default=lambda self: self._default_receivable_account())
    property_rent_income_account_id = fields.Many2one('account.account', string='Default Rent Income Account',
        default=lambda self: self._default_rent_income_account())
    property_service_income_account_id = fields.Many2one('account.account', string='Default Service Income Account',
        default=lambda self: self._default_service_income_account())
    property_deposit_liability_account_id = fields.Many2one('account.account', string='Default Deposit Liability Account',
        default=lambda self: self._default_deposit_liability_account())
    property_advance_liability_account_id = fields.Many2one('account.account', string='Default Advance Liability Account',
        default=lambda self: self._default_advance_liability_account())
    property_maintenance_expense_account_id = fields.Many2one('account.account', string='Default Maintenance Expense Account',
        default=lambda self: self._default_maintenance_expense_account())
    property_cash_account_id = fields.Many2one('account.account', string='Default Cash/Clearing Account',
        default=lambda self: self._default_cash_account())
    property_analytic_plan_id = fields.Many2one('account.analytic.plan', string='Default Analytic Plan',
        default=lambda self: self.env['account.analytic.plan'].search([], limit=1).id)

    def _default_rent_journal(self):
        return self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_deposit_journal(self):
        journals = self.env['account.journal'].search([('type', 'in', ('cash', 'bank')), ('company_id', '=', self.id or self.env.company.id)])
        if journals:
            return journals[0].id
        return self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_maintenance_journal(self):
        return self.env['account.journal'].search([('type', '=', 'purchase'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_cash_journal(self):
        return self.env['account.journal'].search([('type', '=', 'cash'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_bank_journal(self):
        return self.env['account.journal'].search([('type', '=', 'bank'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_receivable_account(self):
        return self.env['account.account'].search([('account_type', '=', 'asset_receivable'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_rent_income_account(self):
        acc = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('name', 'ilike', 'rent'),
            ('company_id', '=', self.id or self.env.company.id)
        ], limit=1)
        if acc:
            return acc.id
        return self.env['account.account'].search([('account_type', '=', 'income'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_service_income_account(self):
        acc = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('name', 'ilike', 'service'),
            ('company_id', '=', self.id or self.env.company.id)
        ], limit=1)
        if acc:
            return acc.id
        return self.env['account.account'].search([('account_type', '=', 'income'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_deposit_liability_account(self):
        acc = self.env['account.account'].search([
            ('account_type', 'in', ('liability_current', 'liability')),
            ('name', 'ilike', 'deposit'),
            ('company_id', '=', self.id or self.env.company.id)
        ], limit=1)
        if acc:
            return acc.id
        return self.env['account.account'].search([('account_type', 'in', ('liability_current', 'liability')), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_advance_liability_account(self):
        acc = self.env['account.account'].search([
            ('account_type', 'in', ('liability_current', 'liability')),
            ('name', 'ilike', 'advance'),
            ('company_id', '=', self.id or self.env.company.id)
        ], limit=1)
        if acc:
            return acc.id
        return self.env['account.account'].search([('account_type', 'in', ('liability_current', 'liability')), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_maintenance_expense_account(self):
        acc = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('name', 'ilike', 'maintenance'),
            ('company_id', '=', self.id or self.env.company.id)
        ], limit=1)
        if acc:
            return acc.id
        return self.env['account.account'].search([('account_type', '=', 'expense'), ('company_id', '=', self.id or self.env.company.id)], limit=1).id

    def _default_cash_account(self):
        acc = self.env['account.account'].search([
            ('account_type', 'in', ('asset_cash', 'asset_current')),
            ('company_id', '=', self.id or self.env.company.id)
        ], limit=1)
        return acc.id

    def action_create_property_custom_accounts(self):
        for company in self:
            def get_or_create_account(name, acc_type, base_code):
                acc = self.env['account.account'].search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
                if acc:
                    return acc.id
                code = base_code
                step = 1
                while self.env['account.account'].search([('code', '=', code), ('company_id', '=', company.id)], limit=1):
                    code = f"{base_code}{step:02d}"
                    step += 1
                acc = self.env['account.account'].create({
                    'name': name,
                    'code': code,
                    'account_type': acc_type,
                    'company_id': company.id,
                })
                return acc.id

            def get_or_create_journal(name, journal_type, base_code):
                journal = self.env['account.journal'].search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
                if journal:
                    return journal.id
                code = base_code[:5]
                step = 1
                while self.env['account.journal'].search([('code', '=', code), ('company_id', '=', company.id)], limit=1):
                    suffix = str(step)
                    code = f"{base_code[:5-len(suffix)]}{suffix}"
                    step += 1
                journal = self.env['account.journal'].create({
                    'name': name,
                    'code': code,
                    'type': journal_type,
                    'company_id': company.id,
                })
                return journal.id

            receivable_id = get_or_create_account("Property Receivable", 'asset_receivable', "12100")
            rent_income_id = get_or_create_account("Property Rent Income", 'income', "41100")
            service_income_id = get_or_create_account("Property Service Income", 'income', "41200")
            deposit_liability_id = get_or_create_account("Property Deposit Liability", 'liability_current', "22100")
            advance_liability_id = get_or_create_account("Property Advance Liability", 'liability_current', "22200")
            maintenance_expense_id = get_or_create_account("Property Maintenance Expense", 'expense', "51100")
            cash_account_id = get_or_create_account("Property Cash/Clearing", 'asset_current', "11100")

            rent_journal_id = get_or_create_journal("Property Rent", 'sale', "PRENT")
            deposit_journal_id = get_or_create_journal("Property Deposit", 'general', "PDEP")
            maintenance_journal_id = get_or_create_journal("Property Maintenance", 'purchase', "PMAI")
            cash_journal_id = get_or_create_journal("Property Cash", 'cash', "PCASH")
            bank_journal_id = get_or_create_journal("Property Bank", 'bank', "PBANK")

            company.write({
                'property_receivable_account_id': receivable_id,
                'property_rent_income_account_id': rent_income_id,
                'property_service_income_account_id': service_income_id,
                'property_deposit_liability_account_id': deposit_liability_id,
                'property_advance_liability_account_id': advance_liability_id,
                'property_maintenance_expense_account_id': maintenance_expense_id,
                'property_cash_account_id': cash_account_id,
                'property_rent_journal_id': rent_journal_id,
                'property_deposit_journal_id': deposit_journal_id,
                'property_maintenance_journal_id': maintenance_journal_id,
                'property_cash_journal_id': cash_journal_id,
                'property_bank_journal_id': bank_journal_id,
            })
