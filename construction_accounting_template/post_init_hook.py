# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    """Auto-load the Construction Company Chart of Accounts on fresh install."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    chart_template = env.ref(
        'construction_accounting_template.construction_chart_template',
        raise_if_not_found=False,
    )
    if not chart_template:
        return

    company = env.company

    # Don't use try_loading or _load — l10n_sa's chart+data may already exist
    # and _load() refuses to run if accounting entries exist.
    # Instead, create only the accounts we need for demo data by code.
    Account = env['account.account']
    IrModelData = env['ir.model.data']

    # Map of bare XML ID → (code, name, account_type, reconcile)
    needed_accounts = {
        'acc_rev_contract': ('411001', 'إيرادات عقود مقاولات', 'income', False),
        'acc_cogs_labor_wages': ('531001', 'أجور عمال يوميين', 'expense_direct_cost', False),
        'acc_accrued_salaries': ('231001', 'مخصص الرواتب والأجور', 'liability_current', True),
        'acc_cogs_material': ('511001', 'تكاليف مواد مباشرة', 'expense_direct_cost', False),
        'acc_cogs_sub_structural': ('521001', 'مقاولو باطن - أعمال هيكلية', 'expense_direct_cost', False),
        'acc_cogs_equip_rental': ('541001', 'تأجير معدات خارجي', 'expense_direct_cost', False),
        'acc_cogs_site_security': ('551001', 'حراسة وأمن الموقع', 'expense_direct_cost', False),
    }

    for bare_name, (code, name, acct_type, reconcile) in needed_accounts.items():
        account = Account.search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        if not account:
            account = Account.create({
                'name': name,
                'code': code,
                'account_type': acct_type,
                'reconcile': reconcile,
                'company_id': company.id,
            })

        # Register XML ID so ref('construction_accounting_template.X') works
        existing_xmlid = IrModelData.search([
            ('module', '=', 'construction_accounting_template'),
            ('name', '=', bare_name),
        ], limit=1)
        if existing_xmlid:
            if existing_xmlid.model == 'account.account.template':
                existing_xmlid.write({
                    'model': 'account.account',
                    'res_id': account.id,
                })
        else:
            IrModelData.create({
                'module': 'construction_accounting_template',
                'name': bare_name,
                'model': 'account.account',
                'res_id': account.id,
            })
