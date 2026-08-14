"""
Migration script for 16.0.2.7.0:
- Audit and check legacy duplicate periodic readings
- Create PostgreSQL partial unique index for periodic reading concurrency protection
- Create PostgreSQL partial unique index for active sale order reading linkage
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
          AND state != 'error'
          AND active = TRUE
          AND account_id IS NOT NULL
          AND date_range_id IS NOT NULL
        GROUP BY account_id, date_range_id, reading_category
        HAVING COUNT(*) > 1;
    """)
    duplicates = cr.fetchall()
    if duplicates:
        for row in duplicates:
            _logger.warning(
                "Migration 16.0.2.7.0 Notice: Found %d duplicate periodic readings for account_id=%s, period_id=%s, category=%s. Reading IDs: %s",
                row[4], row[0], row[1], row[2], row[3]
            )

    # 2. Safely create partial unique index for periodic readings
    cr.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS utility_reading_unique_periodic_account_period_idx
        ON utility_reading (account_id, date_range_id, reading_category)
        WHERE reading_purpose = 'periodic'
          AND state != 'error'
          AND active = TRUE
          AND account_id IS NOT NULL
          AND date_range_id IS NOT NULL;
    """)

    # 3. Safely create partial unique index for active sale orders per reading
    cr.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS utility_sale_order_unique_active_reading_idx
        ON sale_order (reading_id)
        WHERE reading_id IS NOT NULL
          AND state != 'cancel';
    """)
