from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityBankSettlementLine(models.Model):
    _name = 'utility.bank.settlement.line'
    _description = 'تخصيص تسوية بنكية'
    bank_settlement_id = fields.Many2one('utility.bank.settlement', required=True, ondelete='cascade')
    collection_settlement_id = fields.Many2one('utility.collection.settlement', required=True, ondelete='restrict')
    allocated_amount = fields.Monetary(required=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='bank_settlement_id.currency_id', store=True, readonly=True)
    _sql_constraints = [('bank_settlement_source_uniq', 'unique(bank_settlement_id, collection_settlement_id)', 'لا يجوز تكرار تسوية المصدر.')]


class UtilityBankSettlement(models.Model):
    _name = 'utility.bank.settlement'
    _description = 'إيداع وتسوية بنكية'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deposit_date desc, id desc'

    name = fields.Char('المرجع', required=True, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    deposit_date = fields.Date('تاريخ الإيداع', required=True, default=fields.Date.today)
    bank_journal_id = fields.Many2one('account.journal', required=True, domain="[('type', '=', 'bank')]")
    bank_account_id = fields.Many2one('account.account', required=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('utility.bank.settlement.line', 'bank_settlement_id', string='تسويات المصدر')
    expected_amount = fields.Monetary('المتوقع', compute='_compute_amounts', store=True, currency_field='currency_id')
    deposited_amount = fields.Monetary('المودع', compute='_compute_amounts', store=True, currency_field='currency_id')
    remaining_to_deposit = fields.Monetary('المتبقي للإيداع', compute='_compute_amounts', store=True, currency_field='currency_id')
    bank_reference = fields.Char('مرجع البنك', required=True, copy=False)
    deposit_slip_number = fields.Char('رقم قسيمة الإيداع')
    state = fields.Selection([('draft', 'مسودة'), ('confirmed', 'مؤكد'), ('waiting_bank_match', 'بانتظار مطابقة البنك'), ('reconciled', 'تمت المطابقة'), ('cancelled', 'ملغى')], default='draft', tracking=True)
    statement_line_id = fields.Many2one('account.bank.statement.line', readonly=True, copy=False)
    account_move_id = fields.Many2one('account.move', readonly=True, copy=False)
    difference_amount = fields.Monetary('الفرق', compute='_compute_amounts', store=True, currency_field='currency_id')
    notes = fields.Text('ملاحظات')
    _sql_constraints = [('bank_reference_uniq', 'unique(company_id, bank_reference)', 'مرجع البنك مستخدم مسبقًا.')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('name', self.env['ir.sequence'].next_by_code('utility.bank.settlement') or _('جديد'))
        return super().create(vals_list)

    @api.depends('line_ids.allocated_amount')
    def _compute_amounts(self):
        for record in self:
            record.expected_amount = sum(record.line_ids.mapped('collection_settlement_id.declared_amount'))
            record.deposited_amount = sum(record.line_ids.mapped('allocated_amount'))
            record.remaining_to_deposit = record.expected_amount - record.deposited_amount
            record.difference_amount = record.deposited_amount - record.expected_amount

    def action_confirm(self):
        for record in self:
            if not record.line_ids or any(line.collection_settlement_id.state != 'posted' for line in record.line_ids):
                raise ValidationError(_('لا يمكن تأكيد إيداع دون تسويات محصل مرحّلة.'))
            if any(line.currency_id != record.currency_id or line.allocated_amount <= 0 for line in record.line_ids):
                raise ValidationError(_('عملة ومبالغ تخصيص الإيداع غير صحيحة.'))
            record.state = 'confirmed'

    def action_post(self):
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError(_('يجب تأكيد الإيداع قبل إرساله للمطابقة البنكية.'))
            record.state = 'waiting_bank_match'

    def action_reconcile(self):
        for record in self:
            if record.state != 'waiting_bank_match' or not record.statement_line_id:
                raise ValidationError(_('حدد سطر كشف بنكي فعلي قبل المطابقة.'))
            line = record.statement_line_id
            if line.company_id != record.company_id or line.currency_id != record.currency_id:
                raise ValidationError(_('سطر البنك لا يطابق الشركة أو العملة.'))
            if line.amount != record.deposited_amount or record.bank_reference not in (line.payment_ref or ''):
                raise ValidationError(_('لا يمكن المطابقة بالاعتماد على المبلغ وحده؛ تحقق من مرجع البنك والمبلغ.'))
            clearing = record.company_id.deposit_clearing_account_id
            if not clearing:
                raise ValidationError(_('يرجى إعداد حساب مقاصة الإيداع.'))
            move = self.env['account.move'].create({'move_type': 'entry', 'journal_id': record.bank_journal_id.id, 'date': record.deposit_date, 'ref': record.bank_reference, 'line_ids': [
                (0, 0, {'name': record.name, 'account_id': record.bank_account_id.id, 'debit': record.deposited_amount}),
                (0, 0, {'name': record.name, 'account_id': clearing.id, 'credit': record.deposited_amount}),
            ]})
            move.action_post()
            record.write({'account_move_id': move.id, 'state': 'reconciled'})

    def unlink(self):
        if any(record.state not in ('draft', 'cancelled') for record in self):
            raise ValidationError(_('لا يمكن حذف إيداع تمت معالجته.'))
        return super().unlink()
