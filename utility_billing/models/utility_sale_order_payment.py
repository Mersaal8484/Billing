from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date


class UtilitySaleOrderPayment(models.Model):
    _inherit = 'sale.order'

    def _get_or_create_collector_cash_account(self, user, company):
        account_model = self.env['account.account']
        account_name = _('حساب صندوق - %s') % user.name
        account = account_model.search([
            ('name', '=', account_name),
            ('company_id', '=', company.id),
        ], limit=1)
        if account:
            return account

        base_code = '1019%s' % str(user.id).zfill(4)
        used_codes = set(account_model.search([
            ('company_id', '=', company.id),
            ('code', '=like', '%s%%' % base_code),
        ]).mapped('code'))
        account_code = base_code
        suffix = 1
        while account_code in used_codes:
            account_code = '%s%s' % (base_code, suffix)
            suffix += 1
        return account_model.create({
            'name': account_name,
            'code': account_code,
            'account_type': 'asset_cash',
            'company_id': company.id,
        })

    def _get_or_create_outstanding_receipts_account(self, company):
        account_model = self.env['account.account']
        account_name = _('حساب الإيصالات والدفعات المستحقة')
        account = account_model.search([
            ('company_id', '=', company.id),
            ('name', '=', account_name),
            ('account_type', 'in', ('asset_current', 'asset_cash')),
        ], limit=1)
        if account:
            return account
        base_code = '101200'
        used_codes = set(account_model.search([
            ('company_id', '=', company.id),
            ('code', '=like', '%s%%' % base_code),
        ]).mapped('code'))
        account_code = base_code
        suffix = 1
        while account_code in used_codes:
            account_code = '%s%s' % (base_code, suffix)
            suffix += 1
        return account_model.create({
            'name': account_name,
            'code': account_code,
            'account_type': 'asset_current',
            'company_id': company.id,
        })

    def _get_unique_collector_journal_code(self, user, company):
        journal_model = self.env['account.journal']
        base_code = 'U%s' % str(user.id).zfill(3)[-4:]
        used_codes = set(journal_model.search([
            ('company_id', '=', company.id),
            ('code', '=like', 'U%'),
        ]).mapped('code'))
        if base_code not in used_codes:
            return base_code
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        prefix = base_code[:4]
        for suffix in alphabet:
            candidate = '%s%s' % (prefix, suffix)
            if candidate not in used_codes:
                return candidate
        raise ValidationError(_(
            'تعذر توليد رمز فريد ليومية تحصيل المستخدم %s.') % user.name)

    def _ensure_collector_journal(self):
        self.ensure_one()
        current_user = self.env.user
        journal = current_user.collection_journal_id
        if journal and journal.company_id != self.company_id:
            journal = False

        if not journal:
            journal_name = _('يومية تحصيل - %s') % current_user.name
            journal = self.env['account.journal'].search([
                ('company_id', '=', self.company_id.id),
                ('type', '=', 'cash'),
                ('name', '=', journal_name),
            ], limit=1)
            if not journal:
                cash_account = self._get_or_create_collector_cash_account(
                    current_user, self.company_id)
                journal = self.env['account.journal'].create({
                    'name': journal_name,
                    'code': self._get_unique_collector_journal_code(
                        current_user, self.company_id),
                    'type': 'cash',
                    'company_id': self.company_id.id,
                    'default_account_id': cash_account.id,
                })
            current_user.sudo().write({'collection_journal_id': journal.id})
        return journal

    def _ensure_payment_accounts(self, journal):
        company = journal.company_id
        if not company.account_journal_payment_debit_account_id or not company.account_journal_payment_credit_account_id:
            outstanding_acc = self._get_or_create_outstanding_receipts_account(company)
            c_vals = {}
            if not company.account_journal_payment_debit_account_id:
                c_vals['account_journal_payment_debit_account_id'] = outstanding_acc.id
            if not company.account_journal_payment_credit_account_id:
                c_vals['account_journal_payment_credit_account_id'] = outstanding_acc.id
            if c_vals:
                company.sudo().write(c_vals)

        j_vals = {}
        current_user = self.env.user
        cash_acc = journal.default_account_id
        expected_account_name = _('حساب صندوق - %s') % current_user.name
        if not cash_acc or cash_acc.name != expected_account_name:
            cash_acc = self._get_or_create_collector_cash_account(current_user, company)
            j_vals['default_account_id'] = cash_acc.id

        LineModel = self.env['account.payment.method.line']
        acc_field = 'payment_account_id' if hasattr(LineModel, 'payment_account_id') else ('outstanding_account_id' if hasattr(LineModel, 'outstanding_account_id') else False)
        target_out_acc = company.account_journal_payment_debit_account_id.id if company.account_journal_payment_debit_account_id else (cash_acc.id if cash_acc else False)

        if not journal.inbound_payment_method_line_ids:
            manual_inbound = self.env['account.payment.method'].search([
                ('payment_type', '=', 'inbound'),
                ('code', '=', 'manual')
            ], limit=1)
            if manual_inbound:
                m_line = {'name': 'يدوي', 'payment_method_id': manual_inbound.id}
                if acc_field and target_out_acc:
                    m_line[acc_field] = target_out_acc
                j_vals['inbound_payment_method_line_ids'] = [(0, 0, m_line)]
        elif acc_field and target_out_acc:
            for line in journal.inbound_payment_method_line_ids:
                if not getattr(line, acc_field, False):
                    line.sudo().write({acc_field: target_out_acc})

        if not journal.outbound_payment_method_line_ids:
            manual_outbound = self.env['account.payment.method'].search([
                ('payment_type', '=', 'outbound'),
                ('code', '=', 'manual')
            ], limit=1)
            if manual_outbound:
                m_line = {'name': 'يدوي', 'payment_method_id': manual_outbound.id}
                if acc_field and target_out_acc:
                    m_line[acc_field] = target_out_acc
                j_vals['outbound_payment_method_line_ids'] = [(0, 0, m_line)]
        elif acc_field and target_out_acc:
            for line in journal.outbound_payment_method_line_ids:
                if not getattr(line, acc_field, False):
                    line.sudo().write({acc_field: target_out_acc})

        if j_vals:
            journal.sudo().write(j_vals)

        return journal

    def action_register_utility_payment(self):
        self.ensure_one()
        journal = self._ensure_collector_journal()
        journal = self._ensure_payment_accounts(journal)

        return {
            'name': _('تسجيل تحصيل الفاتورة'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_partner_id': self.partner_id.id,
                'default_amount': self.balance_due if self.balance_due > 0 else self.amount_total,
                'default_utility_sale_order_id': self.id,
                'default_journal_id': journal.id if journal else False,
            }
        }

    def _get_posted_utility_moves(self):
        self.ensure_one()
        return (self.invoice_ids | self.utility_move_ids).filtered(
            lambda move: move.state == 'posted' and move.move_type in ('out_invoice', 'out_refund')
        )

    @api.depends(
        'amount_total', 'amount_penalty', 'state', 'date_order',
        'invoice_ids.state', 'invoice_ids.payment_state',
        'invoice_ids.amount_total', 'invoice_ids.amount_residual', 'invoice_ids.move_type',
        'utility_move_ids.state', 'utility_move_ids.payment_state',
        'utility_move_ids.amount_total', 'utility_move_ids.amount_residual', 'utility_move_ids.move_type')
    def _compute_payment(self):
        for r in self:
            posted_moves = r._get_posted_utility_moves()
            if posted_moves:
                signed_total = sum(
                    -move.amount_total if move.move_type == 'out_refund' else move.amount_total
                    for move in posted_moves
                )
                signed_residual = sum(
                    -move.amount_residual if move.move_type == 'out_refund' else move.amount_residual
                    for move in posted_moves
                )
                r.amount_paid = signed_total - signed_residual
                r.balance_due = signed_residual
            else:
                r.amount_paid = 0.0
                r.balance_due = r.amount_total + r.amount_penalty
            r.is_overdue = r.balance_due > 0 and r.date_order and r.date_order.date() < date.today()

    @api.depends('state', 'is_overdue', 'balance_due', 'invoice_ids.state', 'invoice_ids.payment_state', 'utility_move_ids.state', 'utility_move_ids.payment_state')
    def _compute_bill_state(self):
        for r in self:
            if r.state == 'cancel':
                r.bill_state = 'cancelled'
            elif r.state == 'draft':
                r.bill_state = 'draft'
            else:
                posted_invoices = r._get_posted_utility_moves()
                if posted_invoices and r.balance_due <= 0:
                    r.bill_state = 'paid'
                elif r.is_overdue:
                    r.bill_state = 'overdue'
                elif posted_invoices:
                    r.bill_state = 'sent'
                elif r.state == 'sale':
                    r.bill_state = 'confirmed'
                else:
                    r.bill_state = 'draft'

    @api.depends('penalty_ids.amount', 'penalty_ids.state')
    def _compute_amount_penalty(self):
        for r in self:
            r.amount_penalty = sum(
                r.penalty_ids.filtered(lambda p: p.state == 'applied').mapped('amount')
            )
