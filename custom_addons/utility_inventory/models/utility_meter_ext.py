from odoo import fields, models


class UtilityMeterExt(models.Model):
    _inherit = 'utility.meter'

    product_id = fields.Many2one('product.product', 'المنتج', ondelete='restrict',
                                  help='منتج العداد المستخدم في المخزون لتتبع الرقم التسلسلي')
    lot_id = fields.Many2one('stock.lot', 'الرقم التسلسلي (Lot/Serial)', ondelete='restrict',
                             help='ربط العداد بالرقم التسلسلي في نظام المخزون')
