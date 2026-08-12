from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterExt(models.Model):
    _inherit = 'utility.meter'

    # Compatibility projection: stock.lot.name is the only physical serial
    # source once utility_inventory is installed.
    serial_number = fields.Char(
        related='lot_id.name', string='الرقم التسلسلي', store=True,
        readonly=True, index=True,
    )

    product_id = fields.Many2one('product.product', 'المنتج', ondelete='restrict',
                                  help='منتج العداد المستخدم في المخزون لتتبع الرقم التسلسلي')
    lot_id = fields.Many2one('stock.lot', 'الرقم التسلسلي (Lot/Serial)', ondelete='restrict',
                             help='ربط العداد بالرقم التسلسلي في نظام المخزون')

    @api.model_create_multi
    def create(self, vals_list):
        """Convert legacy serial input into the canonical stock lot."""
        Lot = self.env['stock.lot']
        for vals in vals_list:
            legacy_serial = (vals.pop('serial_number', None) or '').strip() or False
            if not legacy_serial:
                continue
            lot = Lot.browse(vals.get('lot_id')).exists() if vals.get('lot_id') else Lot
            if lot and lot.name != legacy_serial:
                raise ValidationError(_(
                    'الرقم التسلسلي المدخل لا يطابق الرقم التسلسلي في المخزون.'
                ))
            if not lot:
                product = self.env['product.product'].browse(vals.get('product_id')).exists()
                if not product:
                    raise ValidationError(_(
                        'يجب تحديد منتج مهدأ بالتتبع التسلسلي قبل إنشاء رقم عداد مادي.'
                    ))
                lot = Lot.search([
                    ('name', '=', legacy_serial),
                    ('product_id', '=', product.id),
                ], limit=1)
                if not lot:
                    lot = Lot.create({
                        'name': legacy_serial,
                        'product_id': product.id,
                        'company_id': vals.get('company_id') or self.env.company.id,
                    })
                vals['lot_id'] = lot.id
        return super().create(vals_list)

    def write(self, vals):
        """Reject independent serial edits and route legacy input to stock."""
        vals = dict(vals)
        if 'serial_number' in vals:
            legacy_serial = (vals.pop('serial_number') or '').strip() or False
            for meter in self:
                if legacy_serial and meter.lot_id and meter.lot_id.name != legacy_serial:
                    raise ValidationError(_(
                        'لا يمكن تعديل الرقم التسلسلي من شاشة العداد؛ عدّل رقم Lot/Serial في المخزون.'
                    ))
                if legacy_serial and not meter.lot_id:
                    product = meter.product_id
                    if not product:
                        raise ValidationError(_(
                            'يجب تحديد منتج مهدأ بالتتبع التسلسلي قبل ربط الرقم المادي.'
                        ))
                    lot = self.env['stock.lot'].search([
                        ('name', '=', legacy_serial),
                        ('product_id', '=', product.id),
                    ], limit=1) or self.env['stock.lot'].create({
                        'name': legacy_serial,
                        'product_id': product.id,
                        'company_id': meter.company_id.id,
                    })
                    vals['lot_id'] = lot.id
        return super().write(vals)

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
                scrap_quant = self.env['stock.quant'].search([
                    ('lot_id', '=', meter.lot_id.id),
                    ('quantity', '>', 0),
                    ('location_id.scrap_location', '=', True),
                ], limit=1)
                if scrap_quant:
                    raise ValidationError(_(
                        'لا يمكن اختيار رقم تسلسلي مكهن أو تالف من مخزن الخردة (%s).'
                    ) % scrap_quant.location_id.display_name)
