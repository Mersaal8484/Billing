from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityAdjustment(models.Model):
    _name = 'utility.adjustment'
    _description = 'Prepaid Token Sale Adjustment Audit'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    reference = fields.Char('Reference', required=True, default=lambda self: _('New'))
    date = fields.Datetime('Date', default=fields.Datetime.now)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    account_id = fields.Many2one('utility.customer', string='Account', required=True)
    adjustment_type = fields.Selection([
        ('credit', 'Credit Audit'),
        ('debit', 'Debit Audit'),
        ('compensation', 'Compensation'),
        ('correction', 'Correction'),
    ], string='Adjustment Type', required=True)
    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    reason = fields.Text(string='Reason', required=True)
    approved_by = fields.Many2one('res.users', string='Approved By')
    operator_id = fields.Many2one('res.users', string='Operator', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True)

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
        })

    def action_apply(self):
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError(_('The adjustment must be approved before applying it.'))
        signed_amount = self.amount
        if self.adjustment_type in ('debit', 'correction'):
            signed_amount = -self.amount
        self.env['utility.transaction'].create_transaction(
            'adjustment', self.account_id, signed_amount,
            adjustment=self, notes=_('Adjustment %s: %s') % (self.reference, self.reason))
        self.state = 'applied'

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'

    @api.model
    def create(self, vals):
        if vals.get('reference', _('New')) == _('New'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('utility.adjustment') or _('New')
        return super().create(vals)
