import logging

_logger = logging.getLogger(__name__)

# Composite indexes recommended by the performance gap analysis
_COMPOSITE_INDEXES = [
    # Reading queries: filter by meter + state + date for billing cycles
    (
        'utility_reading_meter_state_date_idx',
        'utility_reading',
        '(meter_id, state, reading_date)',
    ),
    # Sale order queries: filter by customer + bill_state + date for overdue detection
    (
        'sale_order_customer_billstate_date_idx',
        'sale_order',
        '(customer_id, bill_state, date_order)',
    ),
    # Penalty queries: lookup by sale_order_id for computed penalty amounts
    (
        'utility_penalty_sale_order_idx',
        'utility_penalty',
        '(sale_order_id)',
    ),
]


def post_init_hook(cr, registry):
    """Create composite database indexes after module installation."""
    for index_name, table, columns in _COMPOSITE_INDEXES:
        try:
            cr.execute(
                'CREATE INDEX IF NOT EXISTS %s ON %s %s' % (index_name, table, columns)
            )
            _logger.info('Created composite index %s on %s%s', index_name, table, columns)
        except Exception:
            _logger.warning(
                'Could not create index %s on %s — table may not exist yet.',
                index_name, table,
            )
