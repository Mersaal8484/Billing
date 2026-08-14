"""
Migration script for 16.0.2.7.0:
- Explicitly audit and abort if legacy duplicate periodic readings exist
- Explicitly audit and abort if multiple active sale orders exist for the same reading
- Deploy PostgreSQL partial unique index for periodic reading concurrency protection
- Deploy PostgreSQL partial unique index for active sale order reading linkage
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Audit legacy duplicate periodic readings before indexing
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
            lines.append(f"Account ID: {row[0]}, Date Range ID: {row[1]}, Category: {row[2]}, Count: {row[4]}, Reading IDs: {row[3]}")
        duplicate_summary = "\n".join(lines)
        _logger.error(
            "Migration 16.0.2.7.0 Aborted: Found duplicate periodic readings in database.\n%s",
            duplicate_summary
        )
        raise Exception(
            "Migration 16.0.2.7.0 Aborted: Found duplicate periodic readings in database.\n"
            "Database unique index cannot be applied until duplicate readings are resolved.\n"
            f"Duplicate Details:\n{duplicate_summary}"
        )

    # 2. Audit duplicate active sale orders per reading before indexing
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
            "Migration 16.0.2.7.0 Aborted: Found multiple active sale orders for the same reading.\n%s",
            duplicate_summary
        )
        raise Exception(
            "Migration 16.0.2.7.0 Aborted: Found multiple active sale orders for the same reading.\n"
            "Database unique index cannot be applied until duplicate sale orders are cancelled or resolved.\n"
            f"Duplicate Details:\n{duplicate_summary}"
        )

    # 3. Safely create partial unique index for periodic readings
    cr.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS utility_reading_unique_periodic_account_period_idx
        ON utility_reading (account_id, date_range_id, reading_category)
        WHERE reading_purpose = 'periodic'
          AND active = TRUE
          AND account_id IS NOT NULL
          AND date_range_id IS NOT NULL;
    """)

    # 4. Safely create partial unique index for active sale orders per reading
    cr.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS utility_sale_order_unique_active_reading_idx
        ON sale_order (reading_id)
        WHERE reading_id IS NOT NULL
          AND state != 'cancel';
    """)
