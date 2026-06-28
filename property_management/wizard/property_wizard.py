from odoo import api, fields, models, _


class PropertyLeaseRenewWizard(models.TransientModel):
    _name = 'property.lease.renew.wizard'
    _description = 'Lease Renewal Wizard'

    lease_id = fields.Many2one('property.lease', string='Current Lease', required=True)
    new_start_date = fields.Date(string='New Start Date', required=True)
    new_end_date = fields.Date(string='New End Date', required=True)
    new_rent = fields.Monetary(string='New Rent Amount', required=True)
    increase_percent = fields.Float(string='Increase %', digits=(5, 2))
    currency_id = fields.Many2one('res.currency', related='lease_id.currency_id')

    @api.onchange('new_rent', 'increase_percent')
    def _onchange_rent(self):
        if self.increase_percent and self.lease_id.rent_amount:
            self.new_rent = self.lease_id.rent_amount * (1 + self.increase_percent / 100)

    def action_renew(self):
        self.ensure_one()
        new_lease = self.lease_id.copy({
            'name': _('New'),
            'state': 'draft',
            'lease_type': 'renewal',
            'start_date': self.new_start_date,
            'end_date': self.new_end_date,
            'rent_amount': self.new_rent,
            'schedule_ids': False,
            'payment_ids': False,
        })
        self.lease_id.write({'state': 'renewed'})
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Lease'),
            'res_model': 'property.lease',
            'view_mode': 'form',
            'res_id': new_lease.id,
        }


class PropertyPaymentRegisterWizard(models.TransientModel):
    _name = 'property.payment.register.wizard'
    _description = 'Register Payment Wizard'

    schedule_id = fields.Many2one('property.payment.schedule', string='Schedule Item',
                                  required=True)
    tenant_id = fields.Many2one('property.tenant', string='Tenant',
                                related='schedule_id.tenant_id')
    amount = fields.Monetary(string='Amount', required=True)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.today, required=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('credit_card', 'Credit Card'),
    ], string='Payment Method', default='bank_transfer', required=True)
    journal_id = fields.Many2one('account.journal', string='Payment Journal', domain="[('type', 'in', ('cash', 'bank'))]")
    reference = fields.Char(string='Reference')
    currency_id = fields.Many2one('res.currency', related='schedule_id.currency_id')

    @api.onchange('payment_method', 'schedule_id')
    def _onchange_payment_method(self):
        if self.schedule_id and self.schedule_id.lease_id and self.schedule_id.lease_id.property_id:
            property_rec = self.schedule_id.lease_id.property_id
            method = 'cash' if self.payment_method == 'cash' else 'bank'
            self.journal_id = property_rec._get_journal_for_method(method)

    def action_register(self):
        self.ensure_one()
        payment = self.env['property.payment'].create({
            'schedule_id': self.schedule_id.id,
            'lease_id': self.schedule_id.lease_id.id,
            'tenant_id': self.schedule_id.tenant_id.id,
            'unit_id': self.schedule_id.unit_id.id,
            'amount': self.amount,
            'received_amount': self.amount,
            'date': self.payment_date,
            'payment_method': self.payment_method,
            'journal_id': self.journal_id.id if self.journal_id else False,
            'reference': self.reference,
            'state': 'paid',
        })
        payment.action_paid()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
