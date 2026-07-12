from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReversal(models.Model):
    _name = 'utility.reversal'
    _description = '????? ????? ??? ????'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean('???', default=True)
    company_id = fields.Many2one('res.company', '??????', default=lambda self: self.env.company)
    reference = fields.Char('??????', required=True, default=lambda self: _('????'))
    date = fields.Datetime('???????', default=fields.Datetime.now)
    reversal_type = fields.Selection([
        ('full', '????'),
        ('partial', '????'),
    ], string='??? ???????', required=True, default='full')
    amount = fields.Monetary(string='??????', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    customer_id = fields.Many2one('res.partner', string='??????', required=True)
    account_id = fields.Many2one('utility.customer', string='??????', required=True)
    meter_id = fields.Many2one('utility.meter', string='??????')
    pos_order_id = fields.Many2one('pos.order', string='??? ???? ?????')
    reason = fields.Text(string='?????', required=True)
    approved_by = fields.Many2one('res.users', string='????? ??')
    operator_id = fields.Many2one('res.users', string='??????', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', '?????'),
        ('approved', '?????'),
        ('completed', '?????'),
        ('rejected', '?????'),
    ], default='draft', string='??????', tracking=True)

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
        })

    def action_complete(self):
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError(_('??? ?????? ??????? ??? ??????.'))
        self.env['utility.transaction'].create_transaction(
            'reversal', self.account_id, self.amount,
            pos_order=self.pos_order_id, reversal=self,
            notes=_('????? %s: %s') % (self.reference, self.reason),
        )
        if self.pos_order_id:
            self.pos_order_id.write({'reversal_id': self.id})
        self.state = 'completed'

    def action_reject(self):
        self.ensure_one()
        self.state = 'rejected'

    @api.model
    def create(self, vals):
        if vals.get('reference', _('????')) == _('????'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('utility.reversal') or _('????')
        return super().create(vals)
