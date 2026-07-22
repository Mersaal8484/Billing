from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class UtilityMeterReplacement(models.Model):
    _name = 'utility.meter.replacement'
    _description = 'سجل استبدال العدادات عبر حساب المشترك'
    _inherit = ['mail.thread']
    _order = 'replace_date desc'

    name = fields.Char(string="الاسم", compute="_compute_name", store=True)
    company_id = fields.Many2one('res.company', string='الشركة', required=True, index=True, default=lambda self: self.env.company)
    closing_reading_id = fields.Many2one('utility.reading', string='سجل القراءة الختامية', readonly=True, copy=False, ondelete='restrict')
    opening_reading_id = fields.Many2one('utility.reading', string='سجل القراءة الافتتاحية', readonly=True, copy=False, ondelete='restrict')
    sale_order_id = fields.Many2one('sale.order', string='فاتورة الاستهلاك المركبة', related='closing_reading_id.included_sale_order_id', store=True, readonly=True)

    # Primary Required Field: utility.customer
    utility_account_id = fields.Many2one('utility.customer', required=True, string="حساب الكهرباء / المشترك", tracking=True, check_company=True)
    partner_id = fields.Many2one('res.partner', related='utility_account_id.partner_id', string="العميل", store=True)

    @api.depends('utility_account_id')
    def _compute_name(self):
        for rec in self:
            if rec.utility_account_id:
                rec.name = f"استبدال لـ {rec.utility_account_id.display_name}"
            else:
                rec.name = "استبدال جديد"

    # Old meter (computed from account to guarantee value is set and saved)
    old_meter_id = fields.Many2one(
        'utility.meter', string="العداد القديم",
        compute='_compute_old_meter_info', store=True, readonly=False, check_company=True)
    old_meter_number = fields.Char(
        string="رقم العداد القديم", compute='_compute_old_meter_info', store=True, readonly=False)
    old_meter_type_id = fields.Many2one(
        'utility.meter.type', string="نوع العداد القديم", compute='_compute_old_meter_info', store=True, readonly=False)
    old_phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string="طور العداد القديم", compute='_compute_old_meter_info', store=True, readonly=False)
    old_last_invo_reading = fields.Float(
        string="آخر قراءة مفوترة", digits=(12, 3), compute='_compute_old_meter_info', store=True, readonly=False)

    old_closing_reading = fields.Float(string="آخر قراءة للعداد عند الاستبدال", digits=(12, 3), required=True, tracking=True)
    old_uninvoiced_consumption = fields.Float(string="الاستهلاك غير المفوتر", digits=(12, 3), compute="_compute_old_uninvoiced", store=True)

    old_meter_serial_scan = fields.Char(string="مسح العداد القديم (باركود)", store=False, help="استخدم الكاميرا لمسح العداد واستدعاء حساب المشترك")
    replacement_image = fields.Binary(string="صورة العداد (اختياري)", attachment=True)

    # New meter
    new_meter_serial_scan = fields.Char(string="مسح العداد الجديد (باركود)", store=False, help="استخدم الكاميرا للبحث عن العداد الجديد")
    new_meter_id = fields.Many2one('utility.meter', string="العداد الجديد (موجود بالنظام)", domain="[('customer_id', '=', False)]", tracking=True, check_company=True)
    new_meter_number = fields.Char(string="رقم العداد الجديد (لإنشاء جديد)", tracking=True)
    new_meter_type_id = fields.Many2one('utility.meter.type', string="نوع العداد الجديد")
    new_phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string="طور العداد الجديد", default='single')
    new_opening_reading = fields.Float(string="القراءة الافتتاحية", digits=(12, 3), required=True, tracking=True)
    new_meter_val = fields.Float(string="معامل الضرب", default=1.0, tracking=True)

    replace_date = fields.Datetime(string="تاريخ الاستبدال", default=fields.Datetime.now, required=True, tracking=True)
    reason = fields.Selection([
        ('fault', 'عطل فني'),
        ('expired', 'انتهاء العمر الافتراضي'),
        ('upgrade', 'تطوير النظام'),
        ('tamper', 'تلاعب/سرقة'),
        ('other', 'أخرى'),
    ], string="سبب الاستبدال", required=True, tracking=True)
    notes = fields.Text(string="ملاحظات")
    user_id = fields.Many2one('res.users', string="المستخدم", default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('done', 'تم الاستبدال (Done)'),
    ], string="الحالة", default='draft', tracking=True)

    @api.depends('utility_account_id', 'utility_account_id.meter_id')
    def _compute_old_meter_info(self):
        for rec in self:
            if rec.utility_account_id and rec.utility_account_id.meter_id:
                acc = rec.utility_account_id
                meter = acc.meter_id
                rec.old_meter_id = meter
                rec.old_meter_number = meter.meter_number
                rec.old_meter_type_id = meter.meter_type_id
                rec.old_phase = meter.phase
                rec.old_last_invo_reading = acc.last_invoice_reading or acc.last_reading_value or 0.0
            else:
                if not rec.old_meter_id:
                    rec.old_meter_id = False
                if not rec.old_meter_number:
                    rec.old_meter_number = False
                if not rec.old_meter_type_id:
                    rec.old_meter_type_id = False
                if not rec.old_phase:
                    rec.old_phase = False
                if not rec.old_last_invo_reading:
                    rec.old_last_invo_reading = 0.0

    @api.depends('old_closing_reading', 'old_last_invo_reading', 'utility_account_id')
    def _compute_old_uninvoiced(self):
        for rec in self:
            val = rec.utility_account_id.meter_id.multiplier if rec.utility_account_id and rec.utility_account_id.meter_id else 1.0
            rec.old_uninvoiced_consumption = max((rec.old_closing_reading - rec.old_last_invo_reading) * val, 0.0)

    @api.onchange('old_closing_reading', 'old_last_invo_reading')
    def _onchange_old_closing_reading(self):
        val = self.utility_account_id.meter_id.multiplier if self.utility_account_id and self.utility_account_id.meter_id else 1.0
        self.old_uninvoiced_consumption = max((self.old_closing_reading - self.old_last_invo_reading) * val, 0.0)

    @api.onchange('utility_account_id')
    def _onchange_utility_account_id(self):
        if self.utility_account_id:
            acc = self.utility_account_id
            if acc.meter_id:
                self.old_meter_id = acc.meter_id
                self.old_meter_number = acc.meter_id.meter_number
                self.old_meter_type_id = acc.meter_id.meter_type_id
                self.old_phase = acc.meter_id.phase
                
            if acc.last_invoice_reading or acc.last_reading_value:
                self.old_last_invo_reading = acc.last_invoice_reading or acc.last_reading_value or 0.0
                self.old_closing_reading = acc.last_reading_value or acc.last_invoice_reading or 0.0
            else:
                last_reading = self.env['utility.reading'].search([
                    ('meter_id', '=', acc.meter_id.id),
                    ('state', '=', 'approved')
                ], order='reading_date desc', limit=1)
                self.old_last_invo_reading = last_reading.reading_value if last_reading else 0.0
                self.old_closing_reading = self.old_last_invo_reading

            val = acc.meter_id.multiplier if acc.meter_id else 1.0
            self.old_uninvoiced_consumption = max((self.old_closing_reading - self.old_last_invo_reading) * val, 0.0)

    @api.onchange('old_meter_serial_scan')
    def _onchange_old_meter_serial_scan(self):
        if self.old_meter_serial_scan:
            meter = self.env['utility.meter'].search(['|', ('meter_number', '=', self.old_meter_serial_scan), ('serial_number', '=', self.old_meter_serial_scan)], limit=1)
            if meter:
                if meter.customer_id:
                    self.utility_account_id = meter.customer_id.id
                    self.old_meter_serial_scan = False
                    return {'warning': {'title': _('نجاح'), 'message': _('تم تحديد حساب المشترك (%s) بناءً على العداد الممسوح.') % meter.customer_id.display_name, 'type': 'notification'}}
                else:
                    return {'warning': {'title': _('تنبيه'), 'message': _('العداد الممسوح غير مرتبط بأي حساب مشترك حالياً.')}}
            else:
                return {'warning': {'title': _('غير موجود'), 'message': _('لم يتم العثور على عداد يحمل الرقم: %s') % self.old_meter_serial_scan}}

    @api.onchange('new_meter_serial_scan')
    def _onchange_new_meter_serial_scan(self):
        if self.new_meter_serial_scan:
            meter = self.env['utility.meter'].search(['|', ('meter_number', '=', self.new_meter_serial_scan), ('serial_number', '=', self.new_meter_serial_scan)], limit=1)
            if meter:
                if not meter.customer_id:
                    self.new_meter_id = meter.id
                    self.new_meter_serial_scan = False
                    return {'warning': {'title': _('نجاح'), 'message': _('تم اختيار العداد الجديد (%s).') % meter.display_name, 'type': 'notification'}}
                else:
                    return {'warning': {'title': _('مرفوض'), 'message': _('هذا العداد مرتبط بالفعل بمشترك آخر (%s)!') % meter.customer_id.display_name}}
            else:
                return {'warning': {'title': _('غير موجود'), 'message': _('العداد %s غير مسجل في المخازن/النظام.') % self.new_meter_serial_scan}}

    @api.constrains('old_closing_reading', 'old_last_invo_reading', 'new_opening_reading')
    def _check_readings_validity(self):
        for rec in self:
            if rec.old_closing_reading < rec.old_last_invo_reading:
                raise ValidationError(_('القراءة الختامية للعداد القديم (%.2f) لا يمكن أن تقل عن آخر قراءة مفوترة (%.2f).') % (rec.old_closing_reading, rec.old_last_invo_reading))
            if rec.new_opening_reading < 0:
                raise ValidationError(_('القراءة الافتتاحية للعداد الجديد لا يمكن أن تكون سالبة.'))

    def action_view_closing_reading(self):
        self.ensure_one()
        if not self.closing_reading_id:
            raise UserError(_('لا توجد قراءة ختامية مرتبطة بهذا الاستبدال.'))
        return {
            'name': _('القراءة الختامية للعداد القديم'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.reading',
            'res_id': self.closing_reading_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_opening_reading(self):
        self.ensure_one()
        if not self.opening_reading_id:
            raise UserError(_('لا توجد قراءة افتتاحية مرتبطة بهذا الاستبدال.'))
        return {
            'name': _('القراءة الافتتاحية للعداد الجديد'),
            'type': 'ir.actions.act_window',
            'res_model': 'utility.reading',
            'res_id': self.opening_reading_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('لم يتم إدراج الاستهلاك غير المفوتر في فاتورة بعد.'))
        return {
            'name': _('فاتورة الاستهلاك المركبة'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _action_confirm_replacement_unified(self):
        """Complete replacement and create auditable closing/opening readings."""
        for rec in self:
            if rec.state == 'done':
                continue
            account = rec.utility_account_id
            if not account:
                raise UserError(_('يجب تحديد حساب المشترك أولاً.'))
            old_meter = rec.old_meter_id or account.meter_id
            if not old_meter:
                raise UserError(_('حساب المشترك المختار [%s] لا يملك عداداً فعالاً في النظام لكي يتم استبداله.') % account.display_name)

            new_meter = rec.new_meter_id
            if not new_meter and rec.new_meter_number:
                new_meter = self.env['utility.meter'].create({
                    'meter_number': rec.new_meter_number,
                    'meter_type_id': rec.new_meter_type_id.id if rec.new_meter_type_id else False,
                    'phase': rec.new_phase,
                    'installation_date': rec.replace_date.date(),
                })
                rec.new_meter_id = new_meter
            if not new_meter or old_meter == new_meter:
                raise UserError(_('يجب اختيار عداد جديد مختلف عن العداد القديم.'))
            if rec.old_closing_reading < rec.old_last_invo_reading:
                raise UserError(_('القراءة الختامية لا يمكن أن تقل عن آخر قراءة مفوترة.'))

            Reading = self.env['utility.reading'].with_context(_bypass_reading_protection=True)
            closing = Reading.create({
                'company_id': rec.company_id.id, 'account_id': account.id,
                'meter_id': old_meter.id, 'reading_date': rec.replace_date,
                'reading_value': rec.old_closing_reading,
                'previous_reading': rec.old_last_invo_reading,
                'previous_reading_date': account.last_invoice_date or rec.replace_date,
                'meter_multiplier': old_meter.multiplier or 1.0,
                'reading_type': 'manual', 'reading_purpose': 'replacement_closing',
                'reading_category': 'customer', 'replacement_id': rec.id,
                'state': 'approved',
                'remarks': _('قراءة إغلاق بسبب استبدال العداد بالعملية %s') % rec.display_name,
            })
            if closing.consumption < 0:
                raise UserError(_(
                    'القراءة الختامية أقل من آخر قراءة صحيحة للعداد القديم.'))
            old_meter.write({'customer_id': False, 'active': False})
            new_meter.write({'customer_id': account.id, 'multiplier': rec.new_meter_val, 'active': True})
            account.write({'meter_id': new_meter.id, 'last_reading_value': rec.new_opening_reading})
            opening = Reading.create({
                'company_id': rec.company_id.id, 'account_id': account.id,
                'meter_id': new_meter.id, 'reading_date': rec.replace_date,
                'reading_value': rec.new_opening_reading,
                'previous_reading': rec.new_opening_reading,
                'previous_reading_date': rec.replace_date,
                'meter_multiplier': rec.new_meter_val or 1.0,
                'reading_type': 'manual', 'reading_purpose': 'opening',
                'reading_category': 'customer', 'replacement_id': rec.id,
                'state': 'approved', 'is_initial_reading': True,
                'remarks': _('قراءة افتتاحية بسبب استبدال العداد بالعملية %s') % rec.display_name,
            })
            self.env['utility.meter.log']._create_log(old_meter, 'removal', _('رفع العداد %s واستبداله بـ %s') % (old_meter.meter_number, new_meter.meter_number), ref_record=rec)
            self.env['utility.meter.log']._create_log(new_meter, 'replacement', _('تركيب العداد %s للمشترك %s') % (new_meter.meter_number, account.display_name), ref_record=rec)
            rec.write({'closing_reading_id': closing.id, 'opening_reading_id': opening.id, 'old_meter_id': old_meter.id, 'state': 'done'})
        return True

    def action_confirm_replacement(self):
        """Run the unified replacement workflow from the core form."""
        return self._action_confirm_replacement_unified()
