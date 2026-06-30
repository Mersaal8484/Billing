from odoo import api, fields, models


class UtilityTransformer(models.Model):
    _name = 'utility.transformer'
    _description = 'Utility Transformer / Cell'
    _order = 'name'
    _parent_store = True
    _parent_name = 'parent_id'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Transformer Name', required=True)
    code = fields.Char('Transformer Code', required=True)

    is_cell = fields.Boolean('خلية', default=False,
        help='الخلية هي كيان تنظيمي يضم عدة محولات')
    parent_id = fields.Many2one('utility.transformer', 'الخلية الأم',
        index=True, ondelete='cascade',
        domain="[('is_cell', '=', True)]",
        help='الخلية التي ينتمي إليها هذا المحول')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('utility.transformer', 'parent_id',
        string='المحولات التابعة',
        domain=[('is_cell', '=', False)])

    substation_id = fields.Many2one('utility.substation', 'Substation')
    feeder_id = fields.Many2one('utility.feeder', 'Feeder')
    zone_region_id = fields.Many2one('utility.region', 'المنطقة (zone)',
        domain="[('type', '=', 'zone')]",
        help='سجل المنطقة (zone) المنشأ تلقائياً في التدرج الهرمي للمناطق')
    zone_id = fields.Many2one('utility.region', 'Zone', related='feeder_id.zone_id', store=True)
    area_id = fields.Many2one('utility.region', 'Area', related='zone_id.parent_id', store=True)
    region_id = fields.Many2one('utility.region', 'Region', related='zone_id.parent_id.parent_id', store=True)
    capacity = fields.Float('Capacity (kVA)')
    phase = fields.Selection([
        ('single', 'Single Phase'),
        ('three', 'Three Phase'),
    ], string='Phase')
    manufacturer = fields.Char('Manufacturer')
    serial_number = fields.Char('Serial Number')
    voltage_primary = fields.Float('Primary Voltage (V)')
    voltage_secondary = fields.Float('Secondary Voltage (V)')
    gps_latitude = fields.Float('GPS Latitude')
    gps_longitude = fields.Float('GPS Longitude')
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('fault', 'Fault'),
        ('maintenance', 'Maintenance'),
    ], string='Status', default='active')
    meter_ids = fields.One2many('utility.meter', 'transformer_id', string='Meters')

    # حقول الخلايا (لمن is_cell=True)
    coupling_meter_id = fields.Many2one('utility.meter', 'عداد الربط',
        domain="[('transformer_id', '=', id)]",
        help='العداد الرئيسي الذي يقيس إجمالي الطاقة الداخلة للخلية/المحول')
    comparison_meter_id = fields.Many2one('utility.meter', 'عداد المقارنة',
        domain="[('transformer_id', '=', id)]",
        help='العداد المستخدم للمقارنة مع العداد الرئيسي أو الفاقد')
    coupling_meter_ids = fields.Many2many('utility.meter', compute='_compute_coupling_meter_ids', string='عدادات الربط')

    @api.depends('coupling_meter_id', 'comparison_meter_id')
    def _compute_coupling_meter_ids(self):
        for rec in self:
            meters = self.env['utility.meter']
            if rec.coupling_meter_id:
                meters |= rec.coupling_meter_id
            if rec.comparison_meter_id:
                meters |= rec.comparison_meter_id
            rec.coupling_meter_ids = [(6, 0, meters.ids)] if meters else False
    cell_account_ids = fields.One2many('utility.customer', 'cell_id',
        string='عقود المشتركين',
        help='عقود المشتركين المغذاة من هذه الخلية/المحول')
    cell_account_count = fields.Integer('عدد العقود',
        compute='_compute_cell_stats', store=True)
    total_consumption = fields.Float('إجمالي الاستهلاك (kWh)',
        compute='_compute_cell_stats', store=True)
    cell_loss_kwh = fields.Float('فاقد (kWh)',
        compute='_compute_cell_stats', store=True)
    loss_percentage = fields.Float('نسبة الفاقد %',
        compute='_compute_cell_stats', store=True)
    distribution_percentage = fields.Float('نسبة التوزيع %',
        default=100.0)
    is_private = fields.Boolean('خاص',
        help='خلية/محول خاص بمشترك واحد أو مجموعة محدودة')
    private_account_id = fields.Many2one('utility.customer', 'الحساب الخاص',
        domain="[('cell_id', '=', id)]")
    coupling_reading_ids = fields.One2many(
        'utility.transformer.reading', 'transformer_id',
        string='قراءات الربط',
        domain=[('reading_type', '=', 'coupling')])
    cell_reading_ids = fields.One2many(
        'utility.transformer.reading', 'transformer_id',
        string='قراءات الخلايا',
        domain=[('reading_type', '=', 'cell')])

    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('unique_transformer_code_substation', 'unique(code, substation_id)',
         'Transformer code must be unique per substation!'),
    ]

    @api.depends('cell_account_ids', 'cell_account_ids.meter_id', 'child_ids.cell_account_ids')
    def _compute_cell_stats(self):
        Reading = self.env.get('utility.reading')
        for rec in self:
            accounts = rec.cell_account_ids
            if rec.is_cell:
                for child in rec.child_ids:
                    accounts |= child.cell_account_ids
            rec.cell_account_count = len(accounts)
            total = 0.0
            if Reading:
                for account in accounts:
                    last_reading = Reading.search([
                        ('account_id', '=', account.id),
                        ('state', 'in', ['approved', 'billed']),
                    ], order='reading_date desc', limit=1)
                    total += last_reading.consumption if last_reading else 0.0
            rec.total_consumption = total
            
            if rec.coupling_meter_id and Reading:
                last_coupling_reading = Reading.search([
                    ('meter_id', '=', rec.coupling_meter_id.id),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                supplied = last_coupling_reading.consumption if last_coupling_reading else 0.0
                rec.cell_loss_kwh = supplied - total
                rec.loss_percentage = (rec.cell_loss_kwh / supplied) * 100 if supplied > 0 else 0.0
            else:
                rec.cell_loss_kwh = 0.0
                rec.loss_percentage = 0.0

    def action_view_cell_accounts(self):
        self.ensure_one()
        domain = [('cell_id', 'child_of', self.id)]
        return {
            'type': 'ir.actions.act_window',
            'name': f'عقود {self.name}',
            'res_model': 'utility.customer',
            'domain': domain,
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
            'context': {
                'default_transformer_id': self.id,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.is_cell and not rec.zone_region_id:
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
