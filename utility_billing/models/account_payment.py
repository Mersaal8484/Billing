from odoo import api, fields, models, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    utility_collection_id = fields.Many2one('utility.collection', string='تحصيل الكهرباء', index=True)
    utility_payment_method = fields.Selection([
        ('cash', 'نقدي'),
        ('bank', 'بنكي'),
        ('electronic', 'إلكتروني'),
    ], string='طريقة دفع الكهرباء')
    electronic_doc_no = fields.Char(string='رقم المستند الإلكتروني')
    is_invoice_verified = fields.Boolean(string='تم التحقق من الفاتورة')
