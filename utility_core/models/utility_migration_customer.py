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
    
    def action_map_codes(self):
        mapping_obj = self.env['utility.migration.mapping']
        
        for rec in self:
            if rec.state == 'imported':
                continue
                
            if rec.legacy_region:
                mapping = mapping_obj.search([('mapping_type', '=', 'region'), ('legacy_code', '=', rec.legacy_region)], limit=1)
                if mapping: rec.region_id = mapping.region_id.id
                
            if rec.legacy_area:
                mapping = mapping_obj.search([('mapping_type', '=', 'area'), ('legacy_code', '=', rec.legacy_area)], limit=1)
                if mapping: rec.area_id = mapping.area_id.id
                
            if rec.legacy_category:
                mapping = mapping_obj.search([('mapping_type', '=', 'category'), ('legacy_code', '=', rec.legacy_category)], limit=1)
                if mapping: rec.category_id = mapping.category_id.id
                
            if rec.legacy_subscriber_type:
                mapping = mapping_obj.search([('mapping_type', '=', 'subscriber'), ('legacy_code', '=', rec.legacy_subscriber_type)], limit=1)
                if mapping: rec.subscriber_type_id = mapping.subscriber_type_id.id
                
            if rec.legacy_contract:
                mapping = mapping_obj.search([('mapping_type', '=', 'contract'), ('legacy_code', '=', rec.legacy_contract)], limit=1)
                if mapping: rec.contract_template_id = mapping.contract_template_id.id
    
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

    def action_import_data(self):
        for rec in self:
            if rec.state == 'imported':
                continue
                
            try:
                # 1. Validation
                if rec.is_active:
                    if not rec.meter_number:
                        raise UserError(_('يجب إدخال رقم العداد للعميل الفعال.'))
                    if not rec.contract_template_id:
                        raise UserError(_('يجب تحديد قالب العقد للعميل الفعال.'))

                # 2. Create Partner
                partner = self.env['res.partner'].search([('name', '=', rec.name), ('mobile', '=', rec.mobile)], limit=1)
                if not partner:
                    try:
                        pec_credit_val = float(rec.previous_balance) if rec.previous_balance else 0.0
                    except ValueError:
                        pec_credit_val = 0.0

                    partner = self.env['res.partner'].create({
                        'name': rec.name,
                        'mobile': rec.mobile,
                        'national_id': rec.national_id,
                        'region_id': rec.region_id.id,
                        'area_id': rec.area_id.id,
                        'pec_credit': pec_credit_val,
                        'is_credit_raised': pec_credit_val > 0,
                        'subscriber_status': 'old',
                        'char_code': rec.char_code,
                        'subscriber_no': rec.subscriber_no,
                        'meter_reading': rec.meter_reading,
                        'opening_reading': rec.opening_reading,
                        'meter_number': rec.meter_number,
                    })
                else:
                    try:
                        pec_credit_val = float(rec.previous_balance) if rec.previous_balance else 0.0
                    except ValueError:
                        pec_credit_val = 0.0
                    partner.pec_credit = pec_credit_val
                    partner.is_credit_raised = pec_credit_val > 0
                    partner.subscriber_status = 'old'
                    partner.char_code = rec.char_code
                    partner.subscriber_no = rec.subscriber_no
                    partner.meter_reading = rec.meter_reading
                    partner.opening_reading = rec.opening_reading
                    partner.meter_number = rec.meter_number
                    if rec.national_id:
                        partner.national_id = rec.national_id
                rec.created_partner_id = partner.id

                # 3. Create Customer and Meter ONLY if active
                if rec.is_active:
                    customer = self.env['utility.customer'].create({
                        'customer_number': rec.customer_number,
                        'partner_id': partner.id,
                        'category_id': rec.category_id.id,
                        'subscriber_id': rec.subscriber_type_id.id,
                        'state': 'active',
                        'contract_template_id': rec.contract_template_id.id,
                    })
                    rec.created_customer_id = customer.id

                    if rec.meter_number:
                        meter = self.env['utility.meter'].search([('meter_number', '=', rec.meter_number)], limit=1)
                        if not meter:
                            meter = self.env['utility.meter'].create({
                                'meter_number': rec.meter_number,
                                'connection_type': 'subscriber',
                                'customer_id': customer.id,
                                'phase': rec.phase,
                            })
                        else:
                            meter.write({
                                'connection_type': 'subscriber',
                                'customer_id': customer.id,
                                'phase': rec.phase,
                            })
                        rec.created_meter_id = meter.id
                        customer.meter_id = meter.id

                        if rec.last_reading > 0:
                            self.env['utility.reading'].create({
                                'meter_id': meter.id,
                                'reading_value': rec.last_reading,
                                'reading_date': fields.Datetime.now(),
                                'reading_type': 'manual',
                                'reading_category': 'customer',
                                'state': 'billed',
                            })

                rec.state = 'imported'
                rec.error_message = False

            except Exception as e:
                rec.state = 'error'
                rec.error_message = str(e)

    def action_create_opening_balances(self):
        for rec in self:
            if rec.state != 'imported' or not rec.created_partner_id:
                raise UserError(_('يجب اعتماد ورفع بيانات العميل أولاً قبل إنشاء الرصيد الافتتاحي.'))
            if rec.opening_move_id:
                continue
            if rec.current_balance > 0:
                journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
                partner = rec.created_partner_id
                account_receivable = partner.property_account_receivable_id
                account_suspense = self.env.company.account_journal_suspense_account_id
                
                if not account_suspense:
                    account_suspense = self.env['account.account'].search([('account_type', '=', 'equity')], limit=1)

                if not account_receivable or not account_suspense:
                    raise UserError(_('يجب إعداد حسابات العملاء والحساب المعلق/حقوق الملكية في النظام.'))

                move = self.env['account.move'].create({
                    'move_type': 'entry',
                    'journal_id': journal.id,
                    'date': fields.Date.today(),
                    'ref': 'رصيد افتتاحي - %s' % rec.customer_number,
                    'line_ids': [
                        (0, 0, {
                            'name': 'رصيد افتتاحي',
                            'partner_id': partner.id,
                            'account_id': account_receivable.id,
                            'debit': rec.current_balance,
                            'credit': 0.0,
                        }),
                        (0, 0, {
                            'name': 'رصيد افتتاحي',
                            'account_id': account_suspense.id,
                            'debit': 0.0,
                            'credit': rec.current_balance,
                        })
                    ]
                })
                move.action_post()
                rec.opening_move_id = move.id

