import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PrepaidAdjustmentWizard(models.TransientModel):
    _name = 'utility.prepaid.adjustment.wizard'
    _description = 'معالج تسوية الدفع المسبق'

    account_id = fields.Many2one(
        'utility.customer',
        string='حساب المشترك',
        required=True,
    )
    meter_id = fields.Many2one(
        'utility.meter',
        string='العداد',
    )
    adjustment_type = fields.Selection([
        ('credit', 'تسوية دائنة'),
        ('debit', 'تسوية مدينة'),
        ('compensation', 'تعويض'),
        ('correction', 'تصحيح'),
    ], string='نوع التسوية', required=True, default='credit')
    amount = fields.Monetary(
        'المبلغ',
        currency_field='currency_id',
        required=True,
    )
    kwh_amount = fields.Float(
        'الوحدات (kWh)',
        digits=(12, 3),
    )
    reason = fields.Text('السبب', required=True)
    requires_management_token = fields.Boolean(
        'يتطلب توكن إدارة',
        default=False,
    )
    token_type = fields.Selection([
        ('credit', 'رصيد'),
        ('management', 'إدارة'),
        ('key_change', 'تغيير مفتاح'),
    ], string='نوع التوكن', default='management')
    currency_id = fields.Many2one(
        'res.currency',
        related='account_id.company_id.currency_id',
        store=True,
    )

    @api.onchange('account_id')
    def _onchange_account_id(self):
        if self.account_id and hasattr(self.account_id, 'meter_ids'):
            meters = self.account_id.meter_ids
            if len(meters) == 1:
                self.meter_id = meters

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('المبلغ يجب أن يكون أكبر من صفر.'))

    @api.onchange('adjustment_type')
    def _onchange_adjustment_type(self):
        if self.adjustment_type in ('credit', 'compensation'):
            self.requires_management_token = True
        else:
            self.requires_management_token = False

    def action_submit(self):
        self.ensure_one()

        if not self.meter_id and self.requires_management_token:
            raise UserError(_('يجب تحديد العداد لتوليد توكن الإدارة.'))

        adjustment_vals = {
            'partner_id': self.account_id.partner_id.id if self.account_id.partner_id else False,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id if self.meter_id else False,
            'adjustment_type': self.adjustment_type,
            'amount': self.amount,
            'kwh_amount': self.kwh_amount,
            'reason': self.reason,
        }

        adjustment = self.env['utility.prepaid.adjustment'].create(adjustment_vals)
        adjustment.action_submit()

        return {
            'type': 'ir.actions.act_window',
            'name': _('تسوية الدفع المسبق'),
            'res_model': 'utility.prepaid.adjustment',
            'res_id': adjustment.id,
            'view_mode': 'form',
            'target': 'current',
        }
