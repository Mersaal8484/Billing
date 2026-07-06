import xmlrpc.client

url = 'http://localhost:8069'
db = 't1'
username = 'admin'
password = 'admin'

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
print(f'Authenticated as uid={uid}')

models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Check template 13
template = models.execute_kw(db, uid, password,
    'utility.contract.template', 'read', [13],
    {'fields': ['name', 'block_ids']})
print(f'Template: {template}')

# Check blocks
blocks = models.execute_kw(db, uid, password,
    'utility.contract.template.block', 'search_read',
    [[('id', 'in', template[0]['block_ids'])]],
    {'fields': ['sequence', 'name', 'from_kwh', 'to_kwh', 'price_per_kwh'],
     'order': 'sequence'})
print(f'Blocks:')
for b in blocks:
    print(f'  id={b["id"]}, seq={b["sequence"]}, name={b["name"]}, from={b["from_kwh"]}, to={b["to_kwh"]}, price={b["price_per_kwh"]}')

# Fix: set last block's to_kwh to 0 (unlimited)
last_block = max(blocks, key=lambda b: b['sequence'])
print(f'\nFixing last block: id={last_block["id"]}, setting to_kwh=0')

models.execute_kw(db, uid, password,
    'utility.contract.template.block', 'write',
    [last_block['id'], {'from_kwh': 0.0, 'to_kwh': 0.0}])

# Verify
blocks_after = models.execute_kw(db, uid, password,
    'utility.contract.template.block', 'search_read',
    [[('id', 'in', template[0]['block_ids'])]],
    {'fields': ['sequence', 'name', 'from_kwh', 'to_kwh', 'price_per_kwh'],
     'order': 'sequence'})
print(f'\nBlocks after fix:')
for b in blocks_after:
    print(f'  seq={b["sequence"]}, name={b["name"]}, from={b["from_kwh"]}, to={b["to_kwh"]}, price={b["price_per_kwh"]}')
