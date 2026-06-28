import logging
_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """Initialize dashboard SQL view and set default config after install."""
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['construction.dashboard'].init()
    try:
        _init_default_config(env)
    except Exception as e:
        _logger.warning('Could not set default config: %s', e)


def _init_default_config(env):
    ICPSudo = env['ir.config_parameter'].sudo()
    company = env.company

    # Default Analytic Plan — create one if none exists for construction
    plan_id = int(ICPSudo.get_param('construction.default_analytic_plan_id', '0') or 0)
    if not plan_id:
        plan = env['account.analytic.plan'].search([
            '|', ('name', 'ilike', 'construction'),
                 ('name', 'ilike', 'project'),
        ], limit=1) or env['account.analytic.plan'].search([], limit=1)
        if not plan:
            plan = env['account.analytic.plan'].create({
                'name': 'Construction Projects',
                'company_id': company.id,
            })
        ICPSudo.set_param('construction.default_analytic_plan_id', str(plan.id))

    # Income Account
    income_id = int(ICPSudo.get_param('construction.income_account_id', '0') or 0)
    if not income_id:
        account = env['account.account'].search([
            ('account_type', '=', 'income'),
            ('deprecated', '=', False),
        ], limit=1)
        if account:
            ICPSudo.set_param('construction.income_account_id', str(account.id))

    # Expense Account
    expense_id = int(ICPSudo.get_param('construction.expense_account_id', '0') or 0)
    if not expense_id:
        account = env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('deprecated', '=', False),
        ], limit=1)
        if account:
            ICPSudo.set_param('construction.expense_account_id', str(account.id))

    # Tax default: 15% for KSA
    tax = ICPSudo.get_param('construction.default_tax', '0.0')
    if float(tax or '0.0') == 0.0:
        ICPSudo.set_param('construction.default_tax', '15.0')
