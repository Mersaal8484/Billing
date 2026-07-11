import xmlrpc.client

url = 'http://localhost:8069'
db = 't1'
username = 'admin'
password = 'admin'

print("Connecting to Odoo...")
common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
if not uid:
    print("Authentication failed.")
    exit(1)

print(f"Authenticated successfully. UID: {uid}")
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

def execute(*args, **kwargs):
    return models.execute_kw(db, uid, password, *args, **kwargs)

print("\n--- Testing utility.customer.wizard ---")
try:
    category_id = execute('utility.subscriber.category', 'search', [[]], {'limit': 1})
    subscriber_id = execute('utility.subscriber', 'search', [[('category_id', '=', category_id[0])]], {'limit': 1}) if category_id else []
    meter_product_id = execute('product.product', 'search', [[('name', 'ilike', 'عداد')]], {'limit': 1})
    meter_models = execute('utility.meter.model', 'search_read', [[]], {'fields': ['product_id'], 'limit': 1})
    
    if meter_models and meter_models[0].get('product_id'):
        meter_product_id = [meter_models[0]['product_id'][0]]
    else:
        print("Warning: No meter model with a product found. This might cause validation error.")

    region_id = execute('utility.region', 'search', [[('type', '=', 'region')]], {'limit': 1})
    area_id = execute('utility.region', 'search', [[('type', '=', 'area'), ('parent_id', '=', region_id[0])]] if region_id else [[('type', '=', 'area')]], {'limit': 1})
    zone_id = execute('utility.region', 'search', [[('type', '=', 'zone'), ('parent_id', '=', area_id[0])]] if area_id else [[('type', '=', 'zone')]], {'limit': 1})
    
    contract_tmpl = execute('utility.contract.template', 'search', [[]], {'limit': 1})

    import random
    rand_sn = f'SN-RPC-{random.randint(1000, 9999)}'

    wizard_vals = {
        'name': 'Test RPC Customer',
        'national_id': '01010101010',
        'mobile': '777000111',
        'phone': '777000222',
        'city': 'Sanaa',
        'street': 'Test Street',
        'category_id': category_id[0] if category_id else False,
        'subscriber_id': subscriber_id[0] if subscriber_id else False,
        'utility_region_id': region_id[0] if region_id else False,
        'utility_area_id': area_id[0] if area_id else False,
        'transformer_zone_id': zone_id[0] if zone_id else False,
        'contract_template_id': contract_tmpl[0] if contract_tmpl else False,
        'create_meter': True,
        'meter_product_id': meter_product_id[0] if meter_product_id else False,
        'serial_number': rand_sn,
        'phase': 'single',
        'payment_type': 'postpaid',
        'communication_type': 'none',
    }
    
    print(f"Creating wizard with vals: {wizard_vals}")
    wizard_id = execute('utility.customer.wizard', 'create', [wizard_vals])
    print(f"Wizard created: ID {wizard_id}")
    
    print("Calling action_create_customer...")
    execute('utility.customer.wizard', 'action_create_customer', [[wizard_id]])
    print("Customer created successfully via wizard!")
except Exception as e:
    print(f"Error occurred: {e}")
