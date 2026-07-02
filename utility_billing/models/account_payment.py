from odoo import api, fields, models, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    utility_sale_order_id = fields.Many2one('sale.order', string='فاتورة الكهرباء', index=True)
    utility_payment_method = fields.Selection([
        ('cash', 'نقدي'),
        ('bank', 'بنكي'),
        ('electronic', 'إلكتروني'),
    ], string='طريقة دفع الكهرباء')
    electronic_doc_no = fields.Char(string='رقم المستند الإلكتروني')
    is_invoice_verified = fields.Boolean(string='تم التحقق من الفاتورة')
    cashier_shift_id = fields.Many2one('utility.cashier.shift', string='الوردية',
        default=lambda self: self._default_cashier_shift())
    collector_shift_id = fields.Many2one('utility.collector.shift', string='يومية التحصيل',
        default=lambda self: self._default_collector_shift())
    date_range_id = fields.Many2one('date.range', string='الفترة', 
        default=lambda self: self.env['date.range'].search([('is_current_period', '=', True), ('work_type', '=', 'payment')], limit=1))

    @api.model
    def _default_cashier_shift(self):
        if self.env.context.get('cashier_shift_id'):
            return self.env.context['cashier_shift_id']
        shift = self.env['utility.cashier.shift'].search([
            ('cashier_id', '=', self.env.user.id),
            ('state', '=', 'open'),
        ], limit=1)
        return shift.id if shift else False

    @api.model
    def _default_collector_shift(self):
        if self.env.context.get('collector_shift_id'):
            return self.env.context['collector_shift_id']
        shift = self.env['utility.collector.shift'].search([
            ('collector_id', '=', self.env.user.id),
            ('state', '=', 'open'),
        ], limit=1)
        return shift.id if shift else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'journal_id' in fields_list and not res.get('journal_id'):
            if self.env.user.collection_journal_id:
                res['journal_id'] = self.env.user.collection_journal_id.id
        return res

    def action_post(self):
        res = super().action_post()
        for payment in self.filtered('utility_sale_order_id'):
            payment._reconcile_utility_sale_order()
        return res

    def _reconcile_utility_sale_order(self):
        self.ensure_one()
        order = self.utility_sale_order_id
        if not order or not self.move_id:
            return
        invoices = order.invoice_ids.filtered(lambda m: m.state == 'posted' and m.payment_state != 'paid')
        if not invoices:
            return
        payment_lines = self.move_id.line_ids.filtered(
            lambda line: not line.reconciled and line.account_id.account_type == 'asset_receivable'
        )
        invoice_lines = invoices.mapped('line_ids').filtered(
            lambda line: not line.reconciled and line.account_id.account_type == 'asset_receivable'
        )
        lines = payment_lines | invoice_lines
        if lines:
            lines.reconcile()
