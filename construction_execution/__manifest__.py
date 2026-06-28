{
    'name': 'Construction Execution',
    'version': '16.0.1.0.0',
    'category': 'Construction',
    'summary': 'Complete Construction Project Execution Engine',
    'description': """
Construction Execution Module
=============================
Production-ready module for managing construction project execution lifecycle.

Features:
- Bill of Quantities with unlimited hierarchy
- Rate Analysis with resource breakdown
- Material Planning, Requests, Issue/Return
- Variation Orders with approval workflow
- Progress Measurement (Daily/Weekly/Monthly)
- Interim Payment Certificates (IPC)
- Cost Control, Budgeting & Forecasting
- Earned Value Management (EVM)
- Cash Flow Forecasting
- Dashboard with KPIs (SPI, CPI, EAC, ETC, BAC, VAC)
- Full audit trail and chatter
""",
    'author': 'Construction ERP Team',
    'website': 'https://www.construction-erp.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'project',
        'purchase',
        'stock',
        'sale_management',
        'analytic',
        'crm',
        'report_xlsx',
    ],
    'data': [
        'security/construction_security.xml',
        'security/ir.model.access.csv',
        'data/construction_data.xml',
        'data/sequence.xml',
        'data/construction_config_data.xml',
        'data/construction_cron.xml',
        'views/construction_project_views.xml',
        'views/construction_boq_views.xml',
        'views/construction_resource_views.xml',
        'views/construction_material_views.xml',
        'views/construction_variation_views.xml',
        'views/construction_progress_views.xml',
        'views/construction_ipc_views.xml',
        'views/project_project_inherit_views.xml',
        'views/sale_order_inherit_views.xml',
        'views/purchase_order_inherit_views.xml',
        'views/stock_picking_inherit_views.xml',
        'views/crm_lead_inherit_views.xml',
        'views/res_config_settings_views.xml',
        'views/construction_cost_views.xml',
        'views/construction_budget_views.xml',
        'views/construction_forecast_views.xml',
        'views/construction_cashflow_views.xml',
        'views/construction_dashboard_views.xml',
        'report/construction_reports.xml',
        'report/construction_boq_report.xml',
        'report/construction_ipc_report.xml',
        'report/construction_progress_report.xml',
        'views/construction_menu.xml',
        'wizard/construction_wizard_views.xml',
    ],
    'demo': [
        'data/demo_data.xml',
        'data/scenario_full.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 10,
}
