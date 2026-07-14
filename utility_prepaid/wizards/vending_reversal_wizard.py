import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services.security_service import PrepaidSecurityService

_logger = logging.getLogger(__name__)


class VendingReversalWizard(models.TransientModel):
    _name = 'utility.vending.reversal.wizard'
    _description = 'معالج عكس البيع'

    vending_request_id = fields.Many2one(
        'utility.vending.request',
        string='طلب البيع',
        required=True,
    )
    token_id = fields.Many2one(
        'utility.token',
        string='التوكن الأصلي',
    )
    reversal_reason_id = fields.Many2one(
        'utility.reversal.reason',
        string='سبب العكس',
        required=True,
    )
    reversal_type = fields.Selection([
        ('full', 'عكس كامل'),
        ('partial', 'عكس جزئي'),
    ], string='نوع العكس', default='full', required=True)
    refund_amount = fields.Monetary(
        'مبلغ الاسترداد',
        currency_field='currency_id',
    )
    notes = fields.Text('ملاحظات')
    currency_id = fields.Many2one(
        'res.currency',
        related='vending_request_id.company_id.currency_id',
        store=True,
    )

    @api.onchange('vending_request_id', 'reversal_type')
    def _onchange_vending_request(self):
        if self.vending_request_id:
            token = self.vending_request_id.token_ids.filtered(
                lambda t: t.status == 'success', limit=1)
            if token:
                self.token_id = token
            if self.reversal_type == 'full':
                self.refund_amount = self.vending_request_id.energy_amount
            else:
                self.refund_amount = 0.0

    @api.onchange('reversal_type')
    def _onchange_reversal_type(self):
        if self.reversal_type == 'full' and self.vending_request_id:
            self.refund_amount = self.vending_request_id.energy_amount

    @api.constrains('refund_amount')
    def _check_refund_amount(self):
        for rec in self:
            if rec.reversal_type == 'partial' and (not rec.refund_amount or rec.refund_amount <= 0):
                raise UserError(_('يجب تحديد مبلغ الاسترداد للعكس الجزئي.'))
            if rec.reversal_type == 'full' and rec.vending_request_id:
                if rec.refund_amount > rec.vending_request_id.energy_amount:
                    raise UserError(_('مبلغ الاسترداد لا يمكن أن يتجاوز مبلغ الطاقة.'))

    def action_submit(self):
        self.ensure_one()

        if self.vending_request_id.state not in ('completed', 'token_generated'):
            raise UserError(_('لا يمكن عكس طلب غير مكتمل.'))

        if self.reversal_reason_id.requires_approval:
            security_service = PrepaidSecurityService(self.env)
            try:
                temp_reversal = self.env['utility.vending.reversal'].new({
                    'vending_request_id': self.vending_request_id.id,
                    'amount': self.refund_amount,
                })
                security_service.validate_reversal_approval(
                    temp_reversal, self.env.user)
            except UserError:
                raise

        reversal = self.env['utility.vending.reversal'].create({
            'vending_request_id': self.vending_request_id.id,
            'token_id': self.token_id.id if self.token_id else False,
            'reversal_type': self.reversal_type,
            'amount': self.refund_amount,
            'reason_id': self.reversal_reason_id.id,
            'reason_details': self.notes or '',
        })
        reversal.action_submit()

        return {
            'type': 'ir.actions.act_window',
            'name': _('طلب العكس'),
            'res_model': 'utility.vending.reversal',
            'res_id': reversal.id,
            'view_mode': 'form',
            'target': 'current',
        }
