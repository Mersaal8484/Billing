"""
Pre-migration script for 16.0.2.7.0:
- Runs before model initialization.
- Audits and fails early with clear diagnostic error if duplicate periodic readings or duplicate active sale orders exist.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Audit legacy duplicate periodic readings before schema updates
    cr.execute("""
        SELECT account_id, date_range_id, reading_category, array_agg(id) AS reading_ids, COUNT(*) AS cnt
        FROM utility_reading
        WHERE reading_purpose = 'periodic'
          AND active = TRUE
          AND account_id IS NOT NULL
          AND date_range_id IS NOT NULL
        GROUP BY account_id, date_range_id, reading_category
        HAVING COUNT(*) > 1;
    """)
    duplicates = cr.fetchall()
    if duplicates:
        lines = []
        for row in duplicates:
            lines.append(
                f"Account ID: {row[0]}, Date Range ID: {row[1]}, Category: {row[2]}, Count: {row[4]}, Reading IDs: {row[3]}"
            )
        duplicate_summary = "\n".join(lines)
        _logger.error(
            "Migration 16.0.2.7.0 Pre-check Aborted: Found duplicate periodic readings in database.\n%s",
            duplicate_summary
        )
        raise Exception(
            "Migration 16.0.2.7.0 Pre-check Aborted: Found duplicate periodic readings in database.\n"
            "Resolve duplicate periodic readings before upgrading the module.\n"
            f"Duplicate Details:\n{duplicate_summary}"
        )

    # 2. Audit duplicate active sale orders per reading before schema updates
    cr.execute("""
        SELECT reading_id, array_agg(id) AS order_ids, COUNT(*) AS cnt
        FROM sale_order
        WHERE reading_id IS NOT NULL
          AND state != 'cancel'
        GROUP BY reading_id
        HAVING COUNT(*) > 1;
    """)
    so_duplicates = cr.fetchall()
    if so_duplicates:
        lines = []
        for row in so_duplicates:
            lines.append(f"Reading ID: {row[0]}, Count: {row[2]}, Sale Order IDs: {row[1]}")
        duplicate_summary = "\n".join(lines)
        _logger.error(
            "Migration 16.0.2.7.0 Pre-check Aborted: Found multiple active sale orders for the same reading.\n%s",
            duplicate_summary
        )
        raise Exception(
            "Migration 16.0.2.7.0 Pre-check Aborted: Found multiple active sale orders for the same reading.\n"
            "Cancel or resolve duplicate sale orders before upgrading the module.\n"
            f"Duplicate Details:\n{duplicate_summary}"
        )
