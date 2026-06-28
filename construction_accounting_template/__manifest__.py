# -*- coding: utf-8 -*-
{
    'name': 'Construction Accounting Template (KSA)',
    'version': '16.0.1.1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Professional Chart of Accounts for Construction & Contracting Companies in Saudi Arabia',
    'description': """
Construction Accounting Template for KSA
==========================================
Professional Chart of Accounts designed for Main Contractors and
Subcontractors operating in Saudi Arabia.

Key Features:
- Full KSA-compliant chart (SAR currency, ZATCA-ready VAT 15%)
- Construction-specific accounts: WIP Assets/Liabilities, Holdbacks,
  Retentions, Advances, Equipment Costs
- 5-element direct cost breakdown: Materials, Subcontractors, Labor,
  Equipment, Site Overheads
- Withholding Tax templates (5% rental, 5% contract, 20% consulting)
- Progress billing & milestone revenue recognition support
- Analytic mapping framework (Project + Cost Category)
    """,
    'author': 'Saudi Horizon Contracting Co. Ltd',
    'website': 'https://www.saudihorizon.sa',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'base_iban',
        'l10n_sa',
    ],
    'data': [
        'data/account_chart_template.xml',
        'data/account.account.template.csv',
        'data/account_chart_properties.xml',
        'data/account_tax_group.xml',
        'data/account_tax_template.xml',
        'data/account_fiscal_position.xml',
        'data/analytic_data.xml',
    ],
    'demo': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
