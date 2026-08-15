def migrate(cr, version):
    """Update legacy reading settlement records from state 'done' to canonical state 'processed'."""
    cr.execute("""
        UPDATE utility_reading_settlement
        SET state = 'processed'
        WHERE state = 'done';
    """)
