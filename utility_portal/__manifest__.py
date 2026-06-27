{
    'name': 'Utility Portal',
    'version': '16.0.1.0.0',
    'category': 'Industries/Utilities',
    'summary': 'Customer Self-Service Portal & REST API',
    'description': """
Enterprise Utility Customer Portal
====================================
Complete customer self-service portal with REST API.
Allows customers to view accounts, purchase electricity,
view tokens, pay bills, raise complaints, and track service requests.

Features: Customer Login, Account Overview, Online Recharge,
Token History, Bill Payment, Service Requests, Complaints,
Notifications (Email/SMS/Push).
    """,
    'author': 'Utility ERP Platform',
    'website': 'https://www.utility-erp.com',
    'license': 'LGPL-3',
    'depends': ['utility_core', 'utility_prepaid', 'utility_billing', 'portal', 'payment'],
    'data': [
        'security/ir.model.access.csv',
        'views/utility_portal_templates.xml',
        'data/utility_portal_data.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 50,
}
