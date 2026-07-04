from odoo import api, fields, models


class UtilityTransformer(models.Model):
    _name = 'utility.transformer'
    _description = 'محول كهرباء'
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('اسم المحول', required=True)
    code = fields.Char('رمز المحول', required=True)

    # ===== الموقع في الشبكة =====
    substation_id = fields.Many2one('utility.substation', 'Substation')
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر / الخلية', index=True)
    zone_region_id = fields.Many2one(
        'utility.region', 'المنطقة (zone)',
        domain="[('type', '=', 'zone')]",
        help='سجل المنطقة (zone) المنشأ تلقائياً في التدرج الهرمي للمناطق'
    )
    zone_id = fields.Many2one('utility.region', 'Zone', related='feeder_id.zone_id', store=True)
    area_id = fields.Many2one('utility.region', 'Area', related='zone_id.parent_id', store=True)
    region_id = fields.Many2one('utility.region', 'Region', related='zone_id.parent_id.parent_id', store=True)

    is_private = fields.Boolean(string='محول خاص', default=False, help='يُحدد ما إذا كان المحول خاصاً بمشترك واحد')

    # ===== المواصفات الفنية =====
    capacity = fields.Float('Capacity (kVA)')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='الطور')
    manufacturer = fields.Char('Manufacturer')
    serial_number = fields.Char('Serial Number')
    voltage_primary = fields.Float('Primary Voltage (V)')
    voltage_secondary = fields.Float('Secondary Voltage (V)')
    address = fields.Text('Address')
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('fault', 'Fault'),
        ('maintenance', 'Maintenance'),
    ], string='الحالة', default='active')

    # ===== الربط بالمشتركين والعدادات =====
    meter_ids = fields.One2many('utility.meter', 'transformer_id', string='العدادات')
    customer_ids = fields.One2many(
        'utility.customer', 'transformer_id',
        string='عقود المشتركين',
        help='عقود المشتركين المغذاة من هذا المحول'
    )
    customer_count = fields.Integer(
        'عدد العقود',
        compute='_compute_customer_count',
        store=True
    )

    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('unique_transformer_code_substation', 'unique(code, substation_id)',
         'Transformer code must be unique per substation!'),
    ]

    # ===== Compute =====
    @api.depends('customer_ids')
    def _compute_customer_count(self):
        for rec in self:
            rec.customer_count = len(rec.customer_ids)

    # ===== Actions =====
    def action_view_customers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'عقود {self.name}',
            'res_model': 'utility.customer',
            'domain': [('transformer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_open_transformer_balance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'توازن - {self.name}',
            'res_model': 'utility.transformer.balance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_transformer_id': self.id},
        }

    # ===== ORM Overrides =====
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.zone_region_id:
                parent = rec.area_id or rec.region_id
                zone = self.env['utility.region'].create({
                    'name': rec.name,
                    'code': rec.code,
                    'type': 'zone',
                    'parent_id': parent.id if parent else False,
                    'company_id': rec.company_id.id,
                    'transformer_origin_id': rec.id,
                })
                rec.zone_region_id = zone.id
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals or 'code' in vals:
            for rec in self:
                if rec.zone_region_id:
                    zone_vals = {}
                    if 'name' in vals:
                        zone_vals['name'] = rec.name
                    if 'code' in vals:
                        zone_vals['code'] = rec.code
                    if zone_vals:
                        rec.zone_region_id.write(zone_vals)
        return res

    def unlink(self):
        zones = self.env['utility.region']
        for rec in self:
            if rec.zone_region_id:
                zones |= rec.zone_region_id
        res = super().unlink()
        if zones:
            zones.unlink()
        return res
