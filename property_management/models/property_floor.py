from odoo import api, fields, models


class PropertyFloor(models.Model):
    _name = 'property.floor'
    _description = 'Floor'
    _order = 'building_id, number'
    _rec_name = 'display_name'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='building_id.company_id', store=True, index=True)
    property_id = fields.Many2one('property.property', related='building_id.property_id', store=True, index=True)
    building_id = fields.Many2one('property.building', string='Building', required=True, index=True)

    name = fields.Char(string='Floor Name', required=True, translate=True)
    code = fields.Char(string='Floor Code', required=True, index=True)
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    number = fields.Integer(string='Floor Number', default=1)

    unit_ids = fields.One2many('property.unit', 'floor_id', string='Units')
    total_units = fields.Integer(string='Units', compute='_compute_unit_count', store=True)
    total_area = fields.Float(string='Area (sqm)', digits=(10, 2))

    _sql_constraints = [
        ('floor_code_building_unique', 'UNIQUE(code, building_id)', 'Floor code must be unique per building!'),
    ]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.name} ({rec.code})'

    @api.depends('unit_ids')
    def _compute_unit_count(self):
        for rec in self:
            rec.total_units = len(rec.unit_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                seq = self.env['ir.sequence'].next_by_code('property.floor')
                vals['code'] = seq or '/'
        return super().create(vals_list)
