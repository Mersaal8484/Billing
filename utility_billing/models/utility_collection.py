from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class UtilityCollection(models.Model):
    _name = 'utility.collection'
    _description = 'تحصيل فاتورة كهرباء'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'collection_date desc, id desc'

    name = fields.Char('المرجع', required=True, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    collection_date = fields.Datetime('تاريخ التحصيل', required=True, default=fields.Datetime.now)
    payment_id = fields.Many2one('account.payment', required=True, ondelete='restrict', index=True)
    allocation_id = fields.Many2one('utility.payment.allocation', required=True, ondelete='restrict', index=True)
    utility_customer_id = fields.Many2one('utility.customer', related='payment_id.utility_customer_id', store=True, readonly=True)
    owner_partner_id = fields.Many2one('res.partner', related='utility_customer_id.owner_partner_id', store=True, readonly=True)
    accounting_partner_id = fields.Many2one('res.partner', related='utility_customer_id.partner_id', store=True, readonly=True)
    sale_order_id = fields.Many2one('sale.order', related='payment_id.utility_sale_order_id', store=True, readonly=True)
    invoice_id = fields.Many2one('account.move', related='allocation_id.invoice_id', store=True, readonly=True)
    collector_id = fields.Many2one('utility.staff', required=True, index=True)
    collection_method = fields.Selection([
        ('field_collector', 'محصل ميداني'), ('bank_transfer', 'تحويل بنكي'),
        ('external_collection', 'محصل خارجي'), ('electronic', 'إلكتروني'),
        ('api', 'واجهة API'), ('other', 'أخرى'),
    ], required=True, default='field_collector')
    currency_id = fields.Many2one('res.currency', related='payment_id.currency_id', store=True, readonly=True)
    amount = fields.Monetary('المبلغ', related='payment_id.amount', store=True, readonly=True, currency_field='currency_id')
    settled_amount = fields.Monetary('المسدد للمحصل', compute='_compute_settled_amount', store=True, currency_field='currency_id')
    remaining_amount = fields.Monetary('المتبقي لدى المحصل', compute='_compute_settled_amount', store=True, currency_field='currency_id', index=True)
    external_reference = fields.Char('المرجع الخارجي', copy=False, index=True)
    source = fields.Selection([('manual', 'يدوي'), ('gateway', 'بوابة'), ('api', 'API')], default='manual', required=True)
    journal_id = fields.Many2one('account.journal', string='يومية التحصيل', readonly=True)
    state = fields.Selection([
        ('draft', 'مسودة'), ('confirmed', 'مؤكد'), ('posted', 'مرحّل'),
        ('included_in_settlement', 'ضمن التسوية'), ('settled', 'مسدد'), ('cancelled', 'ملغى'),
    ], default='draft', required=True, tracking=True, index=True)
    account_move_id = fields.Many2one('account.move', 'قيد الحيازة', readonly=True, copy=False)
    settlement_line_ids = fields.One2many('utility.collection.settlement.line', 'collection_id', readonly=True)
    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('collection_payment_uniq', 'unique(payment_id)', 'لا يجوز إنشاء أكثر من تحصيل لنفس الدفعة.'),
        ('collection_allocation_uniq', 'unique(allocation_id)', 'لا يجوز إنشاء أكثر من تحصيل لنفس التخصيص.'),
        ('collection_external_ref_uniq', 'unique(company_id, external_reference)', 'المرجع الخارجي للتحصيل مستخدم مسبقًا.'),
    ]

    @api.depends('settlement_line_ids.amount')
    def _compute_settled_amount(self):
        for record in self:
            record.settled_amount = sum(record.settlement_line_ids.mapped('amount'))
            record.remaining_amount = record.amount - record.settled_amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('name', self.env['ir.sequence'].next_by_code('utility.collection') or _('جديد'))
        records = super().create(vals_list)
        for record in records:
            if record.payment_id.company_id != record.company_id:
                raise ValidationError(_('شركة التحصيل يجب أن تطابق شركة الدفعة.'))
            if record.payment_id.state != 'posted' or record.allocation_id.state != 'reconciled':
                raise ValidationError(_('لا يمكن إنشاء تحصيل قبل ترحيل الدفعة وتسوية تخصيصها.'))
            if record.allocation_id.payment_id != record.payment_id:
                raise ValidationError(_('تخصيص التحصيل لا يطابق الدفعة المحددة.'))
            if record.collector_id.company_id != record.company_id:
                raise ValidationError(_('المحصل يجب أن ينتمي إلى نفس الشركة.'))
        return records

    def _get_accounts(self):
        company = self.company_id
        if not company.collector_receivable_account_id or not company.collection_clearing_account_id:
            raise ValidationError(_('يرجى إعداد حساب ذمم المحصل وحساب مقاصة التحصيل أولًا.'))
        journal = company.collection_journal_id or self.collector_id.collection_journal_id
        if not journal:
            raise ValidationError(_('يرجى إعداد يومية التحصيل قبل ترحيل التحصيل.'))
        return journal, company.collector_receivable_account_id, company.collection_clearing_account_id

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                continue
            if record.payment_id.state != 'posted' or record.allocation_id.state != 'reconciled':
                raise ValidationError(_('التحصيل يتطلب دفعة مرحلة وتخصيصًا تمت تسويته.'))
            record.state = 'confirmed'
        return True

    def action_post(self):
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError(_('يجب تأكيد التحصيل قبل ترحيله.'))
            journal, collector_account, clearing_account = record._get_accounts()
            collector_partner = record.collector_id.partner_id
            if not collector_partner:
                raise ValidationError(_('يجب ربط المحصل بشريك محاسبي.'))
            move = self.env['account.move'].create({
                'move_type': 'entry', 'journal_id': journal.id,
                'date': fields.Date.context_today(record),
                'ref': _('حيازة تحصيل %s') % record.name,
                'line_ids': [(0, 0, {
                    'name': record.name, 'account_id': collector_account.id,
                    'partner_id': collector_partner.id, 'debit': record.amount,
                }), (0, 0, {
                    'name': record.name, 'account_id': clearing_account.id,
                    'credit': record.amount,
                })],
            })
            move.action_post()
            record.write({'account_move_id': move.id, 'journal_id': journal.id, 'state': 'posted'})
        return True

    def action_cancel(self):
        if any(record.state in ('posted', 'included_in_settlement', 'settled') for record in self):
            raise ValidationError(_('لا يمكن إلغاء تحصيل مرحّل؛ استخدم إجراء عكس معتمد.'))
        self.write({'state': 'cancelled'})


class UtilityCollectionSettlementLine(models.Model):
    _name = 'utility.collection.settlement.line'
    _description = 'بند تسوية تحصيل'
    settlement_id = fields.Many2one('utility.collection.settlement', required=True, ondelete='cascade')
    collection_id = fields.Many2one('utility.collection', required=True, ondelete='restrict')
    amount = fields.Monetary(required=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='settlement_id.currency_id', store=True, readonly=True)
    _sql_constraints = [('settlement_collection_uniq', 'unique(settlement_id, collection_id)', 'لا يجوز تكرار التحصيل في التسوية.')]


class UtilityCollectionSettlement(models.Model):
    _name = 'utility.collection.settlement'
    _description = 'تسوية عهدة محصل'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'settlement_date desc, id desc'

    name = fields.Char('المرجع', required=True, readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    collector_id = fields.Many2one('utility.staff', required=True, index=True)
    settlement_date = fields.Date('تاريخ التسوية', required=True, default=fields.Date.today)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('utility.collection.settlement.line', 'settlement_id', string='التحصيلات')
    expected_amount = fields.Monetary('المتوقع', compute='_compute_amounts', store=True, currency_field='currency_id')
    declared_amount = fields.Monetary('المصرح بتسليمه', currency_field='currency_id')
    difference_amount = fields.Monetary('الفرق', compute='_compute_amounts', store=True, currency_field='currency_id')
    settlement_method = fields.Selection([('cash', 'نقدي'), ('bank_transfer', 'تحويل بنكي'), ('external', 'جهة خارجية')], required=True, default='cash')
    state = fields.Selection([('draft', 'مسودة'), ('confirmed', 'مؤكد'), ('posted', 'مرحّل'), ('deposited', 'مودع'), ('reconciled', 'مطابق'), ('cancelled', 'ملغى')], default='draft', tracking=True)
    account_move_id = fields.Many2one('account.move', readonly=True, copy=False)
    reference = fields.Char('المرجع')
    notes = fields.Text('ملاحظات')
    _sql_constraints = [('settlement_ref_uniq', 'unique(company_id, name)', 'مرجع التسوية يجب أن يكون فريدًا.')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('name', self.env['ir.sequence'].next_by_code('utility.collection.settlement') or _('جديد'))
        return super().create(vals_list)

    @api.depends('line_ids.amount', 'declared_amount')
    def _compute_amounts(self):
        for record in self:
            record.expected_amount = sum(record.line_ids.mapped('amount'))
            record.difference_amount = record.declared_amount - record.expected_amount

    def action_confirm(self):
        for record in self:
            if record.state != 'draft' or not record.line_ids:
                raise ValidationError(_('أضف تحصيلات مؤهلة قبل تأكيد التسوية.'))
            for line in record.line_ids:
                collection = line.collection_id
                if (collection.state != 'posted' or collection.collector_id != record.collector_id
                        or collection.company_id != record.company_id or collection.currency_id != record.currency_id
                        or collection.remaining_amount < line.amount or line.amount <= 0):
                    raise ValidationError(_('أحد تحصيلات التسوية غير مؤهل أو تجاوز المتبقي.'))
            record.state = 'confirmed'
        return True

    def action_post(self):
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError(_('يجب تأكيد التسوية قبل ترحيلها.'))
            company = record.company_id
            if not company.deposit_clearing_account_id or not company.collector_receivable_account_id or not company.settlement_journal_id:
                raise ValidationError(_('يرجى إعداد حساب مقاصة الإيداع وذمم المحصل ويومية التسويات.'))
            collector_partner = record.collector_id.partner_id
            if not collector_partner:
                raise ValidationError(_('يجب ربط المحصل بشريك محاسبي.'))
            lines = [(0, 0, {'name': record.name, 'account_id': company.deposit_clearing_account_id.id, 'debit': record.declared_amount})]
            collector_credit = min(record.declared_amount, record.expected_amount)
            lines.append((0, 0, {'name': record.name, 'account_id': company.collector_receivable_account_id.id, 'partner_id': collector_partner.id, 'credit': collector_credit}))
            if record.difference_amount > 0:
                if not company.collection_surplus_account_id:
                    raise ValidationError(_('يرجى إعداد حساب فائض التحصيل قبل تسجيل فائض.'))
                lines.append((0, 0, {'name': _('فائض %s') % record.name, 'account_id': company.collection_surplus_account_id.id, 'credit': record.difference_amount}))
            move = self.env['account.move'].create({'move_type': 'entry', 'journal_id': company.settlement_journal_id.id, 'date': record.settlement_date, 'ref': record.name, 'line_ids': lines})
            move.action_post()
            record.write({'account_move_id': move.id, 'state': 'posted'})
            record.line_ids.mapped('collection_id').write({'state': 'included_in_settlement'})
        return True

    def unlink(self):
        if any(record.state not in ('draft', 'cancelled') for record in self):
            raise ValidationError(_('لا يمكن حذف تسوية مرحّلة.'))
        return super().unlink()
