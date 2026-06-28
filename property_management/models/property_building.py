from odoo import api, fields, models


class PropertyBuilding(models.Model):
    _name = 'property.building'
    _description = 'Building'
    _order = 'code'
    _rec_name = 'display_name'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='property_id.company_id', store=True, index=True)
    property_id = fields.Many2one('property.property', string='Property', required=True, index=True)

    name = fields.Char(string='Building Name', required=True, translate=True)
    code = fields.Char(string='Building Code', required=True, index=True)
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    arabic_name = fields.Char(string='Arabic Name')

    floor_ids = fields.One2many('property.floor', 'building_id', string='Floors')
    unit_ids = fields.One2many('property.unit', 'building_id', string='Units')

    total_floors = fields.Integer(string='Total Floors', default=1)
    total_units = fields.Integer(string='Total Units', compute='_compute_totals', store=True)
    occupied_units = fields.Integer(string='Occupied Units', compute='_compute_totals', store=True)

    manager_id = fields.Many2one('res.users', string='Building Manager')
    year_built = fields.Integer(string='Year Built')
    total_area = fields.Float(string='Total Area (sqm)', digits=(10, 2))

    description = fields.Text(string='Description', translate=True)
    image = fields.Binary(string='Image', attachment=True)

    _sql_constraints = [
        ('building_code_property_unique', 'UNIQUE(code, property_id)', 'Building code must be unique per property!'),
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.code}] {rec.name}'

    @api.depends('unit_ids')
    def _compute_totals(self):
        for rec in self:
            rec.total_units = len(rec.unit_ids)
            rec.occupied_units = len(rec.unit_ids.filtered(
                lambda u: u.status and u.status.code == 'OCCUPIED'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                seq = self.env['ir.sequence'].next_by_code('property.building')
                vals['code'] = seq or '/'
        return super().create(vals_list)

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]
