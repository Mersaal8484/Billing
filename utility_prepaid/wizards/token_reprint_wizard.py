import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TokenReprintWizard(models.TransientModel):
    _name = 'utility.token.reprint.wizard'
    _description = 'معالج إعادة طباعة التوكن'

    token_id = fields.Many2one(
        'utility.token',
        string='التوكن',
        required=True,
        readonly=True,
    )
    reason = fields.Text('سبب إعادة الطباعة')
    reprint_count = fields.Integer(
        'عدد إعادة الطباعة',
        compute='_compute_reprint_count',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            token = self.env['utility.token'].browse(active_id)
            res['token_id'] = token.id
        return res

    @api.depends('token_id')
    def _compute_reprint_count(self):
        for rec in self:
            rec.reprint_count = rec.token_id.reprint_count if rec.token_id else 0

    def action_reprint(self):
        self.ensure_one()

        if self.token_id.status != 'success':
            raise UserError(_('لا يمكن إعادة طباعة توكن غير ناجح.'))

        limit = self.token_id.company_id.token_reprint_limit or 3
        if self.token_id.reprint_count >= limit:
            raise UserError(_('تم تجاوز حد إعادة الطباعة (%d).') % limit)

        if self.token_id.company_id.require_reprint_reason and not self.reason:
            raise UserError(_('يجب تحديد سبب إعادة الطباعة.'))

        self.token_id.write({
            'reprint_count': self.token_id.reprint_count + 1,
            'last_reprint_date': fields.Datetime.now(),
            'delivery_state': 'printed',
        })

        return {
            'type': 'ir.actions.report',
            'report_name': 'utility_prepaid.report_token_receipt',
            'report_type': 'qweb-pdf',
            'data': {
                'token_ids': [self.token_id.id],
                'reprint': True,
                'reprint_reason': self.reason or '',
            },
        }
