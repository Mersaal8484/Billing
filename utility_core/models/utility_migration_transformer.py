from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UtilityMigrationTransformer(models.Model):
    _name = 'utility.migration.transformer'
    _description = 'تهيئة بيانات المحولات (النظام القديم)'
    _order = 'id asc'

    name = fields.Char('اسم العرض / المحول', required=True)
    legacy_region = fields.Char('رمز المنطقة')
    legacy_area = fields.Char('رمز الفرع')
    legacy_analytic_id = fields.Char('معرف الحساب التحليلي')
    is_active = fields.Boolean('هل فعال؟', default=True)

    transformer_code = fields.Char('رمز المحول / الحساب التحليلي')
    transformer_name = fields.Char('اسم المحول / الشريك')
    reference = fields.Char('المرجع / كود المحول الفيدر')
    description = fields.Text('الوصف')

    meter_number = fields.Char('رقم العداد (عداد رصد المحول)')
    meter_multiplier = fields.Float('معامل الضرب للعداد', default=1.0)
    current_reading = fields.Float('القراءة الحالية', digits=(12, 3))
    total_consumption = fields.Float('إجمالي الاستهلاك', digits=(12, 3))
    image_status = fields.Char('حالة الصورة')
    opening_reading = fields.Float('قراءة بداية الاشتراك', digits=(12, 3))

    is_calculation_cell = fields.Boolean('خلية إحتساب', default=False)

    cell_meter_multiplier = fields.Float('الخلية / معامل الضرب للعداد', default=1.0)
    cell_meter_number = fields.Char('الخلية / رقم العداد')

    region_id = fields.Many2one('utility.region', string='المنطقة (Odoo)', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', string='الفرع (Odoo)', domain="[('type', '=', 'area')]")
    feeder_id = fields.Many2one('utility.feeder', string='الفيدر / الخلية (Odoo)')

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('imported', 'تم الرفع'),
        ('error', 'خطأ')
    ], string='الحالة', default='draft')

    error_message = fields.Text('رسالة الخطأ', readonly=True)

    created_transformer_id = fields.Many2one('utility.transformer', 'المحول المنشأ', readonly=True)
    created_meter_id = fields.Many2one('utility.meter', 'العداد المنشأ', readonly=True)
    created_reading_id = fields.Many2one('utility.reading', 'القراءة الافتتاحية', readonly=True)

    # -------------------------------------------------------------------------
    # Helper Actions (model-level)
    # -------------------------------------------------------------------------

    @api.model
    def action_download_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/utility_core/static/src/Transformer_Migration_Template.xlsx',
            'target': 'new',
        }

    def action_open_transformer(self):
        self.ensure_one()
        if not self.created_transformer_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('المحول'),
            'res_model': 'utility.transformer',
            'view_mode': 'form',
            'res_id': self.created_transformer_id.id,
            'target': 'current',
        }

    def action_open_meter(self):
        self.ensure_one()
        if not self.created_meter_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('العداد'),
            'res_model': 'utility.meter',
            'view_mode': 'form',
            'res_id': self.created_meter_id.id,
            'target': 'current',
        }

    # -------------------------------------------------------------------------
    # Code Mapping
    # -------------------------------------------------------------------------

    def action_map_codes(self):
        """مطابقة رمز المنطقة والفرع عبر جدول الترميز بنفس منطق تمبلت المشتركين + مطابقة الخلية"""
        mapping_obj = self.env['utility.migration.mapping']
        feeder_obj = self.env['utility.feeder']
        meter_obj = self.env['utility.meter']

        for rec in self:
            if rec.state == 'imported':
                continue

            if rec.legacy_region:
                mapping = mapping_obj.search([('mapping_type', '=', 'region'), ('legacy_code', '=', rec.legacy_region)], limit=1)
                if mapping:
                    rec.region_id = mapping.region_id.id

            if rec.legacy_area:
                mapping = mapping_obj.search([('mapping_type', '=', 'area'), ('legacy_code', '=', rec.legacy_area)], limit=1)
                if mapping:
                    rec.area_id = mapping.area_id.id

            if rec.cell_meter_number:
                feeder = False
                m = meter_obj.search([
                    ('meter_number', '=', rec.cell_meter_number),
                    ('connection_type', '=', 'feeder')
                ], limit=1)
                if m and m.linked_feeder_id:
                    feeder = m.linked_feeder_id

                if not feeder:
                    feeder = feeder_obj.search([
                        '|', ('code', '=', rec.cell_meter_number),
                        ('name', '=like', f"%{rec.cell_meter_number}%")
                    ], limit=1)

                if feeder:
                    rec.feeder_id = feeder.id

    # -------------------------------------------------------------------------
    # Main Actions
    # -------------------------------------------------------------------------

    def action_import_data(self):
        """
        اعتماد ورفع بيانات المحولات:
        - إنشاء / تحديث utility.transformer
        - إنشاء / تحديث utility.meter وتعيين connection_type = 'transformer' و is_coupling_meter = True
        - إنشاء القراءة الافتتاحية utility.reading (state='billed')
        """
        for rec in self:
            if rec.state == 'imported':
                continue
            try:
                with self.env.cr.savepoint():
                    code = rec.reference or rec.transformer_code or rec.legacy_analytic_id or rec.name
                    trans_name = rec.transformer_name or rec.name

                    # 1. Search or create utility.transformer
                    transformer = self.env['utility.transformer'].search([
                        ('company_id', '=', self.env.company.id),
                        ('is_private', '=', False),
                        ('code', '=', code),
                    ], limit=1)

                    trans_vals = {
                        'name': trans_name,
                        'code': code,
                        'notes': rec.description,
                        'company_id': self.env.company.id,
                        'active': rec.is_active,
                    }
                    if rec.feeder_id:
                        trans_vals['feeder_id'] = rec.feeder_id.id
                    if rec.area_id:
                        trans_vals['area_id'] = rec.area_id.id
                    if rec.region_id:
                        trans_vals['region_id'] = rec.region_id.id

                    if transformer:
                        transformer.write(trans_vals)
                    else:
                        transformer = self.env['utility.transformer'].create(trans_vals)

                    rec.created_transformer_id = transformer.id

                    # 2. Search or create meter as a Coupling Meter (عداد مقارنة ورصد رئيسي)
                    meter_num = rec.meter_number or code
                    multiplier = rec.meter_multiplier or 1.0

                    meter = self.env['utility.meter'].search([
                        ('meter_number', '=', meter_num)
                    ], limit=1)

                    status_active = self.env['utility.meter.status'].search([('code', '=', 'ACTIVE')], limit=1)

                    meter_vals = {
                        'meter_number': meter_num,
                        'multiplier': multiplier,
                        'connection_type': 'transformer',
                        'linked_transformer_id': transformer.id,
                        'company_id': self.env.company.id,
                        'payment_type': 'manual',
                        'is_coupling_meter': True,  # عداد مقارنة ورصد رئيسي
                        'active': True,
                    }
                    if status_active:
                        meter_vals['status_id'] = status_active.id

                    if meter:
                        meter.write(meter_vals)
                    else:
                        meter = self.env['utility.meter'].create(meter_vals)

                    rec.created_meter_id = meter.id

                    # Set coupling meter on transformer
                    transformer.write({'coupling_meter_id': meter.id})

                    # 3. Create initial/opening reading using current_reading or opening_reading
                    curr_val = rec.current_reading or rec.opening_reading
                    if curr_val:
                        existing_reading = self.env['utility.reading'].search([
                            ('meter_id', '=', meter.id),
                            ('transformer_id', '=', transformer.id),
                            ('reading_purpose', '=', 'opening')
                        ], limit=1)

                        reading_vals = {
                            'meter_id': meter.id,
                            'transformer_id': transformer.id,
                            'feeder_id': transformer.feeder_id.id if transformer.feeder_id else False,
                            'reading_value': curr_val,
                            'reading_date': fields.Datetime.now(),
                            'reading_type': 'manual',
                            'reading_purpose': 'opening',
                            'is_initial_reading': True,
                            'reading_category': 'transformer',
                            'state': 'billed',
                        }

                        if existing_reading:
                            existing_reading.write(reading_vals)
                            reading = existing_reading
                        else:
                            reading = self.env['utility.reading'].create(reading_vals)

                        rec.created_reading_id = reading.id

                    rec.state = 'imported'
                    rec.error_message = False

            except Exception as e:
                rec.state = 'error'
                rec.error_message = str(e)
