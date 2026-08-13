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

        # 1. XML IDs Section (Checking Canonical utility_core XML IDs)
        required_xmlids = [
            ('utility_core.meter_type_subscriber', 'utility.meter.type', 'نوع عداد المشترك الأساسي'),
            ('utility_core.meter_type_feeder', 'utility.meter.type', 'نوع عداد الفيدر الأساسي'),
            ('utility_core.meter_type_transformer', 'utility.meter.type', 'نوع عداد المحول الأساسي'),
            ('utility_core.meter_status_in_service', 'utility.meter.status', 'حالة العداد في الخدمة'),
            ('utility_core.account_income_electricity', 'account.account', 'حساب إيرادات الكهرباء'),
            ('utility_core.utility_product_consumption', 'product.product', 'منتج استهلاك الكهرباء'),
            ('utility_core.utility_product_penalty', 'product.product', 'منتج الغرامات والمخالفات'),
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

        # 2. Meter Integrity & Duplicates Section
        Meter = self.env['utility.meter']

        # 2a. Duplicate meter_number
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

        # 2b. Duplicate operational_number
        duplicate_op_numbers = Meter.read_group(
            [('operational_number', '!=', False)], ['operational_number'], ['operational_number'], having=[('operational_number:count', '>', 1)])
        if duplicate_op_numbers:
            for item in duplicate_op_numbers:
                lines.append((0, 0, {
                    'section': 'meter',
                    'status': 'warning',
                    'check_name': 'فحص تكرار الرقم التشغيلي للعداد',
                    'detail': f"الرقم التشغيلي للعداد ({item['operational_number']}) مكرر في ({item['operational_number_count']}) سجلات.",
                }))
        else:
            lines.append((0, 0, {
                'section': 'meter',
                'status': 'pass',
                'check_name': 'فحص عدم تكرار الأرقام التشغيلية للعدادات',
                'detail': 'جميع الأرقام التشغيلية للعدادات فريدة كلياً.',
            }))

        # 2c. Duplicate Active Lot Assignment
        active_lot_meters = Meter.read_group(
            [('lot_id', '!=', False), ('active', '=', True)], ['lot_id'], ['lot_id'], having=[('lot_id:count', '>', 1)])
        if active_lot_meters:
            for item in active_lot_meters:
                lot = self.env['stock.lot'].browse(item['lot_id'][0])
                lines.append((0, 0, {
                    'section': 'meter',
                    'status': 'fail',
                    'check_name': 'فحص تكرار الرقم التسلسلي بين عدادات نشطة',
                    'detail': f"الرقم التسلسلي ({lot.name}) مرتبط بأكثر من عداد نشط في وقت واحد.",
                }))
        else:
            lines.append((0, 0, {
                'section': 'meter',
                'status': 'pass',
                'check_name': 'فحص توحد تعيين الأرقام التسلسلية للعدادات النشطة',
                'detail': 'كل رقم تسلسلي مادي مرتبط بعداد نشط واحد كحد أقصى.',
            }))

        # 2d. Meter / Lot Product Mismatch & Company Mismatch (High-Performance SQL Aggregates)
        self.env.cr.execute("""
            SELECT COUNT(m.id)
              FROM utility_meter m
              JOIN stock_lot l ON l.id = m.lot_id
             WHERE m.active = True
               AND m.product_id IS NOT NULL
               AND l.product_id <> m.product_id
        """)
        mismatch_count = self.env.cr.fetchone()[0]

        self.env.cr.execute("""
            SELECT COUNT(m.id)
              FROM utility_meter m
              JOIN utility_customer c ON c.id = m.customer_id
             WHERE m.active = True
               AND m.company_id IS NOT NULL
               AND c.company_id IS NOT NULL
               AND m.company_id <> c.company_id
        """)
        company_mismatch_count = self.env.cr.fetchone()[0]

        if mismatch_count > 0:
            lines.append((0, 0, {
                'section': 'meter',
                'status': 'fail',
                'check_name': 'فحص عدم تطابق منتج العداد مع الرقم التسلسلي',
                'detail': f"توجد ({mismatch_count}) عدادات يختلف منتجها عن منتج الرقم التسلسلي بالمخزون.",
            }))
        else:
            lines.append((0, 0, {
                'section': 'meter',
                'status': 'pass',
                'check_name': 'فحص مطابقة منتج العداد والرقم التسلسلي',
                'detail': 'منتجات جميع العدادات تتطابق تماماً مع الأرقام التسلسلية المربوطة بها.',
            }))

        if company_mismatch_count > 0:
            lines.append((0, 0, {
                'section': 'relation',
                'status': 'fail',
                'check_name': 'فحص تعارض الشركة بين العداد وحساب المشترك',
                'detail': f"توجد ({company_mismatch_count}) حالات يتعارض فيها رمز الشركة بين العداد وحساب المشترك.",
            }))
        else:
            lines.append((0, 0, {
                'section': 'relation',
                'status': 'pass',
                'check_name': 'فحص مطابقة شركات العدادات والمشتركين',
                'detail': 'شركات العدادات والمشتركين متطابقة بالكامل.',
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

        # 3b. Warehouse Inspection & Repair Locations Setup
        Warehouse = self.env['stock.warehouse']
        for wh in Warehouse.search([]):
            insp_loc = getattr(wh, 'meter_inspection_location_id', False)
            rep_loc = getattr(wh, 'meter_repair_location_id', False)
            if not insp_loc or not rep_loc:
                lines.append((0, 0, {
                    'section': 'stock',
                    'status': 'warning',
                    'check_name': f"فحص مواقع فحص وصيانة العدادات للمستودع: {wh.name}",
                    'detail': f"المستودع ({wh.name}) ينقصه إعداد موقع الفحص أو موقع الصيانة للعدادات.",
                }))
            else:
                lines.append((0, 0, {
                    'section': 'stock',
                    'status': 'pass',
                    'check_name': f"فحص مواقع فحص وصيانة العدادات للمستودع: {wh.name}",
                    'detail': f"مواقع الفحص والصيانة مجهزة بنجاح للمستودع ({wh.name}).",
                }))

        # 4. Billing Defaults, Accounts & Journals Section
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

            # Check Sales & Payment Journals
            journals = self.env['account.journal'].search([('company_id', '=', company.id)])
            sale_journals = journals.filtered(lambda j: j.type == 'sale')
            bank_journals = journals.filtered(lambda j: j.type in ('bank', 'cash'))
            if not sale_journals:
                lines.append((0, 0, {
                    'section': 'billing',
                    'status': 'fail',
                    'check_name': f"فحص دفاتر المبيعات للشركة: {company.name}",
                    'detail': f"لا يوجد دفتر مبيعات (Sales Journal) معرف للشركة ({company.name}).",
                }))
            else:
                lines.append((0, 0, {
                    'section': 'billing',
                    'status': 'pass',
                    'check_name': f"فحص دفاتر المبيعات للشركة: {company.name}",
                    'detail': f"دفتر المبيعات متاح وجاهز للشركة.",
                }))

            if not bank_journals:
                lines.append((0, 0, {
                    'section': 'billing',
                    'status': 'warning',
                    'check_name': f"فحص دفاتر البنك/النقدية للشركة: {company.name}",
                    'detail': f"لا يوجد دفتر بنك أو نقدية (Bank/Cash Journal) معرف للشركة ({company.name}).",
                }))

        # 5. Broken Customer / Partner Relations Section
        Customer = self.env['utility.customer']
        orphan_customers = Customer.search([('partner_id', '=', False)])
        if orphan_customers:
            lines.append((0, 0, {
                'section': 'relation',
                'status': 'fail',
                'check_name': 'فحص ارتباط حساب المشترك بالشريك المحاسبي',
                'detail': f"توجد ({len(orphan_customers)}) حسابات مشتركين غير مرتبطة بشريك محاسبي (res.partner).",
            }))
        else:
            lines.append((0, 0, {
                'section': 'relation',
                'status': 'pass',
                'check_name': 'فحص ارتباط حسابات المشتركين بالشركاء المحاسبيين',
                'detail': 'جميع حسابات المشتركين مرتبطة بشكل صحيح بالشركاء المحاسبيين.',
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
