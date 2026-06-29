from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PropertySplitBillingWizard(models.TransientModel):
    _name = 'property.split.billing.wizard'
    _description = 'Split Billing / CAM Wizard'

    property_id = fields.Many2one('property.property', string='Property', required=True)
    company_id = fields.Many2one('res.company', related='property_id.company_id')
    currency_id = fields.Many2one('res.currency', related='property_id.currency_id')

    name = fields.Char(string='Description / Bill Title', required=True, default='Shared Utility / CAM Expense')
    service_type = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('security', 'Security'),
        ('cleaning', 'Cleaning'),
        ('gardening', 'Gardening'),
        ('parking', 'Parking'),
        ('amenity', 'Amenity Fee'),
        ('management', 'Management Fee'),
        ('other', 'Other'),
    ], string='Service Type', required=True, default='maintenance')

    date = fields.Date(string='Billing Date', required=True, default=fields.Date.today)
    total_amount = fields.Monetary(string='Total Expense Amount', required=True)

    split_method = fields.Selection([
        ('equal', 'Equal Split (Per Active Tenant)'),
        ('area', 'Proportional by Unit Area (sqm)'),
    ], string='Split Method', default='equal', required=True)

    journal_id = fields.Many2one('account.journal', string='Journal', domain="[('type', '=', 'sale')]")
    notes = fields.Text(string='Notes')

    def action_generate_bills(self):
        self.ensure_one()
        if self.total_amount <= 0:
            raise UserError(_("Total expense amount must be greater than zero."))

        occupied_units = self.env['property.unit'].search([
            ('property_id', '=', self.property_id.id),
            ('current_tenant_id', '!=', False),
        ])

        if not occupied_units:
            raise UserError(_("No active tenants found in this property to split the bill."))

        total_area = sum(occupied_units.mapped('area'))
        if self.split_method == 'area' and total_area <= 0:
            raise UserError(_("Total area of occupied units is zero. Cannot split by area."))
        journal = self.journal_id or self.property_id._get_journal_for_method('rent') or self.env['account.journal'].search([('company_id', '=', self.company_id.id), ('type', '=', 'sale')], limit=1)
        if not journal or journal.type != 'sale':
            journal = self.env['account.journal'].search([('company_id', '=', self.company_id.id), ('type', '=', 'sale')], limit=1)
        income_account = self.property_id._get_service_income_account() or self.env['account.account'].search([('account_type', '=', 'income'), ('company_id', '=', self.company_id.id)], limit=1)

        created_charges = self.env['property.service.charge']

        for unit in occupied_units:
            tenant = unit.current_tenant_id
            if self.split_method == 'equal':
                tenant_amount = self.total_amount / len(occupied_units)
            else:
                tenant_amount = self.total_amount * (unit.area / total_area)

            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': tenant.partner_id.id,
                'invoice_date': self.date,
                'currency_id': self.currency_id.id,
                'journal_id': journal.id if journal else False,
                'invoice_line_ids': [(0, 0, {
                    'name': f'{self.name} ({dict(self._fields["split_method"].selection).get(self.split_method)})',
                    'quantity': 1.0,
                    'price_unit': tenant_amount,
                    'account_id': income_account.id,
                    'analytic_distribution': {str(unit.analytic_account_id.id): 100.0} if unit.analytic_account_id else False,
                })],
            })

            charge = self.env['property.service.charge'].create({
                'name': self.name,
                'property_id': self.property_id.id,
                'unit_id': unit.id,
                'tenant_id': tenant.id,
                'service_type': self.service_type,
                'amount': tenant_amount,
                'date': self.date,
                'is_recurring': False,
                'invoice_id': invoice.id,
                'notes': f'Split billing generated on {self.date} using {self.split_method} method. Total expense: {self.total_amount}.',
            })
            created_charges |= charge

        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Service Charges'),
            'res_model': 'property.service.charge',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_charges.ids)],
        }
