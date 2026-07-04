from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # --- Accounting ---
    fine_account_id = fields.Many2one(
        'account.account',
        string='حساب إيرادات الغرامات',
        check_company=True)
    discount_account_id = fields.Many2one(
        'account.account',
        string='حساب الخصومات / الإعفاءات',
        check_company=True)
    deposit_account_id = fields.Many2one(
        'account.account',
        string='حساب التأمينات',
        check_company=True)
    settlement_account_id = fields.Many2one(
        'account.account',
        string='حساب التسويات المالية',
        check_company=True)
    
    writeoff_journal_id = fields.Many2one(
        'account.journal',
        string='يومية الإعفاءات',
        check_company=True)
    deposit_journal_id = fields.Many2one(
        'account.journal',
        string='يومية التأمينات والودائع',
        check_company=True)
    settlement_journal_id = fields.Many2one(
        'account.journal',
        string='يومية التسويات',
        check_company=True)
    
    penalty_product_id = fields.Many2one(
        'product.product',
        string='منتج الغرامات',
        check_company=True)
    mu_allim_product_id = fields.Many2one(
        'product.product',
        string='منتج المعلم',
        check_company=True)
    cleaning_product_id = fields.Many2one(
        'product.product',
        string='منتج النظافة',
        check_company=True)
    local_fee_product_id = fields.Many2one(
        'product.product',
        string='منتج المجالس المحلية',
        check_company=True)

    writeoff_account_id = fields.Many2one(
        'account.account',
        string='حساب الإعفاءات',
        check_company=True)
    collection_journal_id = fields.Many2one(
        'account.journal',
        string='يومية التحصيل الافتراضية',
        check_company=True)
