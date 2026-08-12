from odoo import SUPERUSER_ID, api
from odoo.exceptions import ValidationError


def migrate(cr, version):
    """Safely convert legacy meter serials to stock lots before projection."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    meters = env['utility.meter'].search([('serial_number', '!=', False)])
    Lot = env['stock.lot']
    for meter in meters:
        serial = (meter.serial_number or '').strip()
        if not serial:
            continue
        if meter.lot_id:
            if meter.lot_id.name != serial:
                raise ValidationError(
                    'ترقية المخزون متوقفة: الرقم التسلسلي للعداد %s لا يطابق Lot/Serial.'
                    % meter.meter_number
                )
            continue
        if not meter.product_id or meter.product_id.tracking != 'serial':
            raise ValidationError(
                'ترقية المخزون متوقفة: العداد %s يحتاج منتجاً مهدأ بالتتبع التسلسلي.'
                % meter.meter_number
            )
        lot = Lot.search([
            ('name', '=', serial),
            ('product_id', '=', meter.product_id.id),
        ], limit=1)
        if lot and lot.company_id and lot.company_id != meter.company_id:
            raise ValidationError(
                'ترقية المخزون متوقفة: شركة Lot/Serial للعداد %s مختلفة.'
                % meter.meter_number
            )
        if not lot:
            lot = Lot.create({
                'name': serial,
                'product_id': meter.product_id.id,
                'company_id': meter.company_id.id,
            })
        meter.write({'lot_id': lot.id})
