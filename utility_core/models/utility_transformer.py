from odoo import api, fields, models


class UtilityTransformer(models.Model):
    _name = 'utility.transformer'
    _description = 'Utility Transformer'
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Transformer Name', required=True)
    code = fields.Char('Transformer Code', required=True)
    substation_id = fields.Many2one('utility.substation', 'Substation')
    feeder_id = fields.Many2one('utility.feeder', 'Feeder')
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

    # حقول خلايا المحول المدمجة
    coupling_meter_id = fields.Many2one('utility.meter', 'عداد الربط',
        domain="[('transformer_id', '=', id)]",
        help='العداد الرئيسي الذي يقيس إجمالي الطاقة الداخلة للمحول')
    cell_account_ids = fields.One2many('utility.customer', 'cell_id',
        string='عقود الخلايا/المشتركين',
        help='عقود المشتركين المغذاة من هذا المحول')
    cell_account_count = fields.Integer('عدد العقود',
        compute='_compute_cell_stats', store=True)
    total_consumption = fields.Float('إجمالي الاستهلاك (kWh)',
        compute='_compute_cell_stats', store=True,
        help='مجموع استهلاك جميع العقود التابعة للمحول في آخر دورة')
    cell_loss_kwh = fields.Float('فاقد المحول (kWh)',
        compute='_compute_cell_stats', store=True)
    loss_percentage = fields.Float('نسبة الفاقد %',
        compute='_compute_cell_stats', store=True)
    distribution_percentage = fields.Float('نسبة التوزيع %',
        default=100.0,
        help='نسبة توزيع الاستهلاك من إجمالي المحول')
    is_private = fields.Boolean('محول خاص',
        help='محول خاص بمشترك واحد أو مجموعة محدودة')
    private_account_id = fields.Many2one('utility.customer', 'الحساب الخاص',
        domain="[('cell_id', '=', id)]")
    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('unique_transformer_code_substation', 'unique(code, substation_id)',
         'Transformer code must be unique per substation!'),
    ]

    @api.depends('cell_account_ids', 'cell_account_ids.meter_id')
    def _compute_cell_stats(self):
        Reading = self.env['utility.reading']
        for rec in self:
            rec.cell_account_count = len(rec.cell_account_ids)
            total = 0.0
            for account in rec.cell_account_ids:
                last_reading = Reading.search([
                    ('account_id', '=', account.id),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                total += last_reading.consumption if last_reading else 0.0
            rec.total_consumption = total
            
            # حساب الفاقد
            if rec.coupling_meter_id:
                # البحث عن استهلاك عداد الربط
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
        """عرض عقود المحول"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'عقود المحول {self.name}',
            'res_model': 'utility.customer',
            'domain': [('cell_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_open_transformer_balance(self):
        """فتح تقرير توازن المحول"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'توازن المحول - {self.name}',
            'res_model': 'utility.transformer.balance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_transformer_id': self.id,
            },
        }
