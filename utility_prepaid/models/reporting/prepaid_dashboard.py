import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityPrepaidDashboard(models.TransientModel):
    _name = 'utility.prepaid.dashboard'
    _description = 'لوحة معلومات الدفع المسبق'

    date_from = fields.Date('من تاريخ')
    date_to = fields.Date('إلى تاريخ')
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)

    today_vending_count = fields.Integer('عمليات البيع اليوم', compute='_compute_dashboard')
    today_vending_amount = fields.Monetary('مبلغ البيع اليوم', currency_field='currency_id', compute='_compute_dashboard')
    today_kwh_sold = fields.Float('kWh مباعة اليوم', digits=(12, 3), compute='_compute_dashboard')

    month_vending_count = fields.Integer('عمليات البيع هذا الشهر', compute='_compute_dashboard')
    month_vending_amount = fields.Monetary('مبلغ البيع هذا الشهر', currency_field='currency_id', compute='_compute_dashboard')
    month_kwh_sold = fields.Float('kWh مباعة هذا الشهر', digits=(12, 3), compute='_compute_dashboard')

    pending_tokens = fields.Integer('توكنات معلقة', compute='_compute_dashboard')
    failed_tokens = fields.Integer('توكنات فاشلة', compute='_compute_dashboard')
    successful_tokens = fields.Integer('توكنات ناجحة', compute='_compute_dashboard')

    open_shifts = fields.Integer('ورديات مفتوحة', compute='_compute_dashboard')
    pending_reversals = fields.Integer('طلبات عكس معلقة', compute='_compute_dashboard')
    pending_adjustments = fields.Integer('تسويات معلقة', compute='_compute_dashboard')

    total_debt_recovered = fields.Monetary('ديون مستقطعة', currency_field='currency_id', compute='_compute_dashboard')
    total_reversals_amount = fields.Monetary('مبالغ معكوسة', currency_field='currency_id', compute='_compute_dashboard')
    total_adjustments_amount = fields.Monetary('مبالغ تسوية', currency_field='currency_id', compute='_compute_dashboard')

    top_meters_ids = fields.Many2many('utility.meter', compute='_compute_dashboard', string='أعلى العدادات مبيعاً')

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)

    def _compute_dashboard(self):
        today = fields.Date.today()
        month_start = today.replace(day=1)

        domain_today = [
            ('company_id', '=', self.company_id.id),
            ('vending_date', '>=', fields.Datetime.from_string(str(today))),
            ('state', 'in', ('completed', 'token_generated', 'paid')),
        ]
        domain_month = [
            ('company_id', '=', self.company_id.id),
            ('vending_date', '>=', fields.Datetime.from_string(str(month_start))),
            ('state', 'in', ('completed', 'token_generated', 'paid')),
        ]

        VendingRequest = self.env['utility.vending.request']
        today_requests = VendingRequest.search(domain_today)
        month_requests = VendingRequest.search(domain_month)

        self.today_vending_count = len(today_requests)
        self.today_vending_amount = sum(today_requests.mapped('gross_amount'))
        self.today_kwh_sold = sum(today_requests.mapped('kwh_purchased'))

        self.month_vending_count = len(month_requests)
        self.month_vending_amount = sum(month_requests.mapped('gross_amount'))
        self.month_kwh_sold = sum(month_requests.mapped('kwh_purchased'))

        Token = self.env['utility.token']
        self.pending_tokens = Token.search_count([
            ('company_id', '=', self.company_id.id),
            ('status', '=', 'pending'),
        ])
        self.failed_tokens = Token.search_count([
            ('company_id', '=', self.company_id.id),
            ('status', '=', 'failed'),
        ])
        self.successful_tokens = Token.search_count([
            ('company_id', '=', self.company_id.id),
            ('status', '=', 'success'),
        ])

        Shift = self.env['utility.cashier.shift']
        self.open_shifts = Shift.search_count([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'open'),
        ])

        Reversal = self.env['utility.vending.reversal']
        self.pending_reversals = Reversal.search_count([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('draft', 'submitted', 'under_review', 'provider_validation', 'approved')),
        ])
        self.total_reversals_amount = sum(
            Reversal.search([
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'completed'),
            ]).mapped('amount')
        )

        Adjustment = self.env['utility.prepaid.adjustment']
        self.pending_adjustments = Adjustment.search_count([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('draft', 'submitted', 'under_review', 'approved')),
        ])
        self.total_adjustments_amount = sum(
            Adjustment.search([
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'applied'),
            ]).mapped('amount')
        )

        Recovery = self.env['utility.prepaid.debt.recovery']
        self.total_debt_recovered = sum(
            Recovery.search([
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'applied'),
            ]).mapped('recovered_amount')
        )

        top_meter_data = VendingRequest.read_group(
            domain_month + [('meter_id', '!=', False)],
            ['meter_id', 'kwh_purchased:sum'],
            ['meter_id'],
        )
        top_meter_data.sort(key=lambda x: x.get('kwh_purchased_sum', 0), reverse=True)
        top_meter_ids = [m['meter_id'][0] for m in top_meter_data[:10] if m.get('meter_id')]
        self.top_meters_ids = [(6, 0, top_meter_ids)]

    def action_refresh(self):
        self._compute_dashboard()

    def action_view_pending_tokens(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('توكنات معلقة'),
            'res_model': 'utility.token',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('status', '=', 'pending'),
            ],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_failed_tokens(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('توكنات فاشلة'),
            'res_model': 'utility.token',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('status', '=', 'failed'),
            ],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_open_shifts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('ورديات مفتوحة'),
            'res_model': 'utility.cashier.shift',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'open'),
            ],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_pending_reversals(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('طلبات عكس معلقة'),
            'res_model': 'utility.vending.reversal',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('state', 'in', ('draft', 'submitted', 'under_review', 'provider_validation', 'approved')),
            ],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_today_vending(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('عمليات البيع اليوم'),
            'res_model': 'utility.vending.request',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('vending_date', '>=', fields.Datetime.from_string(str(fields.Date.today()))),
            ],
            'views': [(False, 'tree'), (False, 'form')],
        }
