{
    'name': 'Yemeni Payroll Localization',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Yemeni Labor Law compliant payroll (Social Insurance, Income Tax, EOS)',
    'description': """
Yemeni Payroll Localization for Odoo 16
========================================
Fully complies with:
- Yemeni Labor Law No. 5 of 1995
- Social Security regulations (6% employee / 9% employer)
- Yemeni Income Tax (progressive wage/salary tax)

Features:
- Two working calendars: 48h (Sat-Thu) and 40h (Sun-Thu)
- Configurable tax brackets via dedicated model
- Configurable EOS provision formula per contract type
- Social Insurance with configurable min/max base caps
- Daylight OT (1.5x) and Nighttime OT (2.0x)
- Employee and Employer social insurance rules
- Progressive income tax with standard exemption
- Unpaid leave deduction
- End-of-Service provision accrual
- Full payroll accounting integration via om_hr_payroll_account
    """,
    'depends': [
        'hr_contract',
        'hr_work_entry_contract',
        'om_hr_payroll',
        'om_hr_payroll_account',
        'hr_holidays',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_leave_type_data.xml',
        'data/resource_calendar_data.xml',
        'data/work_entry_type_data.xml',
        'data/global_time_off_data.xml',
        'data/hr_salary_rule_category.xml',
        'data/hr_contribution_register_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/ye_default_tax_brackets.xml',
        'views/hr_contract_views.xml',
        'views/ye_tax_bracket_views.xml',
        'views/ye_eos_rule_views.xml',
        'views/res_config_settings_views.xml',
        'demo/hr_payroll_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
