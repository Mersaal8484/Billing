"""Normalize the legacy contract-template half-monthly selection value."""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Convert persisted ``bi_monthly`` template values without touching invoices."""
    if not version:
        return

    cr.execute("""
        UPDATE utility_contract_template
           SET recurring_rule_type = 'semi_monthly'
         WHERE recurring_rule_type = 'bi_monthly'
    """)
    if cr.rowcount:
        _logger.info(
            'Normalized %s utility contract template(s) from bi_monthly to semi_monthly.',
            cr.rowcount,
        )
