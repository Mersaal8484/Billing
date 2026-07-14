import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..services.idempotency_service import IdempotencyService

_logger = logging.getLogger(__name__)


class VendingRetryWizard(models.TransientModel):
    _name = 'utility.vending.retry.wizard'
    _description = 'معالج إعادة محاولة البيع'

    vending_request_ids = fields.Many2many(
        'utility.vending.request',
        string='طلبات البيع',
    )
    retry_all = fields.Boolean('إعادة محاولة الكل', default=False)
    max_retries = fields.Integer('أقصى إعادة محاولة', default=3)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids and not res.get('vending_request_ids'):
            res['vending_request_ids'] = [(6, 0, active_ids)]
        return res

    def action_retry(self):
        self.ensure_one()

        if self.retry_all:
            requests = self.env['utility.vending.request'].search([
                ('state', 'in', ('token_pending', 'token_failed')),
                ('retry_count', '<', self.max_retries),
            ], limit=100)
        else:
            requests = self.vending_request_ids.filtered(
                lambda r: r.state in ('token_pending', 'token_failed')
                and r.retry_count < self.max_retries)

        if not requests:
            raise UserError(_('لا توجد طلبات مؤهلة لإعادة المحاولة.'))

        success_count = 0
        fail_count = 0
        results = []

        idempotency_service = IdempotencyService(self.env)

        for req in requests:
            try:
                result = idempotency_service.handle_pending_request(req)
                if result.get('status') in ('recovered', 'success'):
                    success_count += 1
                else:
                    fail_count += 1
                results.append({
                    'reference': req.reference,
                    'state': req.state,
                    'result': result.get('message', ''),
                })
            except Exception as e:
                _logger.exception('Retry failed for request %s', req.reference)
                fail_count += 1
                results.append({
                    'reference': req.reference,
                    'state': req.state,
                    'result': str(e),
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('نتيجة إعادة المحاولة'),
                'message': _('تمت إعادة محاولة %d طلب: %d ناجح، %d فاشل') % (
                    len(requests), success_count, fail_count),
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window_close',
                },
            },
        }
