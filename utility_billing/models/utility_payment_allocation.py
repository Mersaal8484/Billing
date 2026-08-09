from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class UtilityPaymentAllocation(models.Model):
    _name = 'utility.payment.allocation'
    _description = 'تخصيص دفعة كهرباء'
    _order = 'allocation_date desc, id desc'

    name = fields.Char('المرجع', required=True, copy=False, readonly=True)
    company_id = fields.Many2one(
        'res.company', related='payment_id.company_id', store=True,
        readonly=True, index=True)
    payment_id = fields.Many2one(
        'account.payment', string='الدفعة', required=True, ondelete='restrict',
        index=True, check_company=True)
    utility_customer_id = fields.Many2one(
        'utility.customer', related='payment_id.utility_customer_id',
        string='حساب الكهرباء', store=True, readonly=True, index=True)
    sale_order_id = fields.Many2one(
        'sale.order', related='payment_id.utility_sale_order_id',
        string='فاتورة الكهرباء', store=True, readonly=True, index=True)
    invoice_id = fields.Many2one(
        'account.move', string='الفاتورة المحاسبية', required=True,
        ondelete='restrict', index=True, check_company=True,
        domain="[('utility_sale_order_id', '=', sale_order_id), ('state', '=', 'posted')]" )
    partner_id = fields.Many2one(
        'res.partner', related='payment_id.partner_id', string='الشريك المحاسبي',
        store=True, readonly=True, index=True)
    currency_id = fields.Many2one(
        'res.currency', related='payment_id.currency_id', store=True,
        readonly=True)

    requested_amount = fields.Monetary('المبلغ المطلوب', currency_field='currency_id')
    allocated_amount = fields.Monetary('المبلغ المخصص', currency_field='currency_id')
    residual_before = fields.Monetary('المتبقي قبل التخصيص', currency_field='currency_id')
    residual_after = fields.Monetary('المتبقي بعد التخصيص', currency_field='currency_id')
    allocation_date = fields.Datetime(
        'تاريخ التخصيص', required=True, default=fields.Datetime.now, index=True)
    source = fields.Selection([
        ('cashier', 'تحصيل نقدي'),
        ('bank', 'تحويل بنكي'),
        ('gateway', 'بوابة دفع'),
        ('api', 'واجهة API'),
        ('migration', 'ترحيل'),
    ], string='المصدر', required=True, default='cashier', index=True)
    external_reference = fields.Char('المرجع الخارجي', index=True, copy=False)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('allocated', 'مخصص'),
        ('reconciled', 'تمت التسوية'),
        ('cancelled', 'ملغى'),
        ('error', 'خطأ'),
    ], string='الحالة', required=True, default='draft', index=True)
    partial_reconcile_ids = fields.Many2many(
        'account.partial.reconcile', 'utility_payment_allocation_partial_rel',
        'allocation_id', 'partial_reconcile_id', string='تسويات محاسبية',
        readonly=True, copy=False)
    reconciliation_reference = fields.Char('مرجع التسوية', readonly=True, copy=False)
    created_by = fields.Many2one(
        'res.users', string='أنشأه', default=lambda self: self.env.user,
        required=True, readonly=True)
    notes = fields.Text('ملاحظات')
    error_message = fields.Text('رسالة الخطأ', readonly=True)

    def init(self):
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS utility_payment_allocation_ext_uniq
                ON utility_payment_allocation
                   (source, external_reference, utility_customer_id)
             WHERE external_reference IS NOT NULL AND external_reference <> ''
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) in (False, _('New')):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'utility.payment.allocation') or _('New')
        return super().create(vals_list)

    @api.constrains('payment_id', 'invoice_id', 'partner_id', 'utility_customer_id')
    def _check_allocation_context(self):
        for allocation in self:
            payment = allocation.payment_id
            invoice = allocation.invoice_id
            customer = allocation.utility_customer_id
            if not payment or not invoice or not customer:
                continue
            if payment.utility_sale_order_id != invoice.utility_sale_order_id:
                raise ValidationError(_('الدفعة والفاتورة المحاسبية لا تخصان نفس فاتورة الكهرباء.'))
            if invoice.utility_customer_id != customer:
                raise ValidationError(_('الفاتورة المحاسبية لا تخص حساب الكهرباء المحدد.'))
            if payment.partner_id != customer.partner_id or invoice.partner_id != customer.partner_id:
                raise ValidationError(_('الشريك المحاسبي لا يطابق حساب الكهرباء.'))

    @staticmethod
    def _partial_ids(lines):
        partials = lines.mapped('matched_debit_ids') | lines.mapped('matched_credit_ids')
        return partials

    def _lock_invoice(self, invoice):
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT id FROM account_move WHERE id = %s FOR UPDATE', [invoice.id])
        invoice.invalidate_cache([
            'state', 'partner_id', 'move_type', 'amount_residual', 'payment_state'])

    def _resolve_source(self, payment):
        source = self.env.context.get('utility_payment_source')
        if source:
            return source
        if payment.utility_payment_method == 'electronic':
            return 'gateway'
        if payment.utility_payment_method == 'bank':
            return 'bank'
        return 'cashier'

    @api.model
    def allocate_payment(self, payment):
        """Create one auditable allocation and reconcile only its exact invoice."""
        payment.ensure_one()
        if not payment.utility_sale_order_id:
            return self.env['utility.payment.allocation']

        existing = self.search([
            ('payment_id', '=', payment.id),
            ('state', 'in', ('allocated', 'reconciled')),
        ], limit=1)
        if existing:
            return existing

        customer = payment.utility_customer_id
        order = payment.utility_sale_order_id
        invoice = payment.utility_invoice_id
        source = self._resolve_source(payment)
        external_reference = self.env.context.get(
            'utility_external_reference') or payment.electronic_doc_no

        if external_reference:
            duplicate = self.search([
                ('source', '=', source),
                ('external_reference', '=', external_reference),
                ('utility_customer_id', '=', customer.id),
                ('payment_id', '!=', payment.id),
                ('state', 'in', ('allocated', 'reconciled')),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'تم تسجيل المرجع الخارجي %s مسبقًا لهذه الدفعة.'
                ) % external_reference)

        if payment.state != 'posted' or not customer or not order or not invoice:
            raise ValidationError(_('بيانات الدفعة الكهربائية غير مكتملة للتخصيص.'))
        if payment.payment_type != 'inbound':
            raise ValidationError(_('تخصيص الدفعات الصادرة خارج نطاق تحصيل الكهرباء.'))

        self._lock_invoice(invoice)
        if (invoice.utility_sale_order_id != order
                or invoice.utility_customer_id != customer
                or payment.partner_id != customer.partner_id
                or invoice.partner_id != customer.partner_id):
            raise ValidationError(_('الدفعة والفاتورة لا تخصان نفس حساب الكهرباء.'))
        if invoice.state != 'posted' or invoice.move_type != 'out_invoice':
            raise ValidationError(_('الفاتورة المحددة ليست فاتورة تحصيل مرحلة.'))
        if invoice.amount_residual <= 0:
            raise ValidationError(_('الفاتورة المحددة مسددة بالكامل.'))
        if payment.amount <= 0 or payment.amount > invoice.amount_residual:
            raise ValidationError(_('مبلغ الدفعة يتجاوز المتبقي الحالي للفواتير المحددة.'))

        residual_before = invoice.amount_residual
        allocation = self.create({
            'payment_id': payment.id,
            'invoice_id': invoice.id,
            'requested_amount': payment.amount,
            'residual_before': residual_before,
            'source': source,
            'external_reference': external_reference,
            'state': 'allocated',
        })

        payment_lines = payment.move_id.line_ids.filtered(
            lambda line: (
                not line.reconciled
                and line.partner_id == invoice.partner_id
                and line.account_id.account_type == 'asset_receivable'
                and line.company_id == invoice.company_id
                and (not line.currency_id or line.currency_id == invoice.currency_id)
            ))
        invoice_lines = invoice.line_ids.filtered(
            lambda line: (
                not line.reconciled
                and line.partner_id == invoice.partner_id
                and line.account_id.account_type == 'asset_receivable'
                and line.company_id == invoice.company_id
                and (not line.currency_id or line.currency_id == invoice.currency_id)
            ))
        if not payment_lines or not invoice_lines:
            raise ValidationError(_('تعذر تحديد سطور الذمم المدينة للدفعة والفاتورة.'))

        before_partials = self._partial_ids(payment_lines | invoice_lines)
        payment_groups = defaultdict(lambda: self.env['account.move.line'])
        invoice_groups = defaultdict(lambda: self.env['account.move.line'])
        for line in payment_lines:
            payment_groups[(line.account_id.id, line.currency_id.id or invoice.currency_id.id)] |= line
        for line in invoice_lines:
            invoice_groups[(line.account_id.id, line.currency_id.id or invoice.currency_id.id)] |= line
        common_keys = sorted(set(payment_groups) & set(invoice_groups))
        if not common_keys:
            raise ValidationError(_('لا يوجد حساب ذمم مشترك بين الدفعة والفاتورة المحددة.'))
        for key in common_keys:
            (payment_groups[key] | invoice_groups[key]).reconcile()

        invoice.invalidate_cache(['amount_residual', 'payment_state'])
        residual_after = invoice.amount_residual
        allocated_amount = residual_before - residual_after
        currency = invoice.currency_id
        if (float_is_zero(allocated_amount, precision_rounding=currency.rounding)
                or float_compare(
                    residual_before - allocated_amount, residual_after,
                    precision_rounding=currency.rounding) != 0
                or float_compare(allocated_amount, payment.amount,
                                 precision_rounding=currency.rounding) != 0):
            raise ValidationError(_('فشل التحقق من ثابت المبلغ بعد التسوية المحاسبية.'))

        partials = self._partial_ids(payment_lines | invoice_lines) - before_partials
        allocation.write({
            'allocated_amount': allocated_amount,
            'residual_after': residual_after,
            'partial_reconcile_ids': [(6, 0, partials.ids)],
            'reconciliation_reference': ', '.join(partials.mapped('name')),
            'state': 'reconciled',
        })
        return allocation

    def action_cancel(self):
        for allocation in self:
            if allocation.state == 'reconciled':
                raise ValidationError(_('لا يمكن إلغاء تخصيص تمت تسويته؛ استخدم إجراء عكس معتمد.'))
        self.write({'state': 'cancelled'})
