"""
Migration script: 16.0.2.3.0
نقل نموذج utility.payment.gateway.transaction من utility_portal إلى utility_billing.

يقوم هذا السكريبت بتحديث ir.model.data لنقل الـ XML IDs من
utility_portal.* إلى utility_billing.* قبل تحميل أي بيانات جديدة.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # ---------------------------------------------------------------
    # 1. نقل ir.model.data: الموارد التي كانت في utility_portal
    # ---------------------------------------------------------------
    xmlid_map = {
        # sequence
        'seq_utility_payment_gateway_transaction': 'seq_utility_payment_gateway_transaction',
        # views
        'view_utility_payment_gateway_transaction_tree': 'view_utility_payment_gateway_transaction_tree',
        'view_utility_payment_gateway_transaction_form': 'view_utility_payment_gateway_transaction_form',
        'action_utility_payment_gateway_transaction': 'action_utility_payment_gateway_transaction',
        'menu_utility_payment_gateway_transaction': 'menu_utility_payment_gateway_transaction',
        # security
        'rule_payment_gateway_transaction_company': 'rule_payment_gateway_transaction_company',
        'access_utility_payment_gateway_transaction_admin': 'access_utility_payment_gateway_transaction_admin',
        'access_utility_payment_gateway_transaction_auditor': 'access_utility_payment_gateway_transaction_auditor',
    }

    for old_name, new_name in xmlid_map.items():
        cr.execute("""
            UPDATE ir_model_data
               SET module = 'utility_billing',
                   name   = %s
             WHERE module = 'utility_portal'
               AND name   = %s
        """, (new_name, old_name))
        if cr.rowcount:
            _logger.info(
                'Migration 16.0.2.3.0: moved ir.model.data utility_portal.%s → utility_billing.%s',
                old_name, new_name,
            )

    # ---------------------------------------------------------------
    # 2. نقل ir.model: تحديث حقل module على النموذج نفسه
    # ---------------------------------------------------------------
    cr.execute("""
        UPDATE ir_model
           SET info = REPLACE(COALESCE(info, ''), 'utility_portal', 'utility_billing')
         WHERE model = 'utility.payment.gateway.transaction'
    """)

    # ---------------------------------------------------------------
    # 3. نقل ir.model.data للنموذج نفسه (model_ record)
    # ---------------------------------------------------------------
    cr.execute("""
        UPDATE ir_model_data
           SET module = 'utility_billing'
         WHERE module = 'utility_portal'
           AND name   = 'model_utility_payment_gateway_transaction'
    """)
    if cr.rowcount:
        _logger.info(
            'Migration 16.0.2.3.0: moved model ir.model.data entry to utility_billing'
        )

    # ---------------------------------------------------------------
    # 4. نقل حقول ir.model.fields المرتبطة بالنموذج
    # ---------------------------------------------------------------
    cr.execute("""
        UPDATE ir_model_data imd
           SET module = 'utility_billing'
          FROM ir_model im
         WHERE imd.module = 'utility_portal'
           AND imd.model  = 'ir.model.fields'
           AND im.model   = 'utility.payment.gateway.transaction'
           AND EXISTS (
               SELECT 1 FROM ir_model_fields imf
                WHERE imf.id     = imd.res_id
                  AND imf.model_id = im.id
           )
    """)
    if cr.rowcount:
        _logger.info(
            'Migration 16.0.2.3.0: moved %d ir.model.fields entries to utility_billing',
            cr.rowcount,
        )

    _logger.info('Migration 16.0.2.3.0: utility.payment.gateway.transaction migration completed.')
