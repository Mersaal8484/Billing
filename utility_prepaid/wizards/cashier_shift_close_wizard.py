import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class CashierShiftCloseWizard(models.TransientModel):
    _name = 'utility.cashier.shift.close.wizard'
    _description = 'معالج إغلاق الوردية'

    shift_id = fields.Many2one(
        'utility.cashier.shift',
        string='الوردية',
        required=True,
        readonly=True,
    )
    closing_balance = fields.Monetary(
        'الرصيد الختامي',
        currency_field='currency_id',
        required=True,
    )
    notes = fields.Text('ملاحظات')
    prepaid_cash = fields.Monetary(
        'نقدي - دفع مسبق',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    prepaid_bank = fields.Monetary(
        'بنكي - دفع مسبق',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    postpaid_cash = fields.Monetary(
        'نقدي - دفع آجل',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    postpaid_bank = fields.Monetary(
        'بنكي - دفع آجل',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    expected_total = fields.Monetary(
        'الإجمالي المتوقع',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    difference = fields.Monetary(
        'الفرق',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='shift_id.company_id.currency_id',
        store=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            shift = self.env['utility.cashier.shift'].browse(active_id)
            res['shift_id'] = shift.id
            res['closing_balance'] = shift.opening_balance or 0.0
        return res

    @api.depends('shift_id')
    def _compute_totals(self):
        for rec in self:
            if rec.shift_id:
                rec.prepaid_cash = rec.shift_id.prepaid_cash_total
                rec.prepaid_bank = rec.shift_id.prepaid_bank_total
                rec.postpaid_cash = rec.shift_id.postpaid_cash_total
                rec.postpaid_bank = rec.shift_id.postpaid_bank_total
                rec.expected_total = (
                    (rec.shift_id.opening_balance or 0.0)
                    + (rec.shift_id.prepaid_total or 0.0)
                    + (rec.shift_id.postpaid_total or 0.0)
                )
                rec.difference = (rec.closing_balance or 0.0) - rec.expected_total
            else:
                rec.prepaid_cash = 0.0
                rec.prepaid_bank = 0.0
                rec.postpaid_cash = 0.0
                rec.postpaid_bank = 0.0
                rec.expected_total = 0.0
                rec.difference = 0.0

    @api.onchange('closing_balance')
    def _onchange_closing_balance(self):
        if self.shift_id:
            self.difference = (self.closing_balance or 0.0) - (
                (self.shift_id.opening_balance or 0.0)
                + (self.shift_id.prepaid_total or 0.0)
                + (self.shift_id.postpaid_total or 0.0)
            )

    def action_close(self):
        self.ensure_one()

        if self.shift_id.state != 'open':
            raise UserError(_('يمكن إغلاق الوردية المفتوحة فقط.'))

        tolerance = self.shift_id.company_id.cash_tolerance or 0.0
        if abs(self.difference) > tolerance:
            raise ValidationError(
                _('الفرق (%.2f) يتجاوز الحد المسموح به (%.2f). يرجى المراجعة.')
                % (self.difference, tolerance)
            )

        self.shift_id.write({
            'closing_balance': self.closing_balance,
            'end_time': fields.Datetime.now(),
            'state': 'closing',
            'closing_notes': self.notes or '',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('الوردية'),
            'res_model': 'utility.cashier.shift',
            'res_id': self.shift_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
