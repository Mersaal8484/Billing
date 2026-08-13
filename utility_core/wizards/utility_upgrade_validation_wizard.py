from odoo import api, fields, models, _


class UtilityUpgradeValidationWizard(models.TransientModel):
    _name = 'utility.upgrade.validation.wizard'
    _description = 'معالج التدقيق الشامل والفحص الفني بعد الترقية'

    pass_count = fields.Integer(string='عدد الفحوصات الناجحة (PASS)', readonly=True)
    warning_count = fields.Integer(string='عدد التحذيرات (WARNING)', readonly=True)
    fail_count = fields.Integer(string='عدد الأخطاء المحرجة (FAIL)', readonly=True)
    status_summary = fields.Selection([
        ('pass', 'PASS - الترقية والنظام سليم تماماً'),
        ('warning', 'WARNING - توجد تحذيرات تشغيلية غير حرجة'),
        ('fail', 'FAIL - توجد أخطاء محرجة تمنع التشغيل'),
    ], string='النتيجة الإجمالية', readonly=True)

    line_ids = fields.One2many(
        'utility.upgrade.validation.line', 'wizard_id', string='تفاصيل الفحوصات والنتائج', readonly=True)

    def action_run_validation(self):
        self.ensure_one()
        self.line_ids.unlink()
        lines = []

        # 1. XML IDs Section
        required_xmlids = [
            ('utility_core.meter_type_subscriber', 'utility.meter.type', 'نوع عداد المشترك الأساسي'),
            ('utility_core.meter_type_feeder', 'utility.meter.type', 'نوع عداد الفيدر الأساسي'),
            ('utility_core.meter_type_transformer', 'utility.meter.type', 'نوع عداد المحول الأساسي'),
            ('utility_core.meter_status_in_service', 'utility.meter.status', 'حالة العداد في الخدمة'),
            ('utility_billing.account_income_electricity', 'account.account', 'حساب إيرادات الكهرباء'),
            ('utility_billing.utility_product_consumption', 'product.product', 'منتج استهلاك الكهرباء'),
            ('utility_billing.utility_product_penalty', 'product.product', 'منتج الغرامات والمخالفات'),
        ]

        for xmlid, expected_model, label in required_xmlids:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if not record:
                lines.append((0, 0, {
                    'section': 'xmlid',
                    'status': 'fail',
                    'check_name': f"فحص الـ XML ID: {xmlid}",
                    'detail': f"الـ External ID المرجعي ({xmlid}) غير موجود بالنظام ({label}).",
                }))
            elif record._name != expected_model:
                lines.append((0, 0, {
                    'section': 'xmlid',
                    'status': 'fail',
                    'check_name': f"فحص مطابقة نموذج الـ XML ID: {xmlid}",
                    'detail': f"الـ External ID المرجعي ({xmlid}) يشير إلى النموذج ({record._name}) بينما المتوقع ({expected_model}).",
                }))
            else:
                lines.append((0, 0, {
                    'section': 'xmlid',
                    'status': 'pass',
                    'check_name': f"فحص الـ XML ID: {xmlid}",
                    'detail': f"تمت المطابقة بنجاح للسجل ({record.display_name}).",
                }))

        # 2. Meter Integrity Section
        Meter = self.env['utility.meter']
        duplicate_numbers = Meter.read_group(
            [('meter_number', '!=', False)], ['meter_number'], ['meter_number'], having=[('meter_number:count', '>', 1)])
        if duplicate_numbers:
            for item in duplicate_numbers:
                lines.append((0, 0, {
                    'section': 'meter',
                    'status': 'warning',
                    'check_name': 'فحص تكرار رقم العداد',
                    'detail': f"رقم العداد ({item['meter_number']}) مكرر في ({item['meter_number_count']}) سجلات.",
                }))
        else:
            lines.append((0, 0, {
                'section': 'meter',
                'status': 'pass',
                'check_name': 'فحص عدم تكرار أرقام العدادات',
                'detail': 'جميع أرقام العدادات المسجلة فريدة كلياً.',
            }))

        # 3. Stock Integrity Section
        Quant = self.env['stock.quant']
        duplicate_serial_quants = Quant.read_group(
            [('lot_id', '!=', False), ('quantity', '>', 0), ('location_id.usage', '=', 'internal')],
            ['lot_id'], ['lot_id'], having=[('lot_id:count', '>', 1)])
        if duplicate_serial_quants:
            for item in duplicate_serial_quants:
                lot = self.env['stock.lot'].browse(item['lot_id'][0])
                lines.append((0, 0, {
                    'section': 'stock',
                    'status': 'fail',
                    'check_name': 'فحص تعدد الأرصدة الموجبة للرقم التسلسلي',
                    'detail': f"الرقم التسلسلي ({lot.name}) لديه أرصدة موجبة مكررة في أكثر من موقع مخزني داخلي.",
                }))
        else:
            lines.append((0, 0, {
                'section': 'stock',
                'status': 'pass',
                'check_name': 'فحص توحد الأرصدة التسلسلية الموجبة',
                'detail': 'لا توجد أرصدة موجبة مكررة لأي رقم تسلسلي مادي.',
            }))

        # 4. Billing Defaults Section
        Company = self.env['res.company']
        for company in Company.search([]):
            if not getattr(company, 'penalty_product_id', False):
                lines.append((0, 0, {
                    'section': 'billing',
                    'status': 'warning',
                    'check_name': f"فحص إعدادات الفوترة للشركة: {company.name}",
                    'detail': f"منتج الغرامات الافتراضي (penalty_product_id) غير معين للشركة ({company.name}).",
                }))
            else:
                lines.append((0, 0, {
                    'section': 'billing',
                    'status': 'pass',
                    'check_name': f"فحص إعدادات الفوترة للشركة: {company.name}",
                    'detail': f"جميع منتجات الفوترة والغرامات الافتراضية معينة بنجاح للشركة.",
                }))

        # Calculate Summary Metrics
        p_cnt = sum(1 for _, _, l in lines if l['status'] == 'pass')
        w_cnt = sum(1 for _, _, l in lines if l['status'] == 'warning')
        f_cnt = sum(1 for _, _, l in lines if l['status'] == 'fail')

        summary = 'fail' if f_cnt > 0 else ('warning' if w_cnt > 0 else 'pass')

        self.write({
            'line_ids': lines,
            'pass_count': p_cnt,
            'warning_count': w_cnt,
            'fail_count': f_cnt,
            'status_summary': summary,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class UtilityUpgradeValidationLine(models.TransientModel):
    _name = 'utility.upgrade.validation.line'
    _description = 'سطر نتيجة فحص الترقية'

    wizard_id = fields.Many2one('utility.upgrade.validation.wizard', ondelete='cascade')
    section = fields.Selection([
        ('xmlid', 'الـ XML IDs والبيانات المرجعية'),
        ('meter', 'سجلات العدادات والهوية'),
        ('stock', 'الأرصدة والمخزون المادي'),
        ('billing', 'إعدادات الفوترة والحسابات'),
        ('relation', 'العلاقات والشركات'),
    ], string='قسم الفحص', required=True)
    status = fields.Selection([
        ('pass', 'PASS'),
        ('warning', 'WARNING'),
        ('fail', 'FAIL'),
    ], string='نتيجة الفحص', required=True)
    check_name = fields.Char(string='اسم الفحص', required=True)
    detail = fields.Text(string='تفاصيل النتيجة', required=True)
