"""Retire service-order fee UI and normalize one-time activation charges."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    obsolete_xmlids = (
        'utility_billing.view_utility_service_order_form_inherit_billing',
        'utility_billing.view_utility_service_order_tree_inherit_billing',
    )
    for xmlid in obsolete_xmlids:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            record.unlink()

    # Existing rows were created by the former service-order workflow. Preserve
    # their audit trail and classify them without invoking the new uniqueness
    # constraint, because historical accounts may legitimately contain duplicates.
    env.flush_all()
    cr.execute(
        """
        UPDATE utility_service_charge
           SET activation_type = %s
         WHERE activation_type IS NULL
           AND account_id IS NOT NULL
        """,
        ['legacy_activation'],
    )
