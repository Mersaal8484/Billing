import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityVendingRequest(models.Model):
    _name = 'utility.vending.request'
    _description = 'طلب بيع كهرباء مسبقة الدفع'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    reference = fields.Char('المرجع', required=True, copy=False, index=True, default=lambda self: _('جديد'))
    idempotency_key = fields.Char('مفتاح منع التكرار', index=True, copy=False,
        help='مفتاح فريد لمنع تكرار العمليات')

    channel_id = fields.Many2one('utility.vending.channel', 'قناة البيع', index=True)
    policy_id = fields.Many2one('utility.vending.policy', 'سياسة البيع')

    pos_order_id = fields.Many2one('pos.order', 'أمر نقاط البيع', index=True, copy=False)
    pos_session_id = fields.Many2one('pos.session', related='pos_order_id.session_id', string='جلسة POS', store=True)
    shift_id = fields.Many2one('utility.cashier.shift', 'الوردية', index=True)

    account_id = fields.Many2one('utility.customer', 'حساب المشترك', required=True, index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', required=True, index=True)
    partner_id = fields.Many2one('res.partner', 'العميل', related='account_id.partner_id', store=True)
    contract_template_id = fields.Many2one('utility.contract.template', 'قالب العقد',
        related='account_id.contract_template_id', store=True)

    gross_amount = fields.Monetary('المبلغ الإجمالي', currency_field='currency_id')
    energy_amount = fields.Monetary('قيمة الطاقة', currency_field='currency_id', store=True)
    service_charge_amount = fields.Monetary('رسوم الخدمة', currency_field='currency_id', store=True)
    tax_amount = fields.Monetary('الضرائب', currency_field='currency_id', store=True)
    debt_recovery_amount = fields.Monetary('استقطاع الديون', currency_field='currency_id', store=True)
    other_deduction_amount = fields.Monetary('خصومات أخرى', currency_field='currency_id', store=True)
    net_vending_amount = fields.Monetary('صافي قيمة الطاقة', currency_field='currency_id',
        compute='_compute_net_amounts', store=True)
    kwh_purchased = fields.Float('الكيلوواط ساعة المشتراة', digits=(12, 3))

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)

    charge_line_ids = fields.One2many('utility.vending.charge.line', 'vending_request_id', 'بنود الشحنة')
    token_ids = fields.One2many('utility.token', 'vending_request_id', 'رموز STS')
    transaction_ids = fields.One2many('utility.transaction', 'vending_request_id', 'المعاملات')
    sts_transaction_ids = fields.One2many('utility.sts.transaction', 'vending_request_id', 'معاملات STS')
    reversal_ids = fields.One2many('utility.vending.reversal', 'vending_request_id', 'طلبات العكس')

    tariff_snapshot = fields.Text('لقطة التعرفة',
        help='JSON snapshot للتعرفة المستخدمة في عملية البيع')

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('quoted', 'عرض سعر'),
        ('confirmed', 'مؤكد'),
        ('paid', 'مدفوع'),
        ('token_pending', 'بانتظار التوكن'),
        ('token_generated', 'تم توليد التوكن'),
        ('token_failed', 'فشل التوكن'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغى'),
    ], 'الحالة', default='draft', tracking=True, index=True)

    vending_date = fields.Datetime('تاريخ البيع', default=fields.Datetime.now, index=True)
    paid_date = fields.Datetime('تاريخ الدفع')
    completed_date = fields.Datetime('تاريخ الإكمال')
    operator_id = fields.Many2one('res.users', 'المشغل', default=lambda self: self.env.user, index=True)
    notes = fields.Text('ملاحظات')

    account_move_id = fields.Many2one('account.move', 'القيد المحاسبي', index=True, copy=False)
    payment_id = fields.Many2one('account.payment', 'الدفعة', index=True, copy=False)

    retry_count = fields.Integer('عدد إعادة المحاولة', default=0)
    last_error = fields.Text('آخر خطأ')

    _sql_constraints = [
        ('vending_idempotency_unique',
         'unique(company_id, idempotency_key)',
         'مفتاح منع التكرار يجب أن يكون فريداً لكل شركة.'),
    ]

    @api.depends('energy_amount', 'service_charge_amount', 'tax_amount',
                 'debt_recovery_amount', 'other_deduction_amount')
    def _compute_net_amounts(self):
        for rec in self:
            rec.net_vending_amount = (
                (rec.energy_amount or 0.0)
                - (rec.debt_recovery_amount or 0.0)
                - (rec.other_deduction_amount or 0.0)
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.vending.request') or _('جديد')
        return super().create(vals_list)

    @api.constrains('account_id', 'meter_id')
    def _check_meter_belongs_to_account(self):
        for rec in self:
            if rec.account_id and rec.meter_id:
                if rec.meter_id.customer_id != rec.account_id:
                    raise ValidationError(
                        _('العداد %s لا يتبع الحساب %s.')
                        % (rec.meter_id.meter_number, rec.account_id.customer_number)
                    )

    @api.constrains('state')
    def _check_state_transition(self):
        valid_transitions = {
            'draft': ('quoted', 'cancelled'),
            'quoted': ('confirmed', 'cancelled'),
            'confirmed': ('paid', 'cancelled'),
            'paid': ('token_pending', 'completed', 'cancelled'),
            'token_pending': ('token_generated', 'token_failed'),
            'token_generated': ('completed',),
            'token_failed': ('token_pending', 'cancelled'),
        }
        for rec in self:
            allowed = valid_transitions.get(rec.state, ())
            if not allowed and rec.state not in ('draft', 'cancelled'):
                raise ValidationError(
                    _('الحالة "%s" لا تسمح بأي انتقالات.')
                    % dict(self._fields['state'].selection).get(rec.state, rec.state)
                )

    def action_quote(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('يمكن إنشاء عرض السعر فقط من حالة المسودة.'))
        self._calculate_quote()
        self.state = 'quoted'

    def action_confirm(self):
        self.ensure_one()
        if self.state != 'quoted':
            raise UserError(_('يمكن التأكيد فقط من حالة عرض السعر.'))
        self.state = 'confirmed'

    def action_mark_paid(self):
        self.ensure_one()
        if self.state not in ('confirmed', 'paid'):
            raise UserError(_('يجب أن يكون الطلب مؤكداً قبل تحديد الدفع.'))
        self.write({
            'state': 'paid',
            'paid_date': fields.Datetime.now(),
        })

    def action_submit_to_sts(self):
        self.ensure_one()
        if self.state != 'paid':
            raise UserError(_('يجب أن يكون الطلب مدفوعاً قبل الإرسال إلى STS.'))
        self.state = 'token_pending'
        self._generate_tokens()

    def action_complete(self):
        self.ensure_one()
        if self.state not in ('token_generated', 'paid'):
            raise UserError(_('يجب أن يتم توليد التوكن لإكمال الطلب.'))
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now(),
        })
        self._post_accounting_entries()

    def action_cancel(self):
        for rec in self:
            if rec.state in ('completed', 'token_generated'):
                raise UserError(_('لا يمكن إلغاء طلب مكتمل أو تم توليد توكن له.'))
            rec.state = 'cancelled'

    def action_retry_token(self):
        self.ensure_one()
        if self.state not in ('token_pending', 'token_failed'):
            raise UserError(_('يمكن إعادة المحاولة فقط عندما يكون التوكن معلقاً أو فاشلاً.'))
        self.write({
            'retry_count': self.retry_count + 1,
            'state': 'token_pending',
        })
        self._generate_tokens()

    def _calculate_quote(self):
        self.ensure_one()
        quote = self.env['utility.vending.policy'].calculate_quote(
            account=self.account_id,
            meter=self.meter_id,
            gross_amount=self.gross_amount,
            vending_date=self.vending_date,
            channel=self.channel_id,
        )
        self.write({
            'energy_amount': quote.get('energy_amount', 0.0),
            'service_charge_amount': quote.get('service_charge', 0.0),
            'tax_amount': quote.get('tax_amount', 0.0),
            'debt_recovery_amount': quote.get('debt_recovery_amount', 0.0),
            'other_deduction_amount': quote.get('other_deduction_amount', 0.0),
            'kwh_purchased': quote.get('kwh_purchased', 0.0),
            'tariff_snapshot': quote.get('tariff_snapshot', ''),
        })
        self._create_charge_lines(quote.get('charge_lines', []))

    def _create_charge_lines(self, charge_lines):
        self.ensure_one()
        self.charge_line_ids.unlink()
        if charge_lines:
            lines_data = []
            for cl in charge_lines:
                lines_data.append({
                    'vending_request_id': self.id,
                    'charge_type': cl.get('charge_type', 'energy'),
                    'description': cl.get('description', ''),
                    'amount': cl.get('amount', 0.0),
                    'sequence': cl.get('sequence', 0),
                })
            self.env['utility.vending.charge.line'].create(lines_data)

    def _generate_tokens(self):
        self.ensure_one()
        provider = self.company_id.default_sts_provider_id
        if not provider:
            provider = self.env['utility.sts.provider'].search([
                ('active', '=', True),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        if not provider:
            raise UserError(_('لا يوجد مزود STS نشط.'))

        sts_tx = self.env['utility.sts.transaction'].create({
            'vending_request_id': self.id,
            'provider_id': provider.id,
            'meter_id': self.meter_id.id,
            'account_id': self.account_id.id,
            'amount': self.energy_amount,
            'kwh': self.kwh_purchased,
            'state': 'pending',
        })
        sts_tx.action_send_request()

        if sts_tx.state == 'success' and sts_tx.token_value:
            self.env['utility.token'].create({
                'vending_request_id': self.id,
                'account_id': self.account_id.id,
                'meter_id': self.meter_id.id,
                'customer_id': self.partner_id.id,
                'token_number': sts_tx.token_value,
                'token_identifier': sts_tx.token_identifier,
                'amount': self.energy_amount,
                'kwh': self.kwh_purchased,
                'status': 'success',
                'response_date': fields.Datetime.now(),
                'response_code': '00',
                'response_message': _('تم إنشاء الرمز بنجاح'),
                'sts_server': provider.name,
            })
            self.state = 'token_generated'
        else:
            self.state = 'token_failed'
            self.last_error = sts_tx.error_message or _('فشل توليد التوكن')

    def _post_accounting_entries(self):
        self.ensure_one()
        if not self.company_id.prepaid_revenue_policy:
            return
        service = self.env['utility.prepaid.accounting.service']
        service.create_vending_entry(self)

    def action_view_tokens(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('رموز STS'),
            'res_model': 'utility.token',
            'domain': [('vending_request_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('المعاملات'),
            'res_model': 'utility.transaction',
            'domain': [('vending_request_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    @api.model
    def _cron_reconcile_pos_vending(self):
        unreconciled = self.search([
            ('pos_order_id', '!=', False),
            ('state', '=', 'draft'),
        ], limit=100)
        for req in unreconciled:
            if req.pos_order_id and req.pos_order_id.state == 'paid' and not req.pos_order_id.vending_request_id:
                req.pos_order_id.vending_request_id = req.id
                req.action_confirm()

    @api.model
    def _cron_expire_unpaid(self):
        expired = self.search([
            ('state', 'in', ('draft', 'quoted', 'confirmed')),
            ('create_date', '<', fields.Datetime.now()),
        ], limit=500)
        expired.write({'state': 'cancelled'})
