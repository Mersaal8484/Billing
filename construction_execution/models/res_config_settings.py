from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_auto_create_analytic = fields.Boolean(
        string='Auto-create Analytic Account',
        help='Automatically create an analytic account when a new '
             'construction project is created')
    construction_auto_create_project = fields.Boolean(
        string='Auto-create Odoo Project',
        help='Automatically create an Odoo project when a construction '
             'project reaches the Execution stage')
    construction_auto_create_tasks = fields.Boolean(
        string='Auto-create Tasks from BOQ',
        help='Automatically create project tasks from BOQ items '
             'when a BOQ is approved')
    construction_default_retention = fields.Float(
        string='Default Retention %', default=5.0,
        help='Default retention percentage for new IPCs')
    construction_default_tax = fields.Float(
        string='Default Tax %', default=0.0,
        help='Default tax percentage for new IPCs')
    construction_default_analytic_plan_id = fields.Many2one(
        'account.analytic.plan', string='Default Analytic Plan',
        help='Default analytic plan for auto-created analytic accounts')
    construction_income_account_id = fields.Many2one(
        'account.account', string='Default Income Account',
        domain="[('account_type', '=', 'income')]",
        help='Default income account for IPC invoices')
    construction_expense_account_id = fields.Many2one(
        'account.account', string='Default Expense Account',
        domain="[('account_type', '=', 'expense')]",
        help='Default expense account for cost entries')

    @api.model
    def get_values(self):
        res = super().get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        company = self.env.company

        plan_id = int(ICPSudo.get_param(
            'construction.default_analytic_plan_id', default='0') or 0)
        if not plan_id:
            plan = self.env['account.analytic.plan'].search([
                '|', ('name', 'ilike', 'project'),
                     ('name', 'ilike', 'construction'),
            ], limit=1) or self.env['account.analytic.plan'].search([], limit=1)
            if plan:
                plan_id = plan.id

        income_id = int(ICPSudo.get_param(
            'construction.income_account_id', default='0') or 0)
        if not income_id:
            account = self.env['account.account'].search([
                ('account_type', '=', 'income'),
                ('deprecated', '=', False),
            ], limit=1)
            if account:
                income_id = account.id

        expense_id = int(ICPSudo.get_param(
            'construction.expense_account_id', default='0') or 0)
        if not expense_id:
            account = self.env['account.account'].search([
                ('account_type', '=', 'expense'),
                ('deprecated', '=', False),
            ], limit=1)
            if account:
                expense_id = account.id

        res.update(
            construction_auto_create_analytic=(
                ICPSudo.get_param(
                    'construction.auto_create_analytic', default='True')
                == 'True'),
            construction_auto_create_project=(
                ICPSudo.get_param(
                    'construction.auto_create_project', default='True')
                == 'True'),
            construction_auto_create_tasks=(
                ICPSudo.get_param(
                    'construction.auto_create_tasks', default='False')
                == 'True'),
            construction_default_retention=float(
                ICPSudo.get_param(
                    'construction.default_retention', default='5.0')),
            construction_default_tax=float(
                ICPSudo.get_param(
                    'construction.default_tax', default='15.0')),
            construction_default_analytic_plan_id=plan_id,
            construction_income_account_id=income_id,
            construction_expense_account_id=expense_id,
        )
        return res

    def set_values(self):
        super().set_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        ICPSudo.set_param(
            'construction.auto_create_analytic',
            str(self.construction_auto_create_analytic))
        ICPSudo.set_param(
            'construction.auto_create_project',
            str(self.construction_auto_create_project))
        ICPSudo.set_param(
            'construction.auto_create_tasks',
            str(self.construction_auto_create_tasks))
        ICPSudo.set_param(
            'construction.default_retention',
            str(self.construction_default_retention))
        ICPSudo.set_param(
            'construction.default_tax',
            str(self.construction_default_tax))
        ICPSudo.set_param(
            'construction.default_analytic_plan_id',
            str(self.construction_default_analytic_plan_id.id or 0))
        ICPSudo.set_param(
            'construction.income_account_id',
            str(self.construction_income_account_id.id or 0))
        ICPSudo.set_param(
            'construction.expense_account_id',
            str(self.construction_expense_account_id.id or 0))
