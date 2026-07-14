import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UtilityVendingReversal(models.Model):
    _name = 'utility.vending.reversal'
    _description = 'طلب عكس بيع مسبق'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    reference = fields.Char('المرجع', required=True, copy=False, index=True, default=lambda self: _('جديد'))
    date = fields.Datetime('التاريخ', default=fields.Datetime.now)

    vending_request_id = fields.Many2one('utility.vending.request', 'طلب البيع الأصلي',
        required=True, index=True)
    original_vending_request_id = fields.Many2one('utility.vending.request',
        related='vending_request_id', string='الطلب الأصلي', store=True)
    token_id = fields.Many2one('utility.token', 'التوكن الأصلي', index=True)
    pos_order_id = fields.Many2one('pos.order', 'أمر POS',
        related='vending_request_id.pos_order_id', store=True)

    reversal_type = fields.Selection([
        ('full', 'عكس كامل'),
        ('partial', 'عكس جزئي'),
    ], 'نوع العكس', required=True, default='full')
    amount = fields.Monetary('المبلغ', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)

    reason_id = fields.Many2one('utility.reversal.reason', 'سبب العكس', required=True, index=True)
    reason_details = fields.Text('تفاصيل السبب')

    partner_id = fields.Many2one('res.partner', 'العميل',
        related='vending_request_id.partner_id', store=True)
    account_id = fields.Many2one('utility.customer', 'الحساب',
        related='vending_request_id.account_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'العداد',
        related='vending_request_id.meter_id', store=True)

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('submitted', 'مقدم'),
        ('under_review', 'قيد المراجعة'),
        ('provider_validation', 'تحقق من المزود'),
        ('approved', 'موافق عليه'),
        ('sts_reversed', 'تم العكس لدى STS'),
        ('refund_issued', 'تم الاسترداد المالي'),
        ('completed', 'مكتمل'),
        ('rejected', 'مرفوض'),
        ('cancelled', 'ملغى'),
    ], 'الحالة', default='draft', tracking=True, index=True)

    approved_by = fields.Many2one('res.users', 'وافق عليه', index=True)
    operator_id = fields.Many2one('res.users', 'المشغل', default=lambda self: self.env.user, index=True)

    account_move_id = fields.Many2one('account.move', 'القيد المحاسبي العكسي', index=True, copy=False)
    sts_transaction_id = fields.Many2one('utility.sts.transaction', 'معاملة STS للعكس', index=True)

    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('reversal_reference_unique',
         'unique(company_id, reference)',
         'مرجع العكس يجب أن يكون فريداً لكل شركة.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.vending.reversal') or _('جديد')
        return super().create(vals_list)

    @api.constrains('vending_request_id', 'state')
    def _check_valid_reversal(self):
        for rec in self:
            if rec.vending_request_id and rec.vending_request_id.state not in ('completed', 'token_generated'):
                raise ValidationError(_('لا يمكن عكس طلب غير مكتمل.'))

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

    def action_validate_provider(self):
        for rec in self:
            if rec.state != 'under_review':
                continue
            rec.state = 'provider_validation'
            rec._query_provider_status()

    def action_approve(self):
        for rec in self:
            if rec.state not in ('provider_validation', 'under_review'):
                continue
            rec.write({
                'state': 'approved',
                'approved_by': rec.env.user.id,
            })

    def action_reverse_sts(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('يجب الموافقة على العكس قبل التنفيذ لدى STS.'))

            original_token = rec.token_id or self.env['utility.token'].search([
                ('vending_request_id', '=', rec.vending_request_id.id),
                ('status', '=', 'success'),
            ], limit=1)

            if not original_token:
                raise UserError(_('لا يوجد توكن ناجح لعكسه.'))

            sts_tx = self.env['utility.sts.transaction'].create({
                'vending_request_id': rec.vending_request_id.id,
                'reversal_id': rec.id,
                'provider_id': original_token.company_id.default_sts_provider_id.id or False,
                'meter_id': rec.meter_id.id,
                'account_id': rec.account_id.id,
                'amount': rec.amount,
                'transaction_type': 'reverse',
                'state': 'pending',
            })

            if original_token.provider_reference:
                result = original_token.company_id.default_sts_provider_id.send_reverse_transaction(
                    token_value=original_token.token_number,
                    meter_number=rec.meter_id.meter_number,
                )
                if result.get('success'):
                    sts_tx.write({
                        'state': 'success',
                        'raw_response': result.get('raw_response', ''),
                    })
                    rec.write({
                        'state': 'sts_reversed',
                        'sts_transaction_id': sts_tx.id,
                    })
                else:
                    sts_tx.write({
                        'state': 'failed',
                        'error_message': result.get('error_message', ''),
                    })
                    raise UserError(_('فشل العكس لدى المزود: %s') % result.get('error_message', ''))
            else:
                sts_tx.write({'state': 'success'})
                rec.write({
                    'state': 'sts_reversed',
                    'sts_transaction_id': sts_tx.id,
                })

    def action_issue_refund(self):
        for rec in self:
            if rec.state != 'sts_reversed':
                raise UserError(_('يجب إتمام العكس لدى STS قبل إصدار الاسترداد.'))

            self.env['utility.transaction'].create({
                'company_id': rec.company_id.id,
                'reference': self.env['ir.sequence'].next_by_code('utility.transaction') or '/',
                'transaction_type': 'refund',
                'amount': rec.amount,
                'partner_id': rec.partner_id.id,
                'account_id': rec.account_id.id,
                'meter_id': rec.meter_id.id,
                'reversal_id': rec.id,
                'operator_id': rec.env.user.id,
                'notes': _('استرداد عكس %s: %s') % (rec.reference, rec.reason_id.name),
            })

            accounting_service = self.env['utility.prepaid.accounting.service']
            accounting_service.create_reversal_entry(rec)

            rec.state = 'refund_issued'

    def action_complete(self):
        for rec in self:
            if rec.state != 'refund_issued':
                raise UserError(_('يجب إصدار الاسترداد لإكمال العكس.'))
            rec.state = 'completed'
            if rec.vending_request_id:
                rec.vending_request_id.state = 'cancelled'

    def action_reject(self):
        for rec in self:
            if rec.state in ('completed', 'cancelled'):
                continue
            rec.state = 'rejected'

    def action_cancel(self):
        for rec in self:
            if rec.state in ('completed', 'sts_reversed', 'refund_issued'):
                raise UserError(_('لا يمكن إلغاء عكس تم تنفيذه.'))
            rec.state = 'cancelled'

    def _query_provider_status(self):
        self.ensure_one()
        original_token = self.token_id or self.env['utility.token'].search([
            ('vending_request_id', '=', self.vending_request_id.id),
            ('status', '=', 'success'),
        ], limit=1)
        if original_token and original_token.provider_reference:
            provider = original_token.company_id.default_sts_provider_id
            if provider:
                result = provider.send_query_transaction(original_token.provider_reference)
                if result.get('success'):
                    _logger.info('Provider query for reversal %s: %s', self.reference, result)
