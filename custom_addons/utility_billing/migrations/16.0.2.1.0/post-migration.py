"""Remove obsolete postpaid shift and installment metadata during module upgrade."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    obsolete_xmlids = (
        'utility_billing.menu_utility_cashier_shifts',
        'utility_billing.menu_utility_installment_plan',
        'utility_billing.action_cashier_shift_all',
        'utility_billing.action_utility_collector_shift',
        'utility_billing.action_utility_installment_plan',
        'utility_billing.view_cashier_shift_tree',
        'utility_billing.view_cashier_shift_form',
        'utility_billing.view_cashier_shift_search',
        'utility_billing.view_utility_collector_shift_tree',
        'utility_billing.view_utility_collector_shift_form',
        'utility_billing.view_utility_collector_shift_search',
        'utility_billing.view_utility_installment_plan_tree',
        'utility_billing.view_utility_installment_plan_form',
        'utility_billing.admin_collector_shift',
        'utility_billing.collector_collector_shift',
        'utility_billing.supervisor_collector_shift',
        'utility_billing.auditor_collector_shift',
        'utility_billing.access_utility_installment_plan_admin',
        'utility_billing.access_utility_installment_plan_billing',
        'utility_billing.access_utility_installment_plan_auditor',
        'utility_billing.access_utility_installment_plan_line_admin',
        'utility_billing.access_utility_installment_plan_line_billing',
        'utility_billing.access_utility_installment_plan_line_auditor',
        'utility_billing.access_cashier_shift_admin',
        'utility_billing.access_cashier_shift_user',
    )
    for xmlid in obsolete_xmlids:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            record.unlink()

    env['ir.sequence'].search([
        ('code', 'in', (
            'utility.cashier.shift',
            'utility.collector.shift',
            'utility.installment.plan',
        )),
    ]).unlink()