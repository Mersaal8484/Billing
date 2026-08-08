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
        vals = {
            'name': self.name,
            'mobile': self.mobile,
            'national_id': self.national_id,
            'region_id': self.region_id.id if self.region_id else False,
            'area_id': self.area_id.id if self.area_id else False,
            'pec_credit': pec_credit,
            'is_credit_raised': True if (pec_credit > 0 or self.current_balance != 0) else False,
            'credit_raise_date': fields.Date.today() if (pec_credit > 0 or self.current_balance != 0) else False,
            'open_balance': self.current_balance,
            'subscriber_status': 'old',
            'is_subscriber': True,
            # تعكس حالة التفعيل الفعلية للعميل في النظام القديم
            'subscriber_active_status': 'active' if self.is_active else 'inactive',
            'char_code': self.char_code,
            'subscriber_no': self.subscriber_no or self.customer_number,
            'meter_reading': self.meter_reading or int(self.last_reading or 0),
            'opening_reading': self.opening_reading or int(self.last_reading or 0),
            'meter_number': self.meter_number,
        }
        if self.subscriber_type_id:
            vals['subscriber_id'] = self.subscriber_type_id.id
        return vals

    def _get_or_create_private_transformer(self, partner):
        """
        إنشاء أو ربط محول خاص للمشترك إذا كانت خانة (is_private_transformer) مفعّلة.
        """
        self.ensure_one()
        if not self.is_private_transformer:
            return False

        code = f"PRV-{self.customer_number or self.national_id or partner.id}"
        name = f"محول خاص - {partner.name}"

        transformer = self.env['utility.transformer'].search([
            '|', ('code', '=', code), ('name', '=', name)
        ], limit=1)

        area_or_region = self.area_id or self.region_id

        if not transformer:
            transformer = self.env['utility.transformer'].create({
                'name': name,
                'code': code,
                'phase': self.phase or 'single',
                'area_id': area_or_region.id if area_or_region and area_or_region.type == 'area' else False,
                'zone_region_id': area_or_region.id if area_or_region and area_or_region.type == 'zone' else False,
                'is_private': True,
            })
        return transformer

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

    def _create_opening_balance_entry(self, partner, customer=None):
        """
        إنشاء قيد محاسبي للرصيد الافتتاحي (مدين على حساب العميل للمديونية،
        أو دائن للرصيد الدائن المرحل).
        لا يُنشئ القيد إذا كان موجوداً أو كانت المبالغ صفراً.
        """
        self.ensure_one()
        if self.opening_move_id:
            return

        if not self.current_balance:
            return

        journal = (
            self.env.company.opening_journal_id
            or self.env['account.journal'].search([('code', '=', 'OPEN'), ('type', '=', 'general')], limit=1)
            or self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        )
        account_receivable = partner.property_account_receivable_id
        if not account_receivable:
            account_receivable = (
                self.env['account.account'].search([
                    ('account_type', '=', 'asset_receivable'),
                    ('company_id', 'in', (self.env.company.id, False))
                ], limit=1)
                or self.env['account.account'].search([
                    ('code', '=like', '12%'),
                    ('company_id', 'in', (self.env.company.id, False))
                ], limit=1)
                or self.env['account.account'].search([
                    ('name', 'ilike', 'عملاء'),
                    ('company_id', 'in', (self.env.company.id, False))
                ], limit=1)
                or self.env['account.account'].search([
                    ('account_type', 'in', ('asset_receivable', 'asset_current'))
                ], limit=1)
            )
            if not account_receivable:
                # إنشاء حساب ذمم مدينة افتراضي للشركة إن لم يوجد أي حساب مطابق
                account_receivable = self.env['account.account'].create({
                    'name': 'حساب العملاء والذمم المدينة',
                    'code': '120000',
                    'account_type': 'asset_receivable',
                    'company_id': self.env.company.id,
                    'reconcile': True,
                })
            partner.sudo().write({'property_account_receivable_id': account_receivable.id})

        account_suspense = (
            self.env.company.account_journal_suspense_account_id
            or self.env['account.account'].search([
                ('account_type', 'in', ('equity', 'equity_unaffected')),
                ('company_id', 'in', (self.env.company.id, False))
            ], limit=1)
            or self.env['account.account'].search([
                ('code', '=like', '3%'),
                ('company_id', 'in', (self.env.company.id, False))
            ], limit=1)
            or self.env['account.account'].search([
                ('name', 'ilike', 'افتتاح'),
                ('company_id', 'in', (self.env.company.id, False))
            ], limit=1)
            or self.env['account.account'].search([
                ('name', 'ilike', 'أرباح'),
                ('company_id', 'in', (self.env.company.id, False))
            ], limit=1)
            or self.env['account.account'].search([
                ('account_type', 'in', ('equity', 'equity_unaffected', 'liability_current'))
            ], limit=1)
        )
        if not account_suspense:
            # إنشاء حساب الأرصدة الافتتاحية المعلق افتراضي إن لم يوجد أي حساب مطابق
            account_suspense = self.env['account.account'].create({
                'name': 'حساب الأرصدة الافتتاحية (حقوق ملكية)',
                'code': '300000',
                'account_type': 'equity',
                'company_id': self.env.company.id,
            })
        if not journal:
            raise UserError(_('لا توجد يومية عمليات (General Journal) معرّفة في النظام.'))

        line_ids = []
        
        # 1. الرصيد الحالي (إذا كان الرصيد موجباً: مدين للعميل، وإذا كان سالباً: دائن للعميل)
        if self.current_balance > 0:
            line_ids.append((0, 0, {
                'name': 'رصيد افتتاح مديونية - %s' % self.name,
                'partner_id': partner.id,
                'account_id': account_receivable.id,
                'debit': self.current_balance,
                'credit': 0.0,
            }))
            line_ids.append((0, 0, {
                'name': 'رصيد افتتاح مديونية - %s' % self.name,
                'account_id': account_suspense.id,
                'debit': 0.0,
                'credit': self.current_balance,
            }))
        elif self.current_balance < 0:
            credit_amount = abs(self.current_balance)
            line_ids.append((0, 0, {
                'name': 'رصيد افتتاح دائن - %s' % self.name,
                'account_id': account_suspense.id,
                'debit': credit_amount,
                'credit': 0.0,
            }))
            line_ids.append((0, 0, {
                'name': 'رصيد افتتاح دائن - %s' % self.name,
                'partner_id': partner.id,
                'account_id': account_receivable.id,
                'debit': 0.0,
                'credit': credit_amount,
            }))

        if line_ids:
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'ref': 'رصيد افتتاحي - %s' % self.customer_number,
                'line_ids': line_ids,
            })
            move.action_post()
            self.opening_move_id = move.id
            if customer:
                customer.opening_move_id = move.id
            partner.write({
                'is_credit_raised': True,
                'credit_raise_date': fields.Date.today(),
            })

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

        # 0. Private Transformer
        transformer = self._get_or_create_private_transformer(partner)

        # 1. Create or update utility.customer
        company_id = self.env.company.id
        customer = self.env['utility.customer'].search([
            ('customer_number', '=', self.customer_number),
            ('company_id', '=', company_id)
        ], limit=1)

        customer_vals = {
            'customer_number': self.customer_number,
            'partner_id': partner.id,
            'category_id': self.category_id.id,
            'subscriber_id': self.subscriber_type_id.id,
            'state': 'active',
            'contract_template_id': self.contract_template_id.id,
            'company_id': company_id,
        }
        if transformer:
            customer_vals['transformer_id'] = transformer.id
            if transformer.feeder_id:
                customer_vals['cell_id'] = transformer.feeder_id.id

        if customer:
            customer.with_context(skip_opening_entry=True).write(customer_vals)
        else:
            customer = self.env['utility.customer'].with_context(skip_opening_entry=True).create(customer_vals)

        self.created_customer_id = customer.id

        # 2. Create / link meter
        status_active = self.env['utility.meter.status'].search([('code', '=', 'ACTIVE')], limit=1)
        meter_vals = {
            'meter_number': self.meter_number,
            'connection_type': 'subscriber',
            'customer_id': customer.id,
            'phase': self.phase,
            'active': True,
        }
        if status_active:
            meter_vals['status_id'] = status_active.id
        if transformer:
            meter_vals['transformer_id'] = transformer.id
            if transformer.feeder_id:
                meter_vals['feeder_id'] = transformer.feeder_id.id

        meter = self.env['utility.meter'].search(
            [('meter_number', '=', self.meter_number)], limit=1
        )
        if not meter:
            meter = self.env['utility.meter'].create(meter_vals)
        else:
            meter.write(meter_vals)

        self.created_meter_id = meter.id
        customer.meter_id = meter.id

        if transformer and meter:
            transformer.write({'coupling_meter_id': meter.id})

        # 3. Create opening reading (state=billed so it won't be re-billed)
        if self.last_reading > 0:
            existing_reading = self.env['utility.reading'].search([
                ('meter_id', '=', meter.id),
                ('reading_purpose', '=', 'opening')
            ], limit=1)
            if not existing_reading:
                self.env['utility.reading'].create({
                    'meter_id': meter.id,
                    'reading_value': self.last_reading,
                    'reading_date': fields.Datetime.now(),
                    'reading_type': 'manual',
                    'reading_purpose': 'opening',
                    'is_initial_reading': True,
                    'reading_category': 'customer',
                    'state': 'billed',
                })
            else:
                existing_reading.write({
                    'reading_value': self.last_reading,
                })

        # 4. Create opening balance journal entry
        self._create_opening_balance_entry(partner, customer)

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
                with self.env.cr.savepoint():
                    partner = rec._upsert_partner()
                    rec.created_partner_id = partner.id

                    if rec.is_active:
                        rec.with_context(skip_service_activation_charge=True)._create_customer_account(partner)

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

            # مزامنة أي تعديلات يدوية قام بها المستخدم على بطاقة جهة الاتصال (مثل الرصيد، رقم العداد) إلى سجل التهيئة
            partner = rec.created_partner_id
            rec.write({
                 'meter_number': partner.meter_number or rec.meter_number,
                 'meter_reading': partner.meter_reading or rec.meter_reading,
                 'opening_reading': partner.opening_reading or rec.opening_reading,
                 'previous_balance': str(partner.pec_credit) if partner.pec_credit else rec.previous_balance,
                 'current_balance': partner.open_balance if partner.open_balance else rec.current_balance,
                 'customer_number': partner.subscriber_no or rec.customer_number,
                 'name': partner.name or rec.name,
                 'mobile': partner.mobile or rec.mobile,
                 'national_id': partner.national_id or rec.national_id,
            })

            # تحديث بيانات الشريك وتعيين حالة التفعيل قبل إنشاء الحساب
            partner.write(rec._build_partner_vals())

            rec._create_customer_account(partner)
            rec.is_active = True
            # ضمان تحديث حالة التفعيل بعد نجاح العملية
            partner.subscriber_active_status = 'active'
