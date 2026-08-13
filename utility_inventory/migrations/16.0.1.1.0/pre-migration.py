import logging

from odoo import SUPERUSER_ID, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def _resolve_meter_product(cr, product_id, model_id):
    """Resolve the canonical meter product in a deterministic order.

    Priority:
      1. utility_meter.product_id (explicit on the meter)
      2. utility_meter.model_id -> utility.meter.model.product_id

    Returns the product_product id or False when nothing can be resolved.
    """
    if product_id:
        return product_id
    if model_id:
        cr.execute(
            "SELECT product_id FROM utility_meter_model WHERE id = %s",
            [model_id])
        row = cr.fetchone()
        if row and row[0]:
            return row[0]
    return False


def _is_meter_product(cr, product_id):
    """A product is a genuine meter product when it is referenced by the
    meter catalogue (utility.meter.model) or by legacy meters carrying a
    physical serial. Prevents silently converting arbitrary stock items."""
    cr.execute("""
        SELECT 1 FROM utility_meter_model
         WHERE product_id = %s
         LIMIT 1
    """, [product_id])
    if cr.fetchone():
        return True
    cr.execute("""
        SELECT 1 FROM utility_meter
         WHERE product_id = %s
           AND serial_number IS NOT NULL
           AND btrim(serial_number) <> ''
         LIMIT 1
    """, [product_id])
    return bool(cr.fetchone())


def _stock_safe_for_serial(cr, product_id):
    """Return False when switching this product to serial tracking would
    clash with existing stock data (nonzero quants, leftover lone lots,
    or move lines that assume no serial tracking)."""
    cr.execute("""
        SELECT 1 FROM stock_quant
         WHERE product_id = %s
           AND (quantity != 0.0 OR reserved_quantity != 0.0)
         LIMIT 1
    """, [product_id])
    if cr.fetchone():
        return False
    cr.execute("""
        SELECT 1
          FROM stock_move_line
         WHERE product_id = %s
         LIMIT 1
    """, [product_id])
    if cr.fetchone():
        return False
    cr.execute("""
        SELECT 1 FROM stock_lot l
         LEFT JOIN utility_meter m ON m.lot_id = l.id
         WHERE l.product_id = %s
           AND m.id IS NULL
         LIMIT 1
    """, [product_id])
    return not cr.fetchone()


def _lot_assigned_to_another_meter(cr, lot_id, meter_id):
    """Return the other meter already linked to the same physical lot, if any."""
    cr.execute("""
        SELECT meter_number
          FROM utility_meter
         WHERE lot_id = %s AND id != %s
         LIMIT 1
    """, [lot_id, meter_id])
    row = cr.fetchone()
    return row[0] if row else False


def migrate(cr, version):
    """Safely map legacy meter serials to stock lots without blocking the
    whole upgrade because a legacy meter lacks Product/Lot linkage.

    Policy per legacy meter carrying a physical serial:
      A. existing compatible lot_id -> validate and keep it.
      B. no lot_id, but a safe and unambiguous meter Product can be resolved
         -> create/find stock.lot and assign lot_id.
      C. Product cannot be resolved safely -> preserve the upgrade, do NOT
         invent an arbitrary Product, leave physical linkage unresolved for
         later remediation.

    Hard migration failures are reserved for genuine contradictions only:
      - an existing lot_id whose serial conflicts with the legacy serial
      - the same physical Lot/Serial inconsistently assigned to two meters
      - contradictory company/product relationships

    Missing product_id, missing lot_id or product.tracking != 'serial' on a
    legacy meter are NEVER treated as upgrade-blocking corruption.

    The legacy serial_number is never discarded nor silently overwritten.
    The script is idempotent and safe to rerun after rollback.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Read the legacy column directly: this hook runs while the old Core
    # field still exists and before Inventory installs its projection.
    cr.execute("""
        SELECT id, meter_number, serial_number, lot_id, product_id,
               model_id, company_id
          FROM utility_meter
         WHERE serial_number IS NOT NULL
           AND btrim(serial_number) <> ''
    """)
    meters = cr.fetchall()
    Lot = env['stock.lot']
    for meter_id, meter_number, legacy_serial, lot_id, product_id, model_id, company_id in meters:
        serial = legacy_serial.strip()

        # ── Policy A: an existing lot_id is kept and validated ────────────
        if lot_id:
            lot = Lot.browse(lot_id).exists()
            if lot and lot.name != serial:
                raise ValidationError(
                    'ترقية المخزون متوقفة: الرقم التسلسلي للعداد %s لا يطابق '
                    'Lot/Serial الفعلي %s.' % (meter_number, lot.name)
                )
            # A lot that no longer exists stays untouched; it is not a reason
            # to block the upgrade and is left for later remediation.
            _logger.info(
                'Meter %s already linked to lot %s; kept.', meter_number, lot_id)
            continue

        # ── Policy B/C: try to resolve a safe meter Product ────────────────
        resolved = _resolve_meter_product(cr, product_id, model_id)
        if not resolved:
            # Policy C: cannot resolve safely -> leave unresolved.
            _logger.warning(
                'Meter %s has legacy serial %s but no resolvable Product; '
                'physical linkage left for later remediation.', meter_number, serial)
            continue

        product = env['product.product'].browse(resolved).exists()
        if not product:
            _logger.warning(
                'Meter %s serial %s resolves to a missing Product (%s); '
                'physical linkage left for later remediation.',
                meter_number, serial, resolved)
            continue

        if product.tracking != 'serial':
            # Safe conversion is only attempted when the product is a genuine
            # meter Product AND stock data will not clash. Anything else is
            # treated as unresolved (Policy C), never as a blocking error.
            if not _is_meter_product(cr, resolved) or not _stock_safe_for_serial(cr, resolved):
                _logger.warning(
                    'Meter %s serial %s cannot be safely converted to serial '
                    'tracking (product %s); left for later remediation.',
                    meter_number, serial, product.display_name)
                continue
            cr.execute(
                "UPDATE product_template SET tracking = 'serial' WHERE id = %s",
                [product.product_tmpl_id.id])

        company = env['res.company'].browse(company_id).exists()
        lot = Lot.search([
            ('name', '=', serial),
            ('product_id', '=', product.id),
        ], limit=1)
        if lot and lot.company_id and company and lot.company_id != company:
            raise ValidationError(
                'ترقية المخزون متوقفة: شركة Lot/Serial للعداد %s مختلفة.' % meter_number)
        conflicting = _lot_assigned_to_another_meter(cr, lot.id, meter_id) if lot else False
        if conflicting:
            raise ValidationError(
                'ترقية المخزون متوقفة: الرقم التسلسلي للعداد %s مستخدم مسبقًا '
                'لعداد آخر (%s).' % (meter_number, conflicting))
        if not lot:
            lot = Lot.create({
                'name': serial,
                'product_id': product.id,
                'company_id': company.id,
            })
        cr.execute(
            'UPDATE utility_meter SET lot_id = %s, product_id = %s WHERE id = %s',
            [lot.id, product.id, meter_id])