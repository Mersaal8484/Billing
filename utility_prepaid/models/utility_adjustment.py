from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityAdjustment(models.Model):
    _name = 'utility.adjustment'
    _description = '????? ????? ??? ????'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean('???', default=True)
    company_id = fields.Many2one('res.company', '??????', default=lambda self: self.env.company)
    reference = fields.Char('??????', required=True, default=lambda self: _('????'))
    date = fields.Datetime('???????', default=fields.Datetime.now)
    customer_id = fields.Many2one('res.partner', string='??????', required=True)
    account_id = fields.Many2one('utility.customer', string='??????', required=True)
    adjustment_type = fields.Selection([
        ('credit', '????? ???????'),
        ('debit', '????? ??????'),
        ('compensation', '?????'),
        ('correction', '?????'),
    ], string='??? ???????', required=True)
    amount = fields.Monetary(string='??????', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    reason = fields.Text(string='?????', required=True)
    approved_by = fields.Many2one('res.users', string='????? ??')
    operator_id = fields.Many2one('res.users', string='??????', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', '?????'),
        ('approved', '?????'),
        ('applied', '??????'),
        ('cancelled', '????'),
    ], default='draft', string='??????', tracking=True)

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
        })

    def action_apply(self):
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError(_('??? ?????? ??????? ??? ??????.'))
        signed_amount = self.amount
        if self.adjustment_type in ('debit', 'correction'):
            signed_amount = -self.amount
        self.env['utility.transaction'].create_transaction(
            'adjustment', self.account_id, signed_amount,
            adjustment=self, notes=_('????? %s: %s') % (self.reference, self.reason))
        self.state = 'applied'

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'

    @api.model
    def create(self, vals):
        if vals.get('reference', _('????')) == _('????'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('utility.adjustment') or _('????')
        return super().create(vals)
