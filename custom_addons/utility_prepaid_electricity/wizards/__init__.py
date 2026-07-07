from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityTokenValidateWizard(models.TransientModel):
    _name = 'utility.token.validate.wizard'
    _description = 'Validate STS Token'

    token_number = fields.Char(string='Token Number', required=True,
                               help='20-digit STS token number')
    meter_id = fields.Many2one('utility.meter', string='Meter', required=True)
    customer_id = fields.Many2one('utility.customer', string='Customer',
                                  related='meter_id.customer_id')
    result = fields.Char(string='Validation Result', readonly=True)

    def action_validate(self):
        self.ensure_one()
        token = self.env['utility.token'].search([
            ('token_number', '=', self.token_number),
            ('meter_id', '=', self.meter_id.id),
            ('status', '=', 'success'),
        ], limit=1)
        if token:
            self.result = _('Valid token. Amount: %(amount)s, kWh: %(kwh)s') % {
                'amount': token.amount,
                'kwh': token.kwh,
            }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Valid Token'),
                    'message': self.result,
                    'sticky': False,
                    'type': 'success',
                },
            }
        self.result = _('Invalid or expired token.')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invalid Token'),
                'message': self.result,
                'sticky': False,
                'type': 'warning',
            },
        }
