"""State migration for the period lifecycle refactor.

This migration normalizes legacy date.range.state values to the new lifecycle
before the stricter workflow code is applied.
"""

STATE_MAP = {
    'reading_open': 'open',
    'reading_closed': 'closing',
    'reviewing': 'open',
    'review_closed': 'closing',
    'billing': 'closing',
    'accounting': 'closing',
    'payment_open': 'open',
    'payment_closing': 'closing',
    'reopened': 'open',
}


def migrate(cr, version):
    if not version:
        return

    for old_state, new_state in STATE_MAP.items():
        cr.execute(
            """
            UPDATE date_range
               SET state = %s
             WHERE state = %s
            """,
            (new_state, old_state),
        )

