from odoo import SUPERUSER_ID, api
from odoo.exceptions import ValidationError


def migrate(cr, version):
    """Safely convert legacy meter serials to stock lots before projection."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Read the legacy column directly: this hook runs while the old Core
    # field still exists and before Inventory installs its projection.
    cr.execute("""
        SELECT id, meter_number, serial_number, lot_id, product_id, company_id
          FROM utility_meter
         WHERE serial_number IS NOT NULL
           AND btrim(serial_number) <> ''
    """)
    meters = cr.fetchall()
    Lot = env['stock.lot']
    for meter_id, meter_number, legacy_serial, lot_id, product_id, company_id in meters:
        serial = legacy_serial.strip()
        if lot_id:
            lot = Lot.browse(lot_id).exists()
            if lot and lot.name != serial:
                raise ValidationError(
                    'ترقية المخزون متوقفة: الرقم التسلسلي للعداد %s لا يطابق Lot/Serial.'
                    % meter_number
                )
            continue
        product = env['product.product'].browse(product_id).exists()
        company = env['res.company'].browse(company_id).exists()
        if not product or product.tracking != 'serial':
            raise ValidationError(
                'ترقية المخزون متوقفة: العداد %s يحتاج منتجاً مهدأ بالتتبع التسلسلي.'
                % meter_number
            )
        lot = Lot.search([
            ('name', '=', serial),
            ('product_id', '=', product.id),
        ], limit=1)
        if lot and lot.company_id and company and lot.company_id != company:
            raise ValidationError(
                'ترقية المخزون متوقفة: شركة Lot/Serial للعداد %s مختلفة.'
                % meter_number
            )
        if not lot:
            lot = Lot.create({
                'name': serial,
                'product_id': product.id,
                'company_id': company.id,
            })
        cr.execute('UPDATE utility_meter SET lot_id = %s WHERE id = %s', [lot.id, meter_id])
