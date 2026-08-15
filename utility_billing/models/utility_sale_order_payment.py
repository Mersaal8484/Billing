from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date


class UtilitySaleOrderPayment(models.Model):
    _inherit = 'sale.order'

    # ── Removed: _get_or_create_collector_cash_account()         (Phase 5 P0)
    # ── Removed: _get_or_create_outstanding_receipts_account()   (Phase 5 P0)
    # ── Removed: _get_unique_collector_journal_code()            (Phase 5 P0)
    # ── Removed: _ensure_payment_accounts()                      (Phase 5 P0)
    #
    # Rationale: these methods silently created account.account and
    # account.journal records during live payment transactions, violating the
    # production invariant that no CoA mutation may occur at runtime.
    #
    # Collector accounting setup must be performed explicitly by an
    # Accounting Manager or Utility Admin via:
    #   utility.staff → action_create_cash_journal()
    #
    # If a collector's journal is not pre-configured, action_register_utility_payment()
    # below raises a clear ValidationError with an actionable message.

    def _ensure_collector_journal(self):
        """Locate the collector's pre-configured cash journal — fail closed if missing.

        Does NOT create any accounting records. Raises ValidationError if:
          - The calling user has no utility.staff record with collector role
          - The staff record has no collection_journal_id configured
          - The configured journal is not a valid cash journal
        """
        self.ensure_one()
        staff = self.env['utility.staff'].search([
            ('user_id', '=', self.env.user.id),
            ('company_id', '=', self.company_id.id),
            ('role_ids.code', '=', 'collector'),
        ], limit=1)
        if not staff or not staff.collection_journal_id:
            raise ValidationError(_(
                'ACCOUNTING_CONFIG_MISSING: '
                'لا توجد يومية نقدية مستقلة مهيأة لهذا المتحصل. '
                'يجب على مدير المحاسبة أو مدير النظام إعداد يومية التحصيل '
                'عبر سجل الموظف → إجراء "إنشاء يومية التحصيل".'
            ))
        journal = staff.collection_journal_id
        if journal.type != 'cash':
            raise ValidationError(_(
                'ACCOUNTING_CONFIG_INVALID: '
                'يومية المتحصل %s ليست يومية نقدية (cash). '
                'يرجى تصحيح الإعداد من سجل الموظف.'
            ) % journal.name)
        if not journal.default_account_id:
            raise ValidationError(_(
                'ACCOUNTING_CONFIG_INVALID: '
                'يومية المتحصل %s ليس لها حساب صندوق مستقل. '
                'يرجى تكوين الحساب الافتراضي لليومية.'
            ) % journal.name)
        return journal

    def action_register_utility_payment(self):
        self.ensure_one()
        journal = self._ensure_collector_journal()
        if journal.company_id != self.company_id:
            raise ValidationError(_(
                'لم يتم إعداد يومية التحصيل لهذا المستخدم والشركة. '
                'يجب على المحاسب إعدادها قبل تسجيل الدفعات.'
            ))
        if (not journal.default_account_id
                or not self.company_id.account_journal_payment_debit_account_id
                or not self.company_id.account_journal_payment_credit_account_id):
            raise ValidationError(_(
                'إعدادات حسابات الدفعات غير مكتملة في الشركة أو اليومية. '
                'لا يمكن إنشاؤها أثناء تسجيل التحصيل.'
            ))
        if not journal.inbound_payment_method_line_ids:
            raise ValidationError(_('يجب إعداد طريقة دفع واردة في يومية التحصيل.'))
        posted_moves = self._get_posted_utility_moves()

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
                'default_amount': (
                    posted_moves.amount_residual
                    if len(posted_moves) == 1 and posted_moves.amount_residual > 0
                    else self.balance_due if self.balance_due > 0 else self.amount_total
                ),
                'default_utility_sale_order_id': self.id,
                'default_utility_invoice_id': (
                    posted_moves.id if len(posted_moves) == 1 else False
                ),
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
