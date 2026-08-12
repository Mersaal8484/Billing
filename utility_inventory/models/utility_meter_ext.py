from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterExt(models.Model):
    _inherit = 'utility.meter'

    product_id = fields.Many2one('product.product', 'المنتج', ondelete='restrict',
                                  help='منتج العداد المستخدم في المخزون لتتبع الرقم التسلسلي')
    lot_id = fields.Many2one('stock.lot', 'الرقم التسلسلي (Lot/Serial)', ondelete='restrict',
                             help='ربط العداد بالرقم التسلسلي في نظام المخزون')

    @api.constrains('product_id', 'lot_id', 'company_id')
    def _check_utility_inventory_serial_integrity(self):
        for meter in self:
            if meter.lot_id and meter.product_id:
                if meter.lot_id.product_id != meter.product_id:
                    raise ValidationError(_(
                        'الرقم التسلسلي (%s) غير مطابق لمنتج العداد (%s).'
                    ) % (meter.lot_id.name, meter.product_id.display_name))
            if meter.product_id and meter.product_id.tracking != 'serial':
                raise ValidationError(_(
                    'منتج العداد (%s) يجب أن يكون مهدأ بالتتبع التسلسلي (serial tracking).'
                ) % meter.product_id.display_name)
            if meter.lot_id:
                duplicate = self.search([
                    ('id', '!=', meter.id),
                    ('lot_id', '=', meter.lot_id.id),
                    ('active', '=', True),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'الرقم التسلسلي (%s) مستخدم مسبقًا لعداد آخر (%s).'
                    ) % (meter.lot_id.name, duplicate.meter_number or duplicate.display_name))
                if meter.lot_id.company_id and meter.company_id and meter.lot_id.company_id != meter.company_id:
                    raise ValidationError(_(
                        'شركة الرقم التسلسلي تسند إلى شركة مختلفة عن العداد.'
                    ))
                if hasattr(meter.lot_id, 'location_id') and meter.lot_id.location_id:
                    if getattr(meter.lot_id.location_id, 'scrap_location', False):
                        raise ValidationError(_(
                            'لا يمكن اختيار رقم تسلسلي مكهن أو تالف من مخزن الخردة.'
                        ))
