from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityFeeder(models.Model):
    _name = 'utility.feeder'
    _description = 'Utility Feeder (Cell)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('اسم الفيدر / الخلية', required=True, tracking=True)
    code = fields.Char('الرمز', required=True)

    # ===== الموقع في الشبكة =====
    zone_id = fields.Many2one('utility.region', 'Zone', domain="[('type', '=', 'zone')]")
    area_id = fields.Many2one('utility.region', 'Area', related='zone_id.parent_id', store=True)
    region_id = fields.Many2one('utility.region', 'Region', related='zone_id.parent_id.parent_id', store=True)
    substation_id = fields.Many2one('utility.substation', 'Substation')

    # ===== المواصفات الكهربائية =====
    voltage_level = fields.Selection([
        ('lv', 'جهد منخفض (LV)'),
        ('mv', 'جهد متوسط (MV)'),
        ('hv', 'جهد عالي (HV)'),
    ], string='مستوى الجهد')
    rated_capacity = fields.Float('الطاقة الاسمية (kVA)')
    current_load = fields.Float('الحمل الحالي (kVA)')
    load_percentage = fields.Float('نسبة التحميل %', compute='_compute_load_percentage', store=True)

    # ===== العدادات =====
    coupling_meter_id = fields.Many2one(
        'utility.meter', 'عداد الربط الرئيسي',
        domain="[('feeder_id', '=', id)]",
        help='العداد الذي يقيس إجمالي الطاقة الداخلة للفيدر/الخلية',
        tracking=True,
    )
    comparison_meter_ids = fields.Many2many(
        'utility.meter',
        'feeder_comparison_meter_rel',
        'feeder_id', 'meter_id',
        string='عدادات المقارنة',
        domain="[('feeder_id', '=', id)]",
        help='العدادات المستخدمة للمقارنة وكشف الفاقد',
    )
    transformer_ids = fields.One2many('utility.transformer', 'feeder_id', string='المحولات')
    meter_ids = fields.One2many('utility.meter', 'feeder_id', string='جميع العدادات')

    # ===== القراءات =====
    coupling_reading_ids = fields.One2many(
        'utility.reading', 'feeder_id',
        string='قراءات الربط',
        domain=[('reading_category', 'in', ['feeder', 'transformer'])],
    )
    feeder_reading_ids = fields.One2many(
        'utility.reading', 'feeder_id',
        string='قراءات الفيدر',
        domain=[('reading_category', '=', 'feeder')],
    )

    # ===== المشتركون (الخلية) =====
    cell_account_ids = fields.One2many(
        'utility.customer', 'cell_id',
        string='عقود المشتركين',
        help='عقود المشتركين المغذاة مباشرة من الفيدر/الخلية'
    )

    # ===== الأرصدة والفاقد =====
    customer_count = fields.Integer(
        'عدد المشتركين',
        compute='_compute_feeder_stats', store=True
    )
    total_consumption = fields.Float(
        'إجمالي استهلاك المشتركين (kWh)',
        compute='_compute_feeder_stats', store=True
    )
    supplied_kwh = fields.Float(
        'الطاقة المزوّدة (kWh)',
        compute='_compute_feeder_stats', store=True
    )
    loss_kwh = fields.Float(
        'الفاقد (kWh)',
        compute='_compute_feeder_stats', store=True
    )
    loss_percentage = fields.Float(
        'نسبة الفاقد %',
        compute='_compute_feeder_stats', store=True
    )

    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('unique_feeder_code_zone', 'unique(code, zone_id)', 'رمز الفيدر يجب أن يكون فريداً داخل نفس المنطقة!'),
    ]

    # ===== Compute =====
    @api.depends('current_load', 'rated_capacity')
    def _compute_load_percentage(self):
        for r in self:
            if r.rated_capacity:
                r.load_percentage = (r.current_load / r.rated_capacity) * 100.0
            else:
                r.load_percentage = 0.0

    @api.depends('cell_account_ids', 'coupling_reading_ids.consumption')
    def _compute_feeder_stats(self):
        Reading = self.env.get('utility.reading')
        for rec in self:
            customers = rec.cell_account_ids
            rec.customer_count = len(customers)

            total = 0.0
            if Reading:
                for customer in customers:
                    last = Reading.search([
                        ('account_id', '=', customer.id),
                        ('state', 'in', ['approved', 'billed']),
                    ], order='reading_date desc', limit=1)
                    total += last.consumption if last else 0.0
            rec.total_consumption = total

            last_coupling = rec.coupling_reading_ids.filtered(
                lambda r: r.state == 'approved'
            )[:1]
            supplied = last_coupling.consumption if last_coupling else 0.0
            rec.supplied_kwh = supplied
            rec.loss_kwh = max(supplied - total, 0.0)
            rec.loss_percentage = (rec.loss_kwh / supplied * 100) if supplied > 0 else 0.0

    # ===== Actions =====
    def action_view_customers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('مشتركو %s') % self.name,
            'res_model': 'utility.customer',
            'domain': [('cell_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_readings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('قراءات %s') % self.name,
            'res_model': 'utility.reading',
            'domain': [('feeder_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
            'context': {
                'default_feeder_id': self.id,
                'default_reading_category': 'feeder',
            },
        }
