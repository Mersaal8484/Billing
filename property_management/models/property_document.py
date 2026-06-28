from odoo import api, fields, models


class PropertyDocument(models.Model):
    _name = 'property.document'
    _description = 'Property Document'
    _order = 'date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    name = fields.Char(string='Document Name', required=True)
    document_type = fields.Selection([
        ('title_deed', 'Title Deed'),
        ('contract', 'Contract'),
        ('lease', 'Lease Agreement'),
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt'),
        ('permit', 'Permit/License'),
        ('inspection', 'Inspection Report'),
        ('insurance', 'Insurance'),
        ('utility', 'Utility Bill'),
        ('maintenance', 'Maintenance Report'),
        ('legal', 'Legal Document'),
        ('other', 'Other'),
    ], string='Document Type', required=True, default='other')

    property_id = fields.Many2one('property.property', string='Property', index=True)
    building_id = fields.Many2one('property.building', string='Building', index=True)
    unit_id = fields.Many2one('property.unit', string='Unit', index=True)
    owner_id = fields.Many2one('property.owner', string='Owner')
    tenant_id = fields.Many2one('property.tenant', string='Tenant')
    lease_id = fields.Many2one('property.lease', string='Lease')

    file = fields.Binary(string='File', attachment=True, required=True)
    filename = fields.Char(string='Filename')
    file_size = fields.Integer(string='File Size (bytes)')
    description = fields.Text(string='Description')

    date = fields.Date(string='Date', default=fields.Date.today)
    expiry_date = fields.Date(string='Expiry Date')
    is_confidential = fields.Boolean(string='Confidential', default=False)
    is_archived = fields.Boolean(string='Archived', default=False)
    notes = fields.Text(string='Notes')
