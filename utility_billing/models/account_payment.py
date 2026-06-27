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
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'journal_id' in fields_list and not res.get('journal_id'):
            if self.env.user.collection_journal_id:
                res['journal_id'] = self.env.user.collection_journal_id.id
        return res
