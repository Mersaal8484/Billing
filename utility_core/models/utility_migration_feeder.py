from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityMigrationFeeder(models.Model):
    _name = 'utility.migration.feeder'
    _description = 'تهيئة بيانات الفيدرات والخلايا (النظام القديم)'
    _order = 'id asc'

    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True,
        default=lambda self: self.env.company, index=True)

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
        """مطابقة رمز المنطقة ورمز الفرع عبر ذاكرة التخزين المؤقت للشركة."""
        for rec in self:
            if rec.state == 'imported':
                continue
            company_id = rec.company_id.id or self.env.company.id
            cache = self.env['utility.migration.mapping'].get_mapping_cache(company_id)
            missing = []

            if rec.legacy_region:
                val = cache.get(('region', rec.legacy_region.strip()))
                if val:
                    rec.region_id = val.id
                else:
                    missing.append(f"MISSING_REGION_MAPPING: {rec.legacy_region}")

            if rec.legacy_area:
                val = cache.get(('area', rec.legacy_area.strip()))
                if val:
                    rec.area_id = val.id
                else:
                    missing.append(f"MISSING_AREA_MAPPING: {rec.legacy_area}")

            if missing:
                rec.error_message = "\n".join(missing)

    # -------------------------------------------------------------------------
    # Main Actions
    # -------------------------------------------------------------------------

    def action_import_data(self):
        """
        اعتماد ورفع بيانات الفيدرات والخلايا:
        - إنشاء / تحديث utility.feeder محصور بالشركة ومحدد الهوية
        - إنشاء / تحديث utility.meter وتعيين connection_type = 'feeder' و is_coupling_meter = True
        - إنشاء القراءة الافتتاحية utility.reading (state='billed' أو 'approved') بدون كتابة مباشرة للـ feeder_id الـ related
        """
        for rec in self:
            if rec.state == 'imported':
                continue
            try:
                with self.env.cr.savepoint():
                    rec.action_map_codes()
                    company_id = rec.company_id.id or self.env.company.id

                    # 1. Stable Business Identity
                    code = (rec.feeder_code or rec.legacy_analytic_id or '').strip()
                    if not code:
                        if rec.name:
                            code = rec.name.strip()
                        else:
                            raise ValidationError(_('MISSING_FEEDER_IDENTITY: يلزم توفر رمز الفيدر أو الحساب التحليلي لتحديد الهوية المرجعية.'))

                    feeder_name = rec.feeder_name or rec.name or code

                    # Search or create utility.feeder (Company-Scoped & Identity-Checked)
                    feeder = rec.created_feeder_id
                    if not feeder:
                        feeders = self.env['utility.feeder'].search([
                            ('company_id', '=', company_id),
                            ('code', '=', code),
                        ])
                        if len(feeders) > 1:
                            raise ValidationError(_('AMBIGUOUS_FEEDER_IDENTITY: تعددت الفيدرات بنفس الرمز (%s) لنفس الشركة.') % code)
                        feeder = feeders[:1]

                    feeder_vals = {
                        'name': feeder_name,
                        'code': code,
                        'notes': rec.description,
                        'company_id': company_id,
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

                    # 2. Search or create meter as a Coupling Meter (Company-Scoped)
                    meter_num = (rec.meter_number or rec.cell_meter_number or code).strip()
                    multiplier = rec.meter_multiplier or rec.cell_meter_multiplier or 1.0

                    meter = rec.created_meter_id
                    if not meter:
                        meter = self.env['utility.meter'].search([
                            ('company_id', '=', company_id),
                            ('meter_number', '=', meter_num),
                        ], limit=1)

                    status_active = self.env['utility.meter.status'].search([('code', '=', 'ACTIVE')], limit=1)

                    meter_vals = {
                        'meter_number': meter_num,
                        'multiplier': multiplier,
                        'connection_type': 'feeder',
                        'linked_feeder_id': feeder.id,
                        'company_id': company_id,
                        'payment_type': 'manual',
                        'is_coupling_meter': True,
                        'active': True,
                    }
                    if status_active:
                        meter_vals['status_id'] = status_active.id

                    if meter:
                        meter.write(meter_vals)
                    else:
                        meter = self.env['utility.meter'].create(meter_vals)

                    rec.created_meter_id = meter.id
                    feeder.write({'coupling_meter_id': meter.id})

                    # 3. Create initial/opening reading (Zero reading 0.0 is VALID!)
                    curr_val = rec.current_reading if (rec.current_reading is not False and rec.current_reading is not None) else rec.opening_reading
                    if curr_val is not False and curr_val is not None:
                        reading = rec.created_reading_id
                        if not reading:
                            reading = self.env['utility.reading'].search([
                                ('meter_id', '=', meter.id),
                                ('reading_purpose', '=', 'opening')
                            ], limit=1)

                        # Note: feeder_id is related to meter_id on utility.reading; DO NOT pass directly
                        reading_vals = {
                            'meter_id': meter.id,
                            'reading_value': float(curr_val),
                            'reading_date': fields.Datetime.now(),
                            'reading_type': 'manual',
                            'reading_purpose': 'opening',
                            'reading_event': 'normal',
                            'is_initial_reading': True,
                            'reading_category': 'feeder',
                            'reading_source': 'legacy_migration',
                            'state': 'billed',
                        }

                        if reading:
                            reading.write(reading_vals)
                        else:
                            reading = self.env['utility.reading'].create(reading_vals)

                        rec.created_reading_id = reading.id

                    rec.state = 'imported'
                    rec.error_message = False

            except Exception as e:
                rec.state = 'error'
                rec.error_message = str(e)
