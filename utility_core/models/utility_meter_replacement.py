from odoo import models, fields, api, _
from odoo.exceptions import UserError


class UtilityMeterReplacement(models.Model):
    _name = 'utility.meter.replacement'
    _description = 'سجل استبدال العدادات عبر حساب المشترك (Meter Replacement History)'
    _inherit = ['mail.thread']
    _order = 'replace_date desc'

    name = fields.Char(string="الاسم", compute="_compute_name", store=True)

    # Primary Required Field: utility.customer
    utility_account_id = fields.Many2one('utility.customer', required=True, string="حساب الكهرباء / المشترك", tracking=True)
    partner_id = fields.Many2one('res.partner', related='utility_account_id.partner_id', string="العميل", store=True)
    contract_id = fields.Many2one('account.analytic.account', string="العقد التحليلي", compute="_compute_contract_id", store=True, readonly=False, tracking=True)

    @api.depends('utility_account_id')
    def _compute_name(self):
        for rec in self:
            if rec.utility_account_id:
                rec.name = f"استبدال لـ {rec.utility_account_id.display_name}"
            else:
                rec.name = "استبدال جديد"

    # Old meter
    old_meter_id = fields.Many2one('utility.meter', string="العداد القديم", readonly=True)
    old_meter_number = fields.Char(string="رقم العداد القديم", readonly=True)
    old_meter_type_id = fields.Many2one('utility.meter.type', string="نوع العداد القديم", readonly=True)
    old_phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string="طور العداد القديم", readonly=True)
    old_closing_reading = fields.Float(string="القراءة الختامية", digits=(12, 3), required=True, tracking=True)
    old_last_invo_reading = fields.Float(string="آخر قراءة مفوترة", digits=(12, 3), readonly=True)
    old_uninvoiced_consumption = fields.Float(string="الاستهلاك غير المفوتر", digits=(12, 3), compute="_compute_old_uninvoiced", store=True)

    # New meter
    new_meter_id = fields.Many2one('utility.meter', string="العداد الجديد (موجود بالنظام)", domain="[('customer_id', '=', False)]", tracking=True)
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

    @api.depends('utility_account_id')
    def _compute_contract_id(self):
        for rec in self:
            if rec.utility_account_id:
                contract = self.env['account.analytic.account'].search([
                    ('partner_id', '=', rec.utility_account_id.partner_id.id)
                ], limit=1)
                rec.contract_id = contract.id if contract else False
            else:
                rec.contract_id = False

    @api.depends('old_closing_reading', 'old_last_invo_reading', 'utility_account_id')
    def _compute_old_uninvoiced(self):
        for rec in self:
            val = rec.utility_account_id.partner_id.reading_multiplier if rec.utility_account_id and rec.utility_account_id.partner_id.reading_multiplier else 1.0
            rec.old_uninvoiced_consumption = max((rec.old_closing_reading - rec.old_last_invo_reading) * val, 0.0)

    @api.onchange('utility_account_id')
    def _onchange_utility_account_id(self):
        if self.utility_account_id:
            acc = self.utility_account_id
            if acc.meter_id:
                self.old_meter_id = acc.meter_id
                self.old_meter_number = acc.meter_id.meter_number
                self.old_meter_type_id = acc.meter_id.meter_type_id
                self.old_phase = acc.meter_id.phase
            
            contract = self.env['account.analytic.account'].search([
                ('partner_id', '=', acc.partner_id.id)
            ], limit=1)
            if contract:
                self.contract_id = contract.id
                
            if acc.last_reading_value or acc.last_invoice_reading:
                self.old_last_invo_reading = acc.last_invoice_reading
                self.old_closing_reading = acc.last_reading_value
            else:
                # Fallback to get last reading from utility.reading if no contract exists
                last_reading = self.env['utility.reading'].search([
                    ('meter_id', '=', acc.meter_id.id),
                    ('state', '=', 'approved')
                ], order='reading_date desc', limit=1)
                self.old_last_invo_reading = last_reading.reading_value if last_reading else 0.0
                self.old_closing_reading = self.old_last_invo_reading

    def action_confirm_replacement(self):
        for rec in self:
            if rec.state == 'done':
                continue
            
            acc = rec.utility_account_id
            if not acc:
                raise UserError(_("يجب تحديد حساب الكهرباء / المشترك لإتمام الاستبدال!"))

            # Determine or create the new meter
            if rec.new_meter_id:
                new_meter = rec.new_meter_id
            elif rec.new_meter_number:
                new_meter = self.env['utility.meter'].create({
                    'meter_number': rec.new_meter_number,
                    'meter_type_id': rec.new_meter_type_id.id if rec.new_meter_type_id else False,
                    'phase': rec.new_phase,
                    'customer_id': acc.id,
                    'installation_date': rec.replace_date.date() if rec.replace_date else fields.Date.today(),
                })
                rec.new_meter_id = new_meter
            else:
                raise UserError(_("الرجاء اختيار عداد موجود أو إدخال رقم عداد جديد!"))

            # Decommission old meter
            if rec.old_meter_id:
                rec.old_meter_id.write({
                    'customer_id': False,
                    'active': False,
                })

            # Assign new meter to customer account
            new_meter.write({'customer_id': acc.id})
            acc.write({'meter_id': new_meter.id})

            # Update partner details
            if acc and acc.partner_id:
                acc.partner_id.write({
                    'reading_multiplier': rec.new_meter_val,
                    'opening_reading': rec.new_opening_reading,
                })
            rec.state = 'done'
