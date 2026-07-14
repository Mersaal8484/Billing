import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityPrepaidDebtRecovery(models.Model):
    _name = 'utility.prepaid.debt.recovery'
    _description = 'عملية استقطاع دين'
    _rec_name = 'reference'
    _order = 'date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    reference = fields.Char('المرجع', required=True, copy=False, index=True, default=lambda self: _('جديد'))
    date = fields.Datetime('التاريخ', default=fields.Datetime.now, index=True)

    policy_id = fields.Many2one('utility.prepaid.debt.policy', 'سياسة الاستقطاع',
        required=True, index=True)
    account_id = fields.Many2one('utility.customer', 'حساب المشترك', required=True, index=True)
    partner_id = fields.Many2one('res.partner', 'العميل', related='account_id.partner_id', store=True)

    vending_request_id = fields.Many2one('utility.vending.request', 'طلب البيع', index=True)
    debt_amount = fields.Monetary('مبلغ الدين', currency_field='currency_id')
    recovered_amount = fields.Monetary('المبلغ المستقطع', currency_field='currency_id')

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('applied', 'مطبق'),
        ('cancelled', 'ملغى'),
    ], 'الحالة', default='draft', tracking=True, index=True)

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    notes = fields.Text('ملاحظات')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.debt.recovery') or _('جديد')
        return super().create(vals_list)

    def action_apply(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            recovered = rec.policy_id.calculate_recovery(rec.account_id,
                rec.vending_request_id.gross_amount if rec.vending_request_id else rec.debt_amount)
            rec.write({
                'recovered_amount': recovered,
                'state': 'applied',
            })
            if rec.vending_request_id:
                rec.vending_request_id.debt_recovery_amount = recovered
