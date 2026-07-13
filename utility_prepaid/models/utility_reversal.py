from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReversal(models.Model):
    _name = 'utility.reversal'
    _description = 'Prepaid Token Sale Reversal Audit'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    reference = fields.Char('Reference', required=True, default=lambda self: _('New'))
    date = fields.Datetime('Date', default=fields.Datetime.now)
    reversal_type = fields.Selection([
        ('full', 'Full'),
        ('partial', 'Partial'),
    ], string='Reversal Type', required=True, default='full')
    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    account_id = fields.Many2one('utility.customer', string='Account', required=True)
    meter_id = fields.Many2one('utility.meter', string='Meter')
    pos_order_id = fields.Many2one('pos.order', string='POS Order')
    reason = fields.Text(string='Reason', required=True)
    approved_by = fields.Many2one('res.users', string='Approved By')
    operator_id = fields.Many2one('res.users', string='Operator', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ], default='draft', string='Status', tracking=True)

    def action_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
        })

    def action_complete(self):
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError(_('The reversal must be approved before completion.'))
        self.env['utility.transaction'].create_transaction(
            'reversal', self.account_id, self.amount,
            pos_order=self.pos_order_id, reversal=self,
            notes=_('Reversal %s: %s') % (self.reference, self.reason),
        )
        if self.pos_order_id:
            self.pos_order_id.write({'reversal_id': self.id})
        self.state = 'completed'

    def action_reject(self):
        self.ensure_one()
        self.state = 'rejected'

    @api.model
    def create(self, vals):
        if vals.get('reference', _('New')) == _('New'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('utility.reversal') or _('New')
        return super().create(vals)
