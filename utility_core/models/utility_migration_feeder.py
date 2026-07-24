from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UtilityMigrationFeeder(models.Model):
    _name = 'utility.migration.feeder'
    _description = 'تهيئة بيانات الفيدرات والخلايا (النظام القديم)'
    _order = 'id asc'

    name = fields.Char('اسم العرض / الخلية', required=True)
    legacy_region = fields.Char('رمز المنطقة')
    legacy_area = fields.Char('رمز الفرع')
    legacy_analytic_id = fields.Char('معرف الحساب التحليلي')
    is_active = fields.Boolean('هل فعال؟', default=True)

    feeder_code = fields.Char('رمز الفيدر / الحساب التحليلي')
    feeder_name = fields.Char('اسم الفيدر / الخلية')
    description = fields.Text('الوصف')

    meter_number = fields.Char('رقم العداد (عداد الفيدر)')
    meter_multiplier = fields.Float('معامل الضرب للعداد', default=1.0)
    current_reading = fields.Float('القراءة الحالية', digits=(12, 3))
    opening_reading = fields.Float('قراءة بداية الاشتراك', digits=(12, 3))

    is_calculation_cell = fields.Boolean('خلية إحتساب', default=True)

    cell_meter_multiplier = fields.Float('الخلية / معامل الضرب للعداد', default=1.0)
    cell_meter_number = fields.Char('الخلية / رقم العداد')

    region_id = fields.Many2one('utility.region', string='المنطقة (Odoo)', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', string='الفرع (Odoo)', domain="[('type', '=', 'area')]")

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('imported', 'تم الرفع'),
        ('error', 'خطأ')
    ], string='الحالة', default='draft')

    error_message = fields.Text('رسالة الخطأ', readonly=True)

    created_feeder_id = fields.Many2one('utility.feeder', 'الفيدر المنشأ', readonly=True)
    created_meter_id = fields.Many2one('utility.meter', 'العداد المنشأ', readonly=True)
    created_reading_id = fields.Many2one('utility.reading', 'القراءة الافتتاحية', readonly=True)

    # -------------------------------------------------------------------------
    # Helper Actions (model-level)
    # -------------------------------------------------------------------------

    @api.model
    def action_download_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/utility_core/static/src/Feeder_Migration_Template.xlsx',
            'target': 'new',
        }

    def action_open_feeder(self):
        self.ensure_one()
        if not self.created_feeder_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('الفيدر / الخلية'),
            'res_model': 'utility.feeder',
            'view_mode': 'form',
            'res_id': self.created_feeder_id.id,
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
        """مطابقة رمز المنطقة ورمز الفرع عبر جدول الترميز بنفس منطق تمبلت المشتركين"""
        mapping_obj = self.env['utility.migration.mapping']
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

    # -------------------------------------------------------------------------
    # Main Actions
    # -------------------------------------------------------------------------

    def action_import_data(self):
        """
        اعتماد ورفع بيانات الفيدرات والخلايا:
        - إنشاء / تحديث utility.feeder
        - إنشاء / تحديث utility.meter وتعيين connection_type = 'feeder' وربط الفيدر بها
        - إنشاء القراءة الافتتاحية utility.reading (state='billed')
        """
        for rec in self:
            if rec.state == 'imported':
                continue
            try:
                with self.env.cr.savepoint():
                    code = rec.feeder_code or rec.legacy_analytic_id or rec.name
                    feeder_name = rec.feeder_name or rec.name

                    # 1. Search or create utility.feeder
                    feeder = self.env['utility.feeder'].search([
                        '|', ('code', '=', code), ('name', '=', feeder_name)
                    ], limit=1)

                    feeder_vals = {
                        'name': feeder_name,
                        'code': code,
                        'notes': rec.description,
                        'company_id': self.env.company.id,
                        'active': rec.is_active,
                    }
                    if rec.area_id:
                        feeder_vals['area_id'] = rec.area_id.id
                    if rec.region_id:
                        feeder_vals['region_id'] = rec.region_id.id

                    if feeder:
                        feeder.write(feeder_vals)
                    else:
                        feeder = self.env['utility.feeder'].create(feeder_vals)

                    rec.created_feeder_id = feeder.id

                    # 2. Search or create meter
                    meter_num = rec.meter_number or rec.cell_meter_number or code
                    multiplier = rec.meter_multiplier or rec.cell_meter_multiplier or 1.0

                    meter = self.env['utility.meter'].search([
                        ('meter_number', '=', meter_num)
                    ], limit=1)

                    meter_vals = {
                        'meter_number': meter_num,
                        'multiplier': multiplier,
                        'connection_type': 'feeder',
                        'linked_feeder_id': feeder.id,
                        'company_id': self.env.company.id,
                        'payment_type': 'manual',
                        'active': rec.is_active,
                    }

                    if meter:
                        meter.write(meter_vals)
                    else:
                        meter = self.env['utility.meter'].create(meter_vals)

                    rec.created_meter_id = meter.id

                    # Set coupling meter on feeder
                    feeder.write({'coupling_meter_id': meter.id})

                    # 3. Create initial/opening reading using current_reading or opening_reading
                    curr_val = rec.current_reading or rec.opening_reading
                    if curr_val:
                        existing_reading = self.env['utility.reading'].search([
                            ('meter_id', '=', meter.id),
                            ('feeder_id', '=', feeder.id),
                            ('reading_purpose', '=', 'opening')
                        ], limit=1)

                        reading_vals = {
                            'meter_id': meter.id,
                            'feeder_id': feeder.id,
                            'reading_value': curr_val,
                            'reading_date': fields.Datetime.now(),
                            'reading_type': 'manual',
                            'reading_purpose': 'opening',
                            'is_initial_reading': True,
                            'reading_category': 'feeder',
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
