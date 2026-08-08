import xmlrpc.client
import sys
import base64
import os
import uuid
import time

DB = 'utility_db'
USER = 'admin'
PASS = 'admin'
URL = 'http://localhost:8169'

def get_image_base64():
    # create a dummy tiny image in base64
    return b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='

def run_test():
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL))
    uid = common.authenticate(DB, USER, PASS, {})
    if not uid:
        print("Login failed")
        return
    
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL))
    
    # Check if demo region exists or create
    print("--- 1. Setting up demo data ---")
    region_ids = models.execute_kw(DB, uid, PASS, 'utility.region', 'search', [[['code', '=', 'REG-P0']]])
    if region_ids:
        region_id = region_ids[0]
    else:
        region_id = models.execute_kw(DB, uid, PASS, 'utility.region', 'create', [{
            'name': 'Demo Region Phase0',
            'code': 'REG-P0',
            'recurring_rule_type': 'monthly'
        }])
    
    range_ids = models.execute_kw(DB, uid, PASS, 'date.range', 'search', [[['period_code', '=', 'PER-P0']]])
    if range_ids:
        range_id = range_ids[0]
    else:
        from datetime import date, timedelta
        # Ensure DateRangeType exists first, utility_billing might rely on a specific type or we just need one
        type_ids = models.execute_kw(DB, uid, PASS, 'date.range.type', 'search', [[]])
        if type_ids:
            type_id = type_ids[0]
        else:
            type_id = models.execute_kw(DB, uid, PASS, 'date.range.type', 'create', [{'name': 'Monthly Type'}])
        range_id = models.execute_kw(DB, uid, PASS, 'date.range', 'create', [{
            'name': 'Demo Period Phase0',
            'period_code': 'PER-P0',
            'period_role': 'reading',
            'billing_cadence': 'monthly',
            'state': 'open',
            'region_ids': [(6, 0, [region_id])],
            'type_id': type_id,
            'date_start': '2030-01-01',
            'date_end': '2030-01-31'
        }])
    
    contract_tpl_ids = models.execute_kw(DB, uid, PASS, 'utility.contract.template', 'search', [[['code', '=', 'TPL-P0']]])
    if contract_tpl_ids:
        contract_tpl_id = contract_tpl_ids[0]
    else:
        contract_tpl_id = models.execute_kw(DB, uid, PASS, 'utility.contract.template', 'create', [{
            'name': 'Demo Contract Phase0',
            'code': 'TPL-P0',
            'price_per_kwh': 0.15
        }])
    
    customer_ids = models.execute_kw(DB, uid, PASS, 'utility.customer', 'search', [[['customer_number', '=', 'CUST-P0-001']]])
    if customer_ids:
        customer_id = customer_ids[0]
    else:
        cat_ids = models.execute_kw(DB, uid, PASS, 'utility.subscriber.category', 'search', [[]])
        if cat_ids:
            cat_id = cat_ids[0]
        else:
            cat_id = models.execute_kw(DB, uid, PASS, 'utility.subscriber.category', 'create', [{'name': 'Residential'}])
            
        sub_ids = models.execute_kw(DB, uid, PASS, 'utility.subscriber', 'search', [[['category_id', '=', cat_id]]])
        if sub_ids:
            sub_id = sub_ids[0]
        else:
            sub_id = models.execute_kw(DB, uid, PASS, 'utility.subscriber', 'create', [{'name': 'Residential Sub', 'category_id': cat_id}])

        partner_id = models.execute_kw(DB, uid, PASS, 'res.partner', 'create', [{
            'name': 'Phase0 Test Customer'
        }])
        customer_id = models.execute_kw(DB, uid, PASS, 'utility.customer', 'create', [{
            'partner_id': partner_id,
            'customer_number': 'CUST-P0-001',
            'category_id': cat_id,
            'subscriber_id': sub_id,
            'contract_template_id': contract_tpl_id
        }])
    
    meter_ids = models.execute_kw(DB, uid, PASS, 'utility.meter', 'search', [[['meter_number', '=', 'MTR-P0-001']]])
    if meter_ids:
        meter_id = meter_ids[0]
    else:
        meter_id = models.execute_kw(DB, uid, PASS, 'utility.meter', 'create', [{
            'meter_number': 'MTR-P0-001',
            'customer_id': customer_id,
            'payment_type': 'postpaid'
        }])
    
    print("Demo Data created successfully.")
    
    print("--- 2. Creating Reading Batch ---")
    batch_uuid = str(uuid.uuid4())
    batch_id = models.execute_kw(DB, uid, PASS, 'utility.reading.batch', 'create', [{
        'batch_uuid': batch_uuid,
        'date_range_id': range_id,
        'region_id': region_id,
        'state': 'uploaded'
    }])
    
    client_reading_uuid = str(uuid.uuid4())
    
    print("--- 3. Submitting Reading Line (Idempotent call 1) ---")
    
    asset_uuid = str(uuid.uuid4())
    # 1. Create Media Asset (simulate upload)
    asset_id = models.execute_kw(DB, uid, PASS, 'utility.media.asset', 'create', [{
        'asset_type': 'meter_reading',
        'asset_uuid': asset_uuid,
        'client_reading_uuid': client_reading_uuid,
        'batch_id': batch_id,
        'original_filename': 'test_image.jpg',
        'storage_backend': 'filesystem',
        'state': 'uploaded'
    }])

    # 2. Create Batch Line
    line1 = models.execute_kw(DB, uid, PASS, 'utility.reading.batch.line', 'create', [{
        'batch_id': batch_id,
        'meter_number': 'MTR-P0-001',
        'reading_value': 1500.5,
        'client_reading_uuid': client_reading_uuid,
        'asset_uuid': asset_uuid,
        'state': 'pending'
    }])
    print(f"Submitted Line 1: {line1}")
    
    if not reading_ids:
        print("FAIL: utility.reading was not created")
        return
    
    reading_id = reading_ids[0]
    print(f"Reading created: {reading_id}")
    
    print("--- 6. Approving Reading (Generating Bill) ---")
    # Mark as approved to trigger bill generation
    models.execute_kw(DB, uid, PASS, 'utility.reading', 'action_approve', [[reading_id]])
    
    # Check Sale Order
    orders = models.execute_kw(DB, uid, PASS, 'sale.order', 'search_read', 
        [[['reading_id', '=', reading_id]]], 
        {'fields': ['name', 'amount_total', 'amount_tax', 'state']}
    )
    
    if not orders:
        print("FAIL: No sale order was created")
        return
        
    order = orders[0]
    print(f"Bill created: {order['name']} - Total: {order['amount_total']} - Tax: {order['amount_tax']}")
    
    if order['amount_tax'] > 0:
        print("FAIL: Bill contains taxes! Phase 0 requires NO TAXES.")
        return
        
    print("SUCCESS! Phase 0 End-to-End Test Passed.")

if __name__ == '__main__':
    run_test()
