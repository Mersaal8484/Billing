{
    'name': 'Property Management',
    'version': '16.0.1.0.0',
    'category': 'Real Estate',
    'summary': 'Complete Property & Real Estate Management',
    'description': """
Property Management Module
==========================
Enterprise-grade module for managing the complete lifecycle of properties.

Features:
- Property, Building, Floor, Unit registration
- Owner and Tenant management
- Lease contracts with renewal workflow
- Automated payment schedules and rent collection
- Security deposits management
- Maintenance requests and work orders
- Move-in/Move-out inspections
- Utility meters and consumption tracking
- Service charges management
- Document management per property/unit
- Dashboard with KPIs (occupancy, rent collection, vacancy)
- Owner statements and profitability analysis
- Full audit trail, chatter, and activities
""",
    'author': 'Property Management Solutions',
    'website': 'https://www.propert-mgmt.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'sale_management',
        'purchase',
        'stock',
        'portal',
    ],
    'data': [
        'security/property_security.xml',
        'security/ir.model.access.csv',
        'data/property_data.xml',
        'data/property_cron.xml',
        'data/sequence.xml',
        'views/property_property_views.xml',
        'views/property_building_views.xml',
        'views/property_floor_views.xml',
        'views/property_unit_views.xml',
        'views/property_owner_views.xml',
        'views/property_tenant_views.xml',
        'views/property_lease_views.xml',
        'views/property_payment_views.xml',
        'views/property_deposit_views.xml',
        'views/property_maintenance_views.xml',
        'views/property_inspection_views.xml',
        'views/property_utility_views.xml',
        'views/property_document_views.xml',
        'views/property_dashboard_views.xml',
        'views/property_settings_views.xml',
        'report/property_reports.xml',
        'report/property_lease_report.xml',
        'wizard/property_wizard_views.xml',
        'wizard/property_owner_settlement_views.xml',
        'wizard/property_split_billing_views.xml',
        'wizard/property_owner_tenant_wizard_views.xml',
        'views/property_menu.xml',
        'views/property_portal_templates.xml',
        'data/demo_data.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 15,
}
