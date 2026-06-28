from odoo import api, fields, models, _


class PropertyInspection(models.Model):
    _name = 'property.inspection'
    _description = 'Property Inspection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='property_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    name = fields.Char(string='Inspection Reference', required=True, index=True,
                       default=lambda self: _('New'))
    property_id = fields.Many2one('property.property', string='Property', index=True)
    building_id = fields.Many2one('property.building', string='Building', index=True)
    unit_id = fields.Many2one('property.unit', string='Unit', required=True, index=True)
    lease_id = fields.Many2one('property.lease', string='Related Lease')

    inspection_type = fields.Selection([
        ('move_in', 'Move-In'),
        ('move_out', 'Move-Out'),
        ('periodic', 'Periodic'),
        ('damage', 'Damage Assessment'),
        ('safety', 'Safety Inspection'),
    ], string='Type', required=True, default='move_in')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    date = fields.Date(string='Inspection Date', required=True, default=fields.Date.today)
    inspector_id = fields.Many2one('res.users', string='Inspector', required=True)
    tenant_id = fields.Many2one('property.tenant', string='Tenant')
    owner_id = fields.Many2one('property.owner', string='Owner')

    area_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string='Overall Condition', default='good')

    area_notes = fields.Text(string='Area Notes')
    damages_found = fields.Text(string='Damages Found')
    damage_photos = fields.One2many('property.inspection.image', 'inspection_id',
                                    string='Damage Photos', domain=[('image_type', '=', 'damage')])
    repair_estimate = fields.Monetary(string='Repair Cost Estimate', default=0.0)
    notes = fields.Text(string='Inspection Notes')

    tenant_present = fields.Boolean(string='Tenant Present')
    owner_present = fields.Boolean(string='Owner Present')
    tenant_signature = fields.Binary(string='Tenant Signature')
    inspector_signature = fields.Binary(string='Inspector Signature')

    findings_summary = fields.Html(string='Findings Summary')
    recommendations = fields.Text(string='Recommendations')

    @api.depends('inspection_type', 'unit_id')
    def _compute_name(self):
        for rec in self:
            type_label = dict(rec._fields['inspection_type'].selection).get(rec.inspection_type, '')
            rec.name = f'{type_label} - {rec.unit_id.display_name}'

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('property.inspection')
                vals['name'] = seq or '/'
        return super().create(vals_list)


class PropertyInspectionImage(models.Model):
    _name = 'property.inspection.image'
    _description = 'Inspection Image'

    inspection_id = fields.Many2one('property.inspection', string='Inspection',
                                    required=True, ondelete='cascade')
    name = fields.Char(string='Description')
    image = fields.Binary(string='Image', required=True, attachment=True)
    image_type = fields.Selection([('damage', 'Damage'), ('general', 'General')],
                                  string='Type', default='damage')
