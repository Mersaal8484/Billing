import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TokenResendWizard(models.TransientModel):
    _name = 'utility.token.resend.wizard'
    _description = 'معالج إعادة إرسال التوكن'

    token_id = fields.Many2one(
        'utility.token',
        string='التوكن',
        required=True,
        readonly=True,
    )
    delivery_method = fields.Selection([
        ('sms', 'SMS'),
        ('portal', 'البوابة'),
    ], string='طريقة التسليم', default='sms', required=True)
    mobile_number = fields.Char(
        'رقم الهاتف',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            token = self.env['utility.token'].browse(active_id)
            res['token_id'] = token.id
            if token.customer_id:
                res['mobile_number'] = token.customer_id.phone or token.customer_id.mobile
        return res

    @api.onchange('token_id')
    def _onchange_token_id(self):
        if self.token_id and self.token_id.customer_id:
            self.mobile_number = self.token_id.customer_id.phone or self.token_id.customer_id.mobile

    def action_resend(self):
        self.ensure_one()

        if self.token_id.status != 'success':
            raise UserError(_('لا يمكن إعادة إرسال توكن غير ناجح.'))

        limit = self.token_id.company_id.token_resend_limit or 5
        if self.token_id.resend_count >= limit:
            raise UserError(_('تم تجاوز حد إعادة الإرسال (%d).') % limit)

        if self.delivery_method == 'sms':
            if self.mobile_number:
                original_phone = self.token_id.customer_id.phone
                try:
                    if self.mobile_number != original_phone:
                        self.token_id.customer_id.write({'phone': self.mobile_number})
                    self.token_id.action_resend_sms()
                finally:
                    if self.mobile_number != original_phone:
                        self.token_id.customer_id.write({'phone': original_phone})
            else:
                raise UserError(_('يجب تحديد رقم الهاتف.'))
        elif self.delivery_method == 'portal':
            self.token_id.write({
                'resend_count': self.token_id.resend_count + 1,
                'last_resend_date': fields.Datetime.now(),
                'delivery_state': 'sms_sent',
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('تمت إعادة الإرسال'),
                'message': _('تم إعادة إرسال التوكن بنجاح.'),
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window_close',
                },
            },
        }
