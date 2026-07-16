from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UtilityMigrationCustomer(models.Model):
    _name = 'utility.migration.customer'
    _description = 'تهيئة بيانات العملاء (النظام القديم)'
    _order = 'id asc'

    name = fields.Char('الاسم', required=True)
    mobile = fields.Char('الموبايل')
    customer_number = fields.Char('رقم المشترك', required=True)
    national_id = fields.Char('الرقم الوطني')
    current_balance = fields.Float('الرصيد الحالي (الافتتاحي)')
    previous_balance = fields.Char('الرصيد السابق (الخط الساخن)')

    meter_number = fields.Char('رقم العداد')
    last_reading = fields.Float('اخر قراءة مسجلة', digits=(12, 3))

    char_code = fields.Char('رقم الحرف')
    subscriber_no = fields.Char('الرقم الجديد')
    meter_reading = fields.Integer('قراءة العداد في النظام')
    opening_reading = fields.Integer('قراءة الافتتاح')

    legacy_region = fields.Char('رمز المنطقة')
    legacy_area = fields.Char('رمز الفرع')
    legacy_category = fields.Char('رمز الفئة')
    legacy_subscriber_type = fields.Char('رمز نوع المشترك')
    legacy_contract = fields.Char('رمز قالب العقد')

    region_id = fields.Many2one('utility.region', string='المنطقة (Odoo)', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', string='الفرع (Odoo)', domain="[('type', '=', 'area')]")
    category_id = fields.Many2one('utility.subscriber.category', string='الفئة (Odoo)')
    subscriber_type_id = fields.Many2one('utility.subscriber', string='نوع المشترك (Odoo)')
    contract_template_id = fields.Many2one('utility.contract.template', string="قالب العقد (النظام)")

    phase = fields.Selection([
        ('single', '1 Phase'),
        ('three', '3 Phase')
    ], string='الطور', default='single')
    is_private_transformer = fields.Boolean(string='هل المحول خاص؟')

    is_active = fields.Boolean('هل فعال؟', default=True)

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('imported', 'تم الرفع'),
        ('error', 'خطأ')
    ], string='الحالة', default='draft')

    error_message = fields.Text('رسالة الخطأ', readonly=True)

    created_partner_id = fields.Many2one('res.partner', 'جهة الاتصال المنشأة', readonly=True)
    created_customer_id = fields.Many2one('utility.customer', 'حساب العميل المنشأ', readonly=True)
    created_meter_id = fields.Many2one('utility.meter', 'العداد المنشأ', readonly=True)
    opening_move_id = fields.Many2one('account.move', 'قيد الرصيد الافتتاحي', readonly=True)

    # -------------------------------------------------------------------------
    # Helper Actions (model-level)
    # -------------------------------------------------------------------------

    @api.model
    def action_download_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/utility_core/static/src/Migration_Template.xlsx',
            'target': 'new',
        }

    @api.model
    def action_open_import_wizard(self):
        return self.env.ref('utility_core.action_utility_migration_import_wizard').read()[0]

    @api.model
    def action_open_mapping(self):
        return self.env.ref('utility_core.action_utility_migration_mapping').read()[0]

    def action_open_customer(self):
        self.ensure_one()
        if not self.created_customer_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('حساب المشترك'),
            'res_model': 'utility.customer',
            'view_mode': 'form',
            'res_id': self.created_customer_id.id,
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
            if rec.legacy_category:
                mapping = mapping_obj.search([('mapping_type', '=', 'category'), ('legacy_code', '=', rec.legacy_category)], limit=1)
                if mapping:
                    rec.category_id = mapping.category_id.id
            if rec.legacy_subscriber_type:
                mapping = mapping_obj.search([('mapping_type', '=', 'subscriber'), ('legacy_code', '=', rec.legacy_subscriber_type)], limit=1)
                if mapping:
                    rec.subscriber_type_id = mapping.subscriber_type_id.id
            if rec.legacy_contract:
                mapping = mapping_obj.search([('mapping_type', '=', 'contract'), ('legacy_code', '=', rec.legacy_contract)], limit=1)
                if mapping:
                    rec.contract_template_id = mapping.contract_template_id.id

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _get_pec_credit(self):
        """Parse previous_balance safely."""
        self.ensure_one()
        try:
            return float(self.previous_balance) if self.previous_balance else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _build_partner_vals(self):
        """Build res.partner field values from migration record."""
        self.ensure_one()
        pec_credit = self._get_pec_credit()
        return {
            'name': self.name,
            'mobile': self.mobile,
            'national_id': self.national_id,
            'region_id': self.region_id.id,
            'area_id': self.area_id.id,
            'pec_credit': pec_credit,
            'is_credit_raised': pec_credit > 0,
            'subscriber_status': 'old',
            # تعكس حالة التفعيل الفعلية للعميل في النظام القديم
            'subscriber_active_status': 'active' if self.is_active else 'inactive',
            'char_code': self.char_code,
            'subscriber_no': self.subscriber_no,
            'meter_reading': self.meter_reading,
            'opening_reading': self.opening_reading,
            'meter_number': self.meter_number,
        }

    def _upsert_partner(self):
        """Create or update res.partner; return the partner record."""
        self.ensure_one()
        vals = self._build_partner_vals()
        partner = self.env['res.partner'].search(
            [('name', '=', self.name), ('mobile', '=', self.mobile)], limit=1
        )
        if partner:
            partner.write(vals)
        else:
            partner = self.env['res.partner'].create(vals)
        return partner

    def _create_opening_balance_entry(self, partner):
        """
        إنشاء قيد محاسبي للرصيد الافتتاحي (مدين على حساب العميل،
        دائن على حساب التسوية/حقوق الملكية).
        لا يُنشئ القيد إذا كان موجوداً أو كان الرصيد صفراً.
        """
        self.ensure_one()
        if self.opening_move_id or self.current_balance <= 0:
            return

        journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        account_receivable = partner.property_account_receivable_id
        account_suspense = (
            self.env.company.account_journal_suspense_account_id
            or self.env['account.account'].search([('account_type', '=', 'equity')], limit=1)
        )

        if not account_receivable or not account_suspense:
            raise UserError(_(
                'يجب إعداد حساب العميل (الذمم المدينة) والحساب المعلق / حقوق الملكية في النظام.'
            ))
        if not journal:
            raise UserError(_('لا توجد يومية عمليات (General Journal) معرّفة في النظام.'))

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': 'رصيد افتتاحي - %s' % self.customer_number,
            'line_ids': [
                (0, 0, {
                    'name': 'رصيد افتتاحي - %s' % self.name,
                    'partner_id': partner.id,
                    'account_id': account_receivable.id,
                    'debit': self.current_balance,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'رصيد افتتاحي - %s' % self.name,
                    'account_id': account_suspense.id,
                    'debit': 0.0,
                    'credit': self.current_balance,
                }),
            ],
        })
        move.action_post()
        self.opening_move_id = move.id

    def _create_customer_account(self, partner):
        """
        إنشاء حساب utility.customer + العداد + القراءة الافتتاحية +
        قيد الرصيد الافتتاحي للعملاء الفعالين.

        يُستدعى:
          - أثناء رفع البيانات (action_import_data) عند is_active = True.
          - عند تفعيل عميل غير فعال لاحقاً (action_activate_inactive).
        """
        self.ensure_one()

        if not self.contract_template_id:
            raise UserError(_(
                'يجب تحديد قالب العقد قبل تفعيل العميل "%s".'
            ) % self.name)
        if not self.meter_number:
            raise UserError(_(
                'يجب إدخال رقم العداد قبل تفعيل العميل "%s".'
            ) % self.name)
        if not self.category_id:
            raise UserError(_(
                'يجب تحديد فئة المشترك للعميل "%s".'
            ) % self.name)
        if not self.subscriber_type_id:
            raise UserError(_(
                'يجب تحديد نوع المشترك للعميل "%s".'
            ) % self.name)

        # 1. Create utility.customer
        customer = self.env['utility.customer'].create({
            'customer_number': self.customer_number,
            'partner_id': partner.id,
            'category_id': self.category_id.id,
            'subscriber_id': self.subscriber_type_id.id,
            'state': 'active',
            'contract_template_id': self.contract_template_id.id,
        })
        self.created_customer_id = customer.id

        # 2. Create / link meter
        meter = self.env['utility.meter'].search(
            [('meter_number', '=', self.meter_number)], limit=1
        )
        if not meter:
            meter = self.env['utility.meter'].create({
                'meter_number': self.meter_number,
                'connection_type': 'subscriber',
                'customer_id': customer.id,
                'phase': self.phase,
            })
        else:
            meter.write({
                'connection_type': 'subscriber',
                'customer_id': customer.id,
                'phase': self.phase,
            })
        self.created_meter_id = meter.id
        customer.meter_id = meter.id

        # 3. Create opening reading (state=billed so it won't be re-billed)
        if self.last_reading > 0:
            self.env['utility.reading'].create({
                'meter_id': meter.id,
                'reading_value': self.last_reading,
                'reading_date': fields.Datetime.now(),
                'reading_type': 'manual',
                'reading_category': 'customer',
                'state': 'billed',
            })

        # 4. Create opening balance journal entry
        self._create_opening_balance_entry(partner)

    # -------------------------------------------------------------------------
    # Main Actions
    # -------------------------------------------------------------------------

    def action_import_data(self):
        """
        ✅ اعتماد ورفع البيانات:

        لكل سجل في حالة مسودة:
          - يُنشئ / يُحدّث res.partner (لجميع السجلات بصرف النظر عن حالة التفعيل).
          - للعملاء الفعالين (is_active = True):
              * يُنشئ utility.customer.
              * يُنشئ / يربط utility.meter.
              * يُنشئ قراءة افتتاحية (state=billed).
              * يُنشئ قيد محاسبي للرصيد الافتتاحي (إن وُجد).
          - للعملاء غير الفعالين (is_active = False):
              * يكتفي بإنشاء res.partner فقط.
              * يمكن تفعيلهم لاحقاً عبر "تفعيل العميل" (action_activate_inactive).
        """
        for rec in self:
            if rec.state == 'imported':
                continue
            try:
                partner = rec._upsert_partner()
                rec.created_partner_id = partner.id

                if rec.is_active:
                    rec._create_customer_account(partner)

                rec.state = 'imported'
                rec.error_message = False

            except Exception as e:
                rec.state = 'error'
                rec.error_message = str(e)

    def action_activate_inactive(self):
        """
        🔄 تفعيل عميل غير فعال (Server Action):

        يُستخدم لتفعيل العملاء الذين تم رفع بياناتهم (res.partner) لكنهم
        كانوا غير فعالين (is_active = False) وقت الرفع.

        عند التفعيل يتم:
          - التحقق من اكتمال البيانات الإلزامية.
          - إنشاء utility.customer + عداد + قراءة افتتاحية + رصيد افتتاحي.
          - تحديث is_active = True على سجل التهيئة.
        """
        for rec in self:
            if rec.state != 'imported':
                raise UserError(_(
                    'يجب أن يكون السجل في حالة "تم الرفع" قبل التفعيل.\n'
                    'العميل: %s'
                ) % rec.name)

            if rec.created_customer_id:
                raise UserError(_(
                    'العميل "%s" لديه حساب مشترك بالفعل (رقم: %s).\n'
                    'لا يمكن إنشاء حساب مكرر.'
                ) % (rec.name, rec.created_customer_id.customer_number))

            if not rec.created_partner_id:
                raise UserError(_(
                    'لا توجد جهة اتصال مرتبطة بالعميل "%s".\n'
                    'يرجى إعادة رفع البيانات أولاً.'
                ) % rec.name)

            # تحديث بيانات الشريك وتعيين حالة التفعيل قبل إنشاء الحساب
            rec.created_partner_id.write(rec._build_partner_vals())

            rec._create_customer_account(rec.created_partner_id)
            rec.is_active = True
            # ضمان تحديث حالة التفعيل بعد نجاح العملية
            rec.created_partner_id.subscriber_active_status = 'active'
