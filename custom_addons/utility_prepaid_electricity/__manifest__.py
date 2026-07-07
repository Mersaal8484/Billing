{
    'name': 'Utility Prepaid Electricity',
    'version': '16.0.1.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Complete Prepaid Electricity Vending Management',
    'description': """
Utility Prepaid Electricity Management
=======================================
Enterprise-grade module for managing prepaid electricity vending lifecycle
for national electricity distribution companies.

Core Features:
- Customer & Account Management (millions-scale)
- Meter Management with STS Token Integration
- Multi-Tariff Engine (Flat, Block, Seasonal, TOU)
- Prepaid Sales Vending Workflow
- Payment Processing (Cash, POS, Bank, Mobile, Online)
- STS Token Lifecycle Management
- Service Orders (Connection, Disconnection, Replacement)
- Alarm & Event Management
- Real-time Dashboards & KPIs
- Comprehensive Audit Trail
- REST API Layer
- Report Engine

Technical Architecture:
- PostgreSQL optimized with strategic indexes
- Stored computed fields for aggregation
- Batch processing via queue jobs
- Scheduled cron jobs for maintenance
- Pluggable STS vending server integration
- Multi-company, multi-currency, multi-language
    """,
    'author': 'Utility ERP Solutions',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'sale_management',
        'purchase',
        'stock',
        'maintenance',
        'contacts',
    ],
    'data': [
        'security/utility_security.xml',
        'security/ir.model.access.csv',
        'data/utility_data.xml',
        'data/utility_sequence.xml',
        'data/utility_cron.xml',
        'views/utility_region_views.xml',
        'views/utility_area_views.xml',
        'views/utility_feeder_views.xml',
        'views/utility_transformer_views.xml',
        'views/utility_meter_views.xml',
        'views/utility_tariff_views.xml',
        'views/utility_customer_views.xml',
        'views/utility_account_views.xml',
        'views/utility_sale_views.xml',
        'views/utility_token_views.xml',
        'views/utility_payment_views.xml',
        'views/utility_adjustment_views.xml',
        'views/utility_alarm_views.xml',
        'views/utility_service_order_views.xml',
        'views/utility_rtu_views.xml',
        'views/utility_audit_views.xml',
        'views/utility_dashboard_views.xml',
        'views/utility_report_views.xml',
        'views/utility_menu.xml',
        'wizards/utility_token_validate_wizard_views.xml',
        'report/utility_reports.xml',
        'report/utility_receipt_report.xml',
    ],
    'demo': [
        'data/utility_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 20,
}
