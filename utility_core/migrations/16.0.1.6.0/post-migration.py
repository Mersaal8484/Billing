import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    if not version:
        return

    _logger.info("Starting post-migration for transformer_snapshot_id on utility.reading (Layer 1)")
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    readings = env['utility.reading'].with_context(active_test=False).search([
        ('transformer_snapshot_id', '=', False)
    ])
    total = len(readings)
    _logger.info(f"Found {total} records to migrate.")
    
    success_count = 0
    fail_count = 0
    
    for r in readings:
        try:
            # Note: This assigns the *current* transformer_id which may not be 100% historically accurate
            # if the meter was already moved before this fix was applied. This is a known accepted limitation.
            if r.meter_id and r.meter_id.transformer_id:
                r.with_context(_bypass_reading_protection=True).transformer_snapshot_id = r.meter_id.transformer_id.id
            elif r.transformer_id:
                r.with_context(_bypass_reading_protection=True).transformer_snapshot_id = r.transformer_id.id
            success_count += 1
        except Exception as e:
            _logger.error(f"Failed to migrate reading {r.id}: {e}")
            fail_count += 1

    _logger.info(f"=== MIGRATION SUMMARY ===")
    _logger.info(f"Successfully updated: {success_count} / {total}")
    if fail_count > 0:
        _logger.warning(f"Failed to update: {fail_count} / {total}")
    _logger.info(f"=========================")
