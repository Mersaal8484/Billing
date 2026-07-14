import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityPrepaidAdjustment(models.Model):
    _name = 'utility.prepaid.adjustment'
    _description = 'تسوية دفع مسبق'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    reference = fields.Char('المرجع', required=True, copy=False, index=True, default=lambda self: _('جديد'))
    date = fields.Datetime('التاريخ', default=fields.Datetime.now)

    partner_id = fields.Many2one('res.partner', 'العميل', required=True, index=True)
    account_id = fields.Many2one('utility.customer', 'حساب المشترك', required=True, index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', index=True)

    adjustment_type = fields.Selection([
        ('credit', 'تسوية دائنة'),
        ('debit', 'تسوية مدينة'),
        ('compensation', 'تعويض'),
        ('correction', 'تصحيح'),
        ('meter_replacement', 'استبدال عداد'),
        ('free_units', 'وحدات مجانية'),
    ], 'نوع التسوية', required=True, index=True)

    amount = fields.Monetary('المبلغ', currency_field='currency_id', required=True)
    kwh_amount = fields.Float('الوحدات (kWh)', digits=(12, 3),
        help='عدد الوحدات المضافة أو المخصومة')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)

    reason = fields.Text('السبب', required=True)
    technical_report = fields.Text('التقرير الفني')

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('submitted', 'مقدم'),
        ('under_review', 'قيد المراجعة'),
        ('approved', 'موافق عليه'),
        ('applied', 'مطبق'),
        ('cancelled', 'ملغى'),
    ], 'الحالة', default='draft', tracking=True, index=True)

    approved_by = fields.Many2one('res.users', 'وافق عليه', index=True)
    operator_id = fields.Many2one('res.users', 'المشغل', default=lambda self: self.env.user, index=True)

    account_move_id = fields.Many2one('account.move', 'القيد المحاسبي', index=True, copy=False)
    token_id = fields.Many2one('utility.token', 'توكن الإدارة', index=True)

    notes = fields.Text('ملاحظات')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.prepaid.adjustment') or _('جديد')
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('المبلغ يجب أن يكون أكبر من صفر.'))

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            rec.state = 'submitted'

    def action_review(self):
        for rec in self:
            if rec.state != 'submitted':
                continue
            rec.state = 'under_review'

    def action_approve(self):
        for rec in self:
            if rec.state not in ('under_review', 'submitted'):
                continue
            rec.write({
                'state': 'approved',
                'approved_by': rec.env.user.id,
            })

    def action_apply(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('يجب الموافقة على التسوية قبل تطبيقها.'))

            self.env['utility.transaction'].create({
                'company_id': rec.company_id.id,
                'reference': self.env['ir.sequence'].next_by_code('utility.transaction') or '/',
                'transaction_type': 'adjustment',
                'amount': rec.amount if rec.adjustment_type in ('credit', 'compensation') else -rec.amount,
                'partner_id': rec.partner_id.id,
                'account_id': rec.account_id.id,
                'meter_id': rec.meter_id.id,
                'adjustment_id': rec.id,
                'operator_id': rec.env.user.id,
                'notes': _('تسوية %s: %s') % (rec.reference, rec.reason),
            })

            if rec.adjustment_type in ('credit', 'compensation') and rec.account_id:
                if rec.kwh_amount:
                    rec.account_id.total_kwh_purchased = (
                        (rec.account_id.total_kwh_purchased or 0.0) + rec.kwh_amount)
                rec.account_id.total_purchases = (
                    (rec.account_id.total_purchases or 0.0) + rec.amount)

            accounting_service = self.env['utility.prepaid.accounting.service']
            accounting_service.create_adjustment_entry(rec)

            if rec.adjustment_type in ('credit', 'compensation') and rec.meter_id:
                provider = rec.company_id.default_sts_provider_id
                if provider:
                    try:
                        result = provider.send_generate_token(
                            meter_number=rec.meter_id.meter_number,
                            amount=rec.amount,
                            kwh=rec.kwh_amount or 0,
                            token_type='management',
                        )
                        if result.get('success'):
                            token = self.env['utility.token'].create({
                                'company_id': rec.company_id.id,
                                'account_id': rec.account_id.id,
                                'meter_id': rec.meter_id.id,
                                'customer_id': rec.partner_id.id,
                                'token_number': result.get('token_value'),
                                'token_identifier': result.get('token_identifier'),
                                'token_type': 'management',
                                'amount': rec.amount,
                                'kwh': rec.kwh_amount or 0,
                                'status': 'success',
                                'provider_reference': result.get('provider_reference'),
                                'response_date': fields.Datetime.now(),
                            })
                            rec.token_id = token.id
                    except Exception:
                        _logger.exception('Failed to generate management token for adjustment %s', rec.reference)

            rec.state = 'applied'

    def action_cancel(self):
        for rec in self:
            if rec.state in ('applied',):
                raise UserError(_('لا يمكن إلغاء تسوية تم تطبيقها.'))
            rec.state = 'cancelled'
