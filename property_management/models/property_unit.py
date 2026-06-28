from odoo import api, fields, models, _


class PropertyUnit(models.Model):
    _name = 'property.unit'
    _description = 'Property Unit'
    _order = 'property_id, building_id, floor_id, number'
    _rec_name = 'display_name'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='property_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    property_id = fields.Many2one('property.property', string='Property', required=True, index=True)
    building_id = fields.Many2one('property.building', string='Building', index=True)
    floor_id = fields.Many2one('property.floor', string='Floor', index=True)

    number = fields.Char(string='Unit Number', required=True, index=True)
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    arabic_name = fields.Char(string='Arabic Name')

    unit_type = fields.Many2one('property.unit.type', string='Unit Type', required=True)
    status = fields.Many2one('property.unit.status', string='Status', required=True,
                             default=lambda self: self.env.ref('property_management.unit_status_available', raise_if_not_found=False))
    status_code = fields.Char(related='status.code', store=True)

    owner_id = fields.Many2one('property.owner', string='Owner')
    current_tenant_id = fields.Many2one('property.tenant', string='Current Tenant')
    current_lease_id = fields.Many2one('property.lease', string='Active Lease')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', tracking=True)

    area = fields.Float(string='Area (sqm)', digits=(10, 2))
    bedrooms = fields.Integer(string='Bedrooms', default=0)
    bathrooms = fields.Integer(string='Bathrooms', default=0)
    parking = fields.Integer(string='Parking Spaces', default=0)
    balcony = fields.Boolean(string='Balcony')
    garden = fields.Boolean(string='Garden')
    furnished = fields.Boolean(string='Furnished')
    furnished_type = fields.Selection([('unfurnished', 'Unfurnished'), ('semi', 'Semi-Furnished'), ('fully', 'Fully Furnished')], string='Furnishing', default='unfurnished')
    view = fields.Char(string='View')

    monthly_rent = fields.Monetary(string='Monthly Rent (Market)', currency_field='currency_id', default=0.0)
    market_value = fields.Monetary(string='Market Value', currency_field='currency_id', default=0.0)
    security_deposit = fields.Monetary(string='Security Deposit (Standard)', currency_field='currency_id', default=0.0)

    image_ids = fields.One2many('property.unit.image', 'unit_id', string='Images')
    image = fields.Binary(string='Cover Image', compute='_compute_cover_image', inverse='_inverse_cover_image')
    image_small = fields.Binary(string='Cover Image (small)')
    qr_code = fields.Char(string='QR Code')

    lease_ids = fields.One2many('property.lease', 'unit_id', string='Lease History')
    maintenance_ids = fields.One2many('property.maintenance', 'unit_id', string='Maintenance Requests')
    inspection_ids = fields.One2many('property.inspection', 'unit_id', string='Inspections')
    meter_ids = fields.One2many('property.utility', 'unit_id', string='Meters')
    document_ids = fields.One2many('property.document', 'unit_id', string='Documents')

    description = fields.Text(string='Description', translate=True)
    features = fields.Text(string='Features')
    condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('needs_renovation', 'Needs Renovation'),
    ], string='Condition', default='good')

    _sql_constraints = [
        ('unit_number_property_unique', 'UNIQUE(number, property_id, building_id)',
         'Unit number must be unique per property/building!'),
    ]

    @api.depends('number', 'building_id', 'property_id')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.building_id and rec.building_id.code:
                parts.append(str(rec.building_id.code))
            if rec.number:
                parts.append(str(rec.number))
            if not parts:
                parts.append(f"New Unit (ID: {rec.id})" if rec.id else "New Unit")
            rec.display_name = ' - '.join(parts)

    @api.depends('image_ids')
    def _compute_cover_image(self):
        for rec in self:
            first = rec.image_ids[:1]
            rec.image = first.image if first else False

    def _inverse_cover_image(self):
        for rec in self:
            if rec.image:
                if rec.image_ids:
                    rec.image_ids[0].image = rec.image
                else:
                    self.env['property.unit.image'].create({
                        'unit_id': rec.id,
                        'image': rec.image,
                        'name': 'Cover Image',
                    })

    def action_open_leases(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lease History'),
            'res_model': 'property.lease',
            'view_mode': 'tree,form',
            'domain': [('unit_id', '=', self.id)],
            'context': {'default_unit_id': self.id},
        }

    def action_open_maintenance(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance'),
            'res_model': 'property.maintenance',
            'view_mode': 'tree,form',
            'domain': [('unit_id', '=', self.id)],
            'context': {'default_unit_id': self.id},
        }

    def _create_analytic_account(self):
        for rec in self:
            if not rec.analytic_account_id:
                plan = rec.company_id.property_analytic_plan_id
                if not plan:
                    plan = self.env['account.analytic.plan'].search([], limit=1)
                if not plan:
                    plan = self.env['account.analytic.plan'].create({'name': 'Real Estate'})
                name = f"{rec.property_id.name or ''} - Unit {rec.number or ''}".strip(" - ")
                if not name:
                    name = f"Unit {rec.id or ''}"
                analytic = self.env['account.analytic.account'].create({
                    'name': name,
                    'plan_id': plan.id,
                    'company_id': rec.company_id.id or self.env.company.id,
                })
                rec.write({'analytic_account_id': analytic.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._create_analytic_account()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(not rec.analytic_account_id for rec in self):
            self._create_analytic_account()
        return res


class PropertyUnitType(models.Model):
    _name = 'property.unit.type'
    _description = 'Unit Type'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)


class PropertyUnitStatus(models.Model):
    _name = 'property.unit.status'
    _description = 'Unit Status'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)


class PropertyUnitImage(models.Model):
    _name = 'property.unit.image'
    _description = 'Unit Image'

    unit_id = fields.Many2one('property.unit', string='Unit', required=True, ondelete='cascade')
    name = fields.Char(string='Name', default='Image')
    image = fields.Binary(string='Image', required=True, attachment=True)
    sequence = fields.Integer(default=10)
