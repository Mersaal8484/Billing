from odoo import api, fields, models, _


class UtilityMeterIntegrityIssue(models.Model):
    _name = 'utility.meter.integrity.issue'
    _description = 'سجل فروقات التدقيق المخزني والمنطقي للعدادات'
    _order = 'detected_at desc, id desc'

    name = fields.Char(string='رمز التنبيه', compute='_compute_name', store=True)
    meter_id = fields.Many2one('utility.meter', string='العداد', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='meter_id.company_id', string='الشركة', store=True, index=True)
    issue_type = fields.Selection([
        ('logical_installed_but_stock_available', 'منطقيًا مُركب لعميل ولكن ماديًا متاح في المخزن'),
        ('logical_unassigned_but_stock_customer', 'منطقيًا غير معين ولكن ماديًا مسجل لدى موقع عميل'),
        ('lot_missing', 'رقم تسلسلي مادي مفقود'),
        ('product_lot_mismatch', 'عدم تطابق منتج العداد مع المنتج التسلسلي'),
        ('multiple_positive_quants', 'تعدد أرصدة موجبة لنفس الرقم التسلسلي'),
        ('scrapped_but_active', 'تكهين الرقم التسلسلي بينما العداد نشط'),
        ('wrong_warehouse', 'تعارض مستودع الرخص مع المستودع الفعلي'),
    ], string='نوع الاستثناء / الفرق', required=True, index=True)
    severity = fields.Selection([
        ('info', 'معلومات'),
        ('warning', 'تحذير'),
        ('critical', 'حرج'),
    ], string='مستوى الأهمية', default='warning', required=True)
    detected_at = fields.Datetime(string='تاريخ الاكتشاف', default=fields.Datetime.now, required=True, index=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='المستودع', index=True)
    lot_id = fields.Many2one('stock.lot', string='الرقم التسلسلي', index=True)
    physical_location_id = fields.Many2one('stock.location', string='الموقع المخزني الفعلي', index=True)
    logical_customer_id = fields.Many2one('utility.customer', string='العميل المنطقي المعين', index=True)
    message = fields.Text(string='تفاصيل المشكلة والتحليل', required=True)
    resolved = fields.Boolean(string='تم المعالجة والمراجعة', default=False, index=True)
    resolved_at = fields.Datetime(string='تاريخ المعالجة')
    resolved_by_id = fields.Many2one('res.users', string='تمت المعالجة بواسطة')

    @api.depends('meter_id', 'issue_type', 'detected_at')
    def _compute_name(self):
        for rec in self:
            date_str = fields.Date.to_string(rec.detected_at.date()) if rec.detected_at else ''
            rec.name = f"ALIGN-{rec.issue_type}-{rec.meter_id.meter_number or rec.meter_id.id}-{date_str}"

    def action_mark_resolved(self):
        self.write({
            'resolved': True,
            'resolved_at': fields.Datetime.now(),
            'resolved_by_id': self.env.uid,
        })
