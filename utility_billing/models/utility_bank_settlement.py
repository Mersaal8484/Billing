from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class UtilityBankSettlementLine(models.Model):
    _name = 'utility.bank.settlement.line'
    _description = 'تخصيص تسوية بنكية'

    bank_settlement_id = fields.Many2one(
        'utility.bank.settlement', required=True, ondelete='cascade')
    collection_settlement_id = fields.Many2one(
        'utility.collection.settlement', required=True, ondelete='restrict')
    allocated_amount = fields.Monetary(
        required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        related='bank_settlement_id.currency_id', store=True, readonly=True)

    _sql_constraints = [
        ('bank_settlement_source_uniq',
         'unique(bank_settlement_id, collection_settlement_id)',
         'لا يجوز تكرار تسوية المصدر داخل الإيداع نفسه.'),
    ]


class UtilityBankSettlement(models.Model):
    _name = 'utility.bank.settlement'
    _description = 'إيداع وتسوية بنكية'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deposit_date desc, id desc'

    name = fields.Char('المرجع', required=True, readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        index=True)
    deposit_date = fields.Date(
        'تاريخ الإيداع', required=True, default=fields.Date.today)
    bank_journal_id = fields.Many2one(
        'account.journal', required=True,
        domain="[('type', '=', 'bank')]")
    bank_account_id = fields.Many2one('account.account', required=True)
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many(
        'utility.bank.settlement.line', 'bank_settlement_id',
        string='تسويات المصدر')
    expected_amount = fields.Monetary(
        'المبلغ المخصص', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    deposited_amount = fields.Monetary(
        'المبلغ المطابق لكشف البنك', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    remaining_to_deposit = fields.Monetary(
        'غير مخصص من هذا الإيداع', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    bank_reference = fields.Char(
        'مرجع البنك', required=True, copy=False)
    deposit_slip_number = fields.Char('رقم قسيمة الإيداع')
    state = fields.Selection([
        ('draft', 'مسودة'), ('confirmed', 'مؤكد'),
        ('waiting_bank_match', 'بانتظار مطابقة البنك'),
        ('reconciled', 'تمت المطابقة'), ('settled', 'تمت التسوية'),
        ('cancelled', 'ملغى')
    ], default='draft', tracking=True)
    statement_line_id = fields.Many2one(
        'account.bank.statement.line', readonly=True, copy=False)
    account_move_id = fields.Many2one(
        'account.move', string='حركة كشف البنك', readonly=True, copy=False)
    difference_amount = fields.Monetary(
        'الفرق', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('bank_reference_uniq', 'unique(company_id, bank_reference)',
         'مرجع البنك مستخدم مسبقًا.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault(
                'name', self.env['ir.sequence'].next_by_code(
                    'utility.bank.settlement') or _('جديد'))
        records = super().create(vals_list)
        for record in records:
            if record.company_id.currency_id != record.currency_id:
                raise ValidationError(
                    _('الإيداعات البنكية في هذه المرحلة يجب أن تكون بعملة الشركة.'))
            if record.bank_journal_id.company_id != record.company_id:
                raise ValidationError(_('يجب أن تنتمي اليومية البنكية إلى نفس الشركة.'))
        return records

    @api.depends('line_ids.allocated_amount')
    def _compute_amounts(self):
        for record in self:
            amount = sum(record.line_ids.mapped('allocated_amount'))
            record.expected_amount = amount
            record.deposited_amount = amount
            record.remaining_to_deposit = 0.0
            record.difference_amount = 0.0

    def _lock_sources(self):
        sources = self.mapped('line_ids.collection_settlement_id')
        self.env.flush_all()
        ids = tuple(sources.ids)
        if ids:
            self.env.cr.execute(
                'SELECT id FROM utility_collection_settlement '
                'WHERE id IN %s ORDER BY id FOR UPDATE', [ids])
        sources.invalidate_cache()
        return sources

    def _lock_statement_line(self):
        self.ensure_one()
        if not self.statement_line_id:
            return
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT id FROM account_bank_statement_line WHERE id = %s FOR UPDATE',
            [self.statement_line_id.id],
        )
        self.statement_line_id.invalidate_cache()

    def _validate_lines(self):
        self.ensure_one()
        if not self.line_ids:
            raise ValidationError(_('أضف تسويات محصل قبل تأكيد الإيداع.'))
        if self.currency_id != self.company_id.currency_id:
            raise ValidationError(
                _('الإيداع متعدد العملات غير مفعّل؛ استخدم عملة الشركة.'))
        for line in self.line_ids:
            source = line.collection_settlement_id
            if source.company_id != self.company_id or source.currency_id != self.currency_id:
                raise ValidationError(_('الشركة أو العملة لا تطابق تسوية المصدر.'))
            if source.state not in ('posted', 'deposited'):
                raise ValidationError(
                    _('لا يمكن إيداع تسوية محصل غير مرحّلة.'))
            if line.allocated_amount <= 0:
                raise ValidationError(_('مبلغ تخصيص الإيداع يجب أن يكون أكبر من صفر.'))
            available = source.remaining_to_deposit
            if line.bank_settlement_id.state != 'draft':
                available += line.allocated_amount
            if float_compare(
                    line.allocated_amount, available,
                    precision_rounding=self.currency_id.rounding) > 0:
                raise ValidationError(_(
                    'تخصيص الإيداع يتجاوز المتبقي غير المودع لتسوية %s.'
                ) % source.name)

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                continue
            record._lock_sources()
            record._validate_lines()
            record.state = 'confirmed'
        return True

    def action_post(self):
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError(
                    _('يجب تأكيد الإيداع قبل تنفيذ التسوية المالية.'))
            record._lock_sources()
            record._validate_lines()
            bank_account = record.bank_journal_id.default_account_id
            clearing = record.company_id.deposit_clearing_account_id
            if not bank_account or record.bank_journal_id.type != 'bank':
                raise ValidationError(_('يجب إعداد حساب السيولة في اليومية البنكية.'))
            if not clearing or not clearing.reconcile:
                raise ValidationError(_('يجب إعداد حساب مقاصة الإيداع كحساب قابل للتسوية.'))
            if float_compare(
                    record.deposited_amount, 0.0,
                    precision_rounding=record.currency_id.rounding) <= 0:
                raise ValidationError(_('يجب أن يحتوي الإيداع على مبلغ موجب.'))

            # The deposit is the source event: Dr Bank / Cr Deposit Clearing.
            # No bank statement or later matching step is involved.
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': record.bank_journal_id.id,
                'date': record.deposit_date,
                'ref': record.bank_reference,
                'line_ids': [
                    (0, 0, {
                        'name': record.bank_reference,
                        'account_id': bank_account.id,
                        'debit': record.deposited_amount,
                    }),
                    (0, 0, {
                        'name': record.bank_reference,
                        'account_id': clearing.id,
                        'credit': record.deposited_amount,
                    }),
                ],
            })
            move.action_post()
            bank_clearing_line = move.line_ids.filtered(
                lambda line: line.account_id == clearing and not line.reconciled)
            if len(bank_clearing_line) != 1:
                raise ValidationError(_('تعذر تحديد سطر مقاصة الإيداع في القيد البنكي.'))
            for allocation in record.line_ids.sorted('id'):
                source = allocation.collection_settlement_id
                source_line = source.account_move_id.line_ids.filtered(
                    lambda line: line.account_id == clearing and not line.reconciled)
                if len(source_line) != 1:
                    raise ValidationError(_(
                        'يجب أن يحتوي مصدر %s على سطر مقاصة إيداع غير مسدد واحد.'
                    ) % source.name)
                record._create_exact_partial_reconcile(
                    source_line, bank_clearing_line, allocation.allocated_amount)
            record.write({
                'account_move_id': move.id,
                'state': 'settled',
            })
            for source in record.line_ids.mapped('collection_settlement_id'):
                source.invalidate_recordset(['remaining_to_deposit'])
                source.write({
                    'state': 'reconciled'
                    if source.currency_id.is_zero(source.remaining_to_deposit)
                    else 'deposited'
                })
        return True

    def _get_statement_counterpart(self, statement_line, clearing):
        """Return the bank statement counterpart and reclassify suspense exactly."""
        move = statement_line.move_id
        liquidity = move.line_ids.filtered(
            lambda line: line.account_id == statement_line.journal_id.default_account_id
            or line.account_id.account_type in ('asset_cash', 'liability_credit_card'))
        if len(liquidity) != 1:
            raise ValidationError(_('حركة كشف البنك يجب أن تحتوي على سطر سيولة وحيد.'))
        if liquidity.account_id != self.bank_account_id:
            raise ValidationError(_('حساب السيولة في كشف البنك لا يطابق حساب البنك المحدد.'))
        candidates = move.line_ids.filtered(
            lambda line: line != liquidity and not line.reconciled)
        counterpart = candidates.filtered(
            lambda line: line.account_id == clearing)
        if not counterpart:
            suspense = candidates.filtered(
                lambda line: line.account_id == statement_line.journal_id.suspense_account_id)
            if len(suspense) != 1:
                raise ValidationError(_(
                    'تعذر تحديد سطر المقاصة في حركة كشف البنك. '
                    'يجب أن يكون السطر في حساب التعليق أو مقاصة الإيداع.'
                ))
            suspense.with_context(check_move_validity=False).write({
                'account_id': clearing.id,
            })
            counterpart = suspense
        if len(counterpart) != 1:
            raise ValidationError(_('يجب أن يكون لحركة كشف البنك سطر مقابل وحيد.'))
        return liquidity, counterpart

    def _create_exact_partial_reconcile(self, debit_line, credit_line, amount):
        """Reconcile exactly ``amount`` between one source and the bank line.

        ``account.move.line.reconcile()`` matches all available lines by order,
        which is unsafe when one bank deposit is allocated to several source
        settlements.  Creating the partial explicitly preserves the audit
        allocation on the bank settlement line.
        """
        self.ensure_one()
        rounding = self.currency_id.rounding
        for move_line in (debit_line, credit_line):
            if move_line.move_id.state != 'posted' or move_line.reconciled:
                raise ValidationError(_('لا يمكن مطابقة سطر محاسبي مرحّل أو مسدد.'))
            if move_line.account_id != debit_line.account_id:
                raise ValidationError(_('سطرا المطابقة يجب أن يكونا على نفس الحساب.'))
        if float_compare(amount, 0.0, precision_rounding=rounding) <= 0:
            raise ValidationError(_('مبلغ المطابقة يجب أن يكون أكبر من صفر.'))
        if float_compare(amount, debit_line.amount_residual,
                         precision_rounding=rounding) > 0:
            raise ValidationError(_('المبلغ المخصص أكبر من رصيد سطر المصدر.'))
        if float_compare(amount, -credit_line.amount_residual,
                         precision_rounding=rounding) > 0:
            raise ValidationError(_('المبلغ المخصص أكبر من رصيد سطر البنك.'))

        company_currency = self.company_id.currency_id
        partial = self.env['account.partial.reconcile'].with_context(
            check_move_validity=False,
        ).create({
            'debit_move_id': debit_line.id,
            'credit_move_id': credit_line.id,
            'amount': amount,
            'debit_amount_currency': amount if debit_line.currency_id == company_currency else 0.0,
            'credit_amount_currency': amount if credit_line.currency_id == company_currency else 0.0,
        })
        (debit_line | credit_line).invalidate_cache()

        involved_lines = (debit_line | credit_line)._all_reconciled_lines()
        if involved_lines and all(
                company_currency.is_zero(line.amount_residual)
                for line in involved_lines):
            involved_partials = (
                involved_lines.matched_debit_ids
                | involved_lines.matched_credit_ids
            )
            self.env['account.full.reconcile'].with_context(
                skip_invoice_sync=True,
                skip_invoice_line_sync=True,
                skip_account_move_synchronization=True,
                check_move_validity=False,
            ).create({
                'partial_reconcile_ids': [Command.set(involved_partials.ids)],
                'reconciled_line_ids': [Command.set(involved_lines.ids)],
            })
        return partial

    def action_reconcile(self):
        for record in self:
            if record.state != 'waiting_bank_match' or not record.statement_line_id:
                raise ValidationError(_('حدد سطر كشف بنكي فعلي قبل المطابقة.'))
            record._lock_sources()
            record._lock_statement_line()
            record._validate_lines()
            line = record.statement_line_id
            if line.company_id != record.company_id or line.journal_id != record.bank_journal_id:
                raise ValidationError(_('سطر البنك لا يطابق الشركة أو اليومية.'))
            if line.currency_id != record.currency_id:
                raise ValidationError(_('عملة سطر البنك لا تطابق عملة الإيداع.'))
            if float_compare(
                    line.amount, record.deposited_amount,
                    precision_rounding=record.currency_id.rounding) != 0:
                raise ValidationError(_('مبلغ سطر البنك لا يطابق مبلغ الإيداع المحدد.'))
            if record.bank_reference not in (line.payment_ref or ''):
                raise ValidationError(
                    _('مرجع البنك غير موجود في وصف سطر كشف البنك.'))
            if line.amount <= 0 or line.move_id.state != 'posted':
                raise ValidationError(_('يجب أن يكون سطر كشف البنك حركة واردة ومرحّلة.'))

            clearing = record.company_id.deposit_clearing_account_id
            if not clearing or not clearing.reconcile:
                raise ValidationError(
                    _('يجب إعداد حساب مقاصة الإيداع كحساب قابل للتسوية.'))
            _liquidity, bank_counterpart = record._get_statement_counterpart(
                line, clearing)

            if not record.line_ids:
                raise ValidationError(_('لا توجد تخصيصات مصدر للإيداع.'))
            for allocation in record.line_ids.sorted('id'):
                source = allocation.collection_settlement_id
                source_line = source.account_move_id.line_ids.filtered(
                    lambda aml: aml.account_id == clearing and not aml.reconciled)
                if len(source_line) != 1:
                    raise ValidationError(_(
                        'يجب أن يحتوي مصدر %s على سطر مقاصة إيداع غير مسدد واحد.'
                    ) % source.name)
                record._create_exact_partial_reconcile(
                    source_line, bank_counterpart, allocation.allocated_amount)
            line.invalidate_cache(['is_reconciled', 'amount_residual'])
            if not line.is_reconciled:
                raise ValidationError(_('لم تكتمل تسوية سطر كشف البنك.'))
            record.write({
                'statement_line_id': line.id,
                'account_move_id': line.move_id.id,
                'state': 'reconciled',
            })
            for source in record.line_ids.mapped('collection_settlement_id'):
                source.invalidate_cache()
                source_state = (
                    'reconciled'
                    if not source.remaining_to_deposit
                    and not source.account_move_id.line_ids.filtered(
                        lambda aml: aml.account_id == clearing and not aml.reconciled)
                    else 'deposited'
                )
                source.write({'state': source_state})
        return True

    def unlink(self):
        if any(record.state not in ('draft', 'cancelled') for record in self):
            raise ValidationError(_('لا يمكن حذف إيداع تمت معالجته.'))
        return super().unlink()
