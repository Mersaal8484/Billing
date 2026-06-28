from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def default_get(self, fields_list):
        res = super(ResConfigSettings, self).default_get(fields_list)
        company = self.env.company
        
        if 'property_currency_id' in fields_list and not res.get('property_currency_id'):
            res['property_currency_id'] = company.property_currency_id.id or company.currency_id.id
            
        if 'property_rent_journal_id' in fields_list and not res.get('property_rent_journal_id'):
            if not company.property_rent_journal_id:
                journal = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
                res['property_rent_journal_id'] = journal.id
                
        if 'property_deposit_journal_id' in fields_list and not res.get('property_deposit_journal_id'):
            if not company.property_deposit_journal_id:
                journal = self.env['account.journal'].search([('type', 'in', ('cash', 'bank')), ('company_id', '=', company.id)], limit=1)
                if not journal:
                    journal = self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
                res['property_deposit_journal_id'] = journal.id
                
        if 'property_maintenance_journal_id' in fields_list and not res.get('property_maintenance_journal_id'):
            if not company.property_maintenance_journal_id:
                journal = self.env['account.journal'].search([('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
                res['property_maintenance_journal_id'] = journal.id
                
        if 'property_cash_journal_id' in fields_list and not res.get('property_cash_journal_id'):
            if not company.property_cash_journal_id:
                journal = self.env['account.journal'].search([('type', '=', 'cash'), ('company_id', '=', company.id)], limit=1)
                res['property_cash_journal_id'] = journal.id
                
        if 'property_bank_journal_id' in fields_list and not res.get('property_bank_journal_id'):
            if not company.property_bank_journal_id:
                journal = self.env['account.journal'].search([('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1)
                res['property_bank_journal_id'] = journal.id
                
        if 'property_receivable_account_id' in fields_list and not res.get('property_receivable_account_id'):
            if not company.property_receivable_account_id:
                account = self.env['account.account'].search([('account_type', '=', 'asset_receivable'), ('company_id', '=', company.id)], limit=1)
                res['property_receivable_account_id'] = account.id
                
        if 'property_rent_income_account_id' in fields_list and not res.get('property_rent_income_account_id'):
            if not company.property_rent_income_account_id:
                account = self.env['account.account'].search([('account_type', '=', 'income'), ('name', 'ilike', 'rent'), ('company_id', '=', company.id)], limit=1)
                if not account:
                    account = self.env['account.account'].search([('account_type', '=', 'income'), ('company_id', '=', company.id)], limit=1)
                res['property_rent_income_account_id'] = account.id
                
        if 'property_service_income_account_id' in fields_list and not res.get('property_service_income_account_id'):
            if not company.property_service_income_account_id:
                account = self.env['account.account'].search([('account_type', '=', 'income'), ('name', 'ilike', 'service'), ('company_id', '=', company.id)], limit=1)
                if not account:
                    account = self.env['account.account'].search([('account_type', '=', 'income'), ('company_id', '=', company.id)], limit=1)
                res['property_service_income_account_id'] = account.id
                
        if 'property_deposit_liability_account_id' in fields_list and not res.get('property_deposit_liability_account_id'):
            if not company.property_deposit_liability_account_id:
                account = self.env['account.account'].search([('account_type', 'in', ('liability_current', 'liability')), ('name', 'ilike', 'deposit'), ('company_id', '=', company.id)], limit=1)
                if not account:
                    account = self.env['account.account'].search([('account_type', 'in', ('liability_current', 'liability')), ('company_id', '=', company.id)], limit=1)
                res['property_deposit_liability_account_id'] = account.id
                
        if 'property_advance_liability_account_id' in fields_list and not res.get('property_advance_liability_account_id'):
            if not company.property_advance_liability_account_id:
                account = self.env['account.account'].search([('account_type', 'in', ('liability_current', 'liability')), ('name', 'ilike', 'advance'), ('company_id', '=', company.id)], limit=1)
                if not account:
                    account = self.env['account.account'].search([('account_type', 'in', ('liability_current', 'liability')), ('company_id', '=', company.id)], limit=1)
                res['property_advance_liability_account_id'] = account.id
                
        if 'property_maintenance_expense_account_id' in fields_list and not res.get('property_maintenance_expense_account_id'):
            if not company.property_maintenance_expense_account_id:
                account = self.env['account.account'].search([('account_type', '=', 'expense'), ('name', 'ilike', 'maintenance'), ('company_id', '=', company.id)], limit=1)
                if not account:
                    account = self.env['account.account'].search([('account_type', '=', 'expense'), ('company_id', '=', company.id)], limit=1)
                res['property_maintenance_expense_account_id'] = account.id
                
        if 'property_cash_account_id' in fields_list and not res.get('property_cash_account_id'):
            if not company.property_cash_account_id:
                account = self.env['account.account'].search([('account_type', 'in', ('asset_cash', 'asset_current')), ('company_id', '=', company.id)], limit=1)
                res['property_cash_account_id'] = account.id

        if 'property_analytic_plan_id' in fields_list and not res.get('property_analytic_plan_id'):
            if not company.property_analytic_plan_id:
                plan = self.env['account.analytic.plan'].search([], limit=1)
                res['property_analytic_plan_id'] = plan.id
                
        return res

    property_currency_id = fields.Many2one(
        related='company_id.property_currency_id',
        readonly=False,
        string='Default Contract Currency',
    )
    property_rent_journal_id = fields.Many2one(
        related='company_id.property_rent_journal_id',
        readonly=False,
        string='Default Rent Journal',
    )
    property_deposit_journal_id = fields.Many2one(
        related='company_id.property_deposit_journal_id',
        readonly=False,
        string='Default Deposit Journal',
    )
    property_maintenance_journal_id = fields.Many2one(
        related='company_id.property_maintenance_journal_id',
        readonly=False,
        string='Default Maintenance Journal',
    )
    property_cash_journal_id = fields.Many2one(
        related='company_id.property_cash_journal_id',
        readonly=False,
        string='Default Cash Journal',
    )
    property_bank_journal_id = fields.Many2one(
        related='company_id.property_bank_journal_id',
        readonly=False,
        string='Default Bank Journal',
    )
    property_receivable_account_id = fields.Many2one(
        related='company_id.property_receivable_account_id',
        readonly=False,
        string='Default Receivable Account',
    )
    property_rent_income_account_id = fields.Many2one(
        related='company_id.property_rent_income_account_id',
        readonly=False,
        string='Default Rent Income Account',
    )
    property_service_income_account_id = fields.Many2one(
        related='company_id.property_service_income_account_id',
        readonly=False,
        string='Default Service Income Account',
    )
    property_deposit_liability_account_id = fields.Many2one(
        related='company_id.property_deposit_liability_account_id',
        readonly=False,
        string='Default Deposit Liability Account',
    )
    property_advance_liability_account_id = fields.Many2one(
        related='company_id.property_advance_liability_account_id',
        readonly=False,
        string='Default Advance Liability Account',
    )
    property_maintenance_expense_account_id = fields.Many2one(
        related='company_id.property_maintenance_expense_account_id',
        readonly=False,
        string='Default Maintenance Expense Account',
    )
    property_cash_account_id = fields.Many2one(
        related='company_id.property_cash_account_id',
        readonly=False,
        string='Default Cash/Clearing Account',
    )
    property_analytic_plan_id = fields.Many2one(
        related='company_id.property_analytic_plan_id',
        readonly=False,
        string='Default Analytic Plan',
    )

    def action_create_property_custom_accounts(self):
        company = self.env.company

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

        vals = {
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
        }
        company.write(vals)
        if self._name == 'res.config.settings':
            self.write(vals)
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
