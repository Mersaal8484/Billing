"""Remove the obsolete shared-owner columns after preserving account partners."""


def migrate(cr, version):
    """Archive obsolete owner metadata, then remove it from the live schema."""
    cr.execute("""
        SELECT COUNT(*)
          FROM utility_customer
         WHERE partner_id IS NULL
    """)
    if cr.fetchone()[0]:
        raise RuntimeError(
            'Cannot remove owner_partner_id while a utility account has no partner_id.'
        )

    cr.execute("""
        CREATE TABLE IF NOT EXISTS utility_customer_owner_legacy (
            customer_id INTEGER PRIMARY KEY,
            owner_partner_id INTEGER,
            captured_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cr.execute("""
        INSERT INTO utility_customer_owner_legacy (customer_id, owner_partner_id)
        SELECT id, owner_partner_id
          FROM utility_customer
         WHERE owner_partner_id IS NOT NULL
        ON CONFLICT (customer_id) DO NOTHING
    """)
    cr.execute("""
        CREATE TABLE IF NOT EXISTS res_partner_utility_owner_legacy (
            partner_id INTEGER PRIMARY KEY,
            utility_owner_reference VARCHAR,
            captured_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cr.execute("""
        INSERT INTO res_partner_utility_owner_legacy (partner_id, utility_owner_reference)
        SELECT id, utility_owner_reference
          FROM res_partner
         WHERE utility_owner_reference IS NOT NULL
        ON CONFLICT (partner_id) DO NOTHING
    """)

    cr.execute('ALTER TABLE utility_customer DROP COLUMN IF EXISTS owner_partner_id')
    cr.execute('ALTER TABLE res_partner DROP COLUMN IF EXISTS utility_owner_reference')
    cr.execute(
        "DELETE FROM ir_model_fields "
        "WHERE (model = %s AND name = %s) "
        "   OR (model = %s AND name = %s)",
        ['utility.customer', 'owner_partner_id',
         'res.partner', 'utility_owner_reference'],
    )
