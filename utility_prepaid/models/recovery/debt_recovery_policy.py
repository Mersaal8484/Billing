import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityPrepaidDebtPolicy(models.Model):
    _name = 'utility.prepaid.debt.policy'
    _description = 'سياسة استقطاع الديون'
    _rec_name = 'name'
    _order = 'sequence, name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم السياسة', required=True)
    sequence = fields.Integer('التسلسل', default=10)

    recovery_method = fields.Selection([
        ('fixed', 'مبلغ ثابت'),
        ('percentage', 'نسبة مئوية'),
        ('full', 'كامل الدين المستحق'),
        ('installment', 'أقساط'),
        ('priority', 'حسب الأولوية'),
    ], 'طريقة الاستقطاع', default='percentage', required=True)

    recovery_percentage = fields.Float('نسبة الاستقطاع (%)', default=0.0)
    fixed_amount = fields.Monetary('المبلغ الثابت', currency_field='currency_id', default=0.0)
    installment_amount = fields.Monetary('مبلغ القسط', currency_field='currency_id', default=0.0)

    max_recovery_per_vending = fields.Monetary('أقصى استقطاع لكل شحنة',
        currency_field='currency_id', default=0.0)
    min_energy_percentage = fields.Float('أقل نسبة طاقة بعد الاستقطاع (%)', default=10.0)

    scope = fields.Selection([
        ('all', 'جميع العملاء'),
        ('category', 'حسب الفئة'),
        ('subscriber', 'حسب النوع'),
    ], 'النطاق', default='all')
    category_ids = fields.Many2many('utility.subscriber.category', string='الفئات المستهدفة')
    subscriber_ids = fields.Many2many('utility.subscriber', string='الأنواع المستهدفة')

    debt_types = fields.Selection([
        ('all', 'جميع الديون'),
        ('overdue', 'الديون المتأخرة فقط'),
        ('specific', 'أنواع محددة'),
    ], 'أنواع الديون المشمولة', default='all')

    priority_debt_account_ids = fields.Many2many('account.account', string='حسابات الديون ذات الأولوية')
    recovery_account_id = fields.Many2one('account.account', 'حساب الاستقطاع المحاسبي')

    date_from = fields.Date('ساري من')
    date_to = fields.Date('ساري حتى')
    description = fields.Text('الوصف')

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    line_ids = fields.One2many('utility.prepaid.debt.policy.line', 'policy_id', 'بنود السياسة')

    @api.model
    def get_applicable_policy(self, account):
        domain = [
            ('active', '=', True),
            ('company_id', '=', account.company_id.id),
        ]
        if account.category_id:
            policies = self.search(domain + [('scope', '=', 'category'),
                                              ('category_ids', 'in', account.category_id.id)])
            if policies:
                return policies[0]
        if account.subscriber_id:
            policies = self.search(domain + [('scope', '=', 'subscriber'),
                                              ('subscriber_ids', 'in', account.subscriber_id.id)])
            if policies:
                return policies[0]
        default = self.search(domain + [('scope', '=', 'all')], order='sequence, id', limit=1)
        return default[0] if default else self.env['utility.prepaid.debt.policy']

    def calculate_recovery(self, account, gross_amount):
        self.ensure_one()
        if not self.active:
            return 0.0

        debt = account.accounting_balance or 0.0
        if debt <= 0:
            return 0.0

        if self.recovery_method == 'full':
            amount = min(debt, gross_amount * (self.min_energy_percentage / 100.0))
            return max(0, min(debt, gross_amount - amount))
        elif self.recovery_method == 'percentage':
            amount = gross_amount * (self.recovery_percentage / 100.0)
        elif self.recovery_method == 'fixed':
            amount = self.fixed_amount
        elif self.recovery_method == 'installment':
            amount = self.installment_amount
        else:
            amount = 0.0

        if self.max_recovery_per_vending:
            amount = min(amount, self.max_recovery_per_vending)

        min_energy = gross_amount * (self.min_energy_percentage / 100.0)
        if gross_amount - amount < min_energy:
            amount = max(0, gross_amount - min_energy)

        return min(amount, debt)
