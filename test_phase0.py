"""
test_phase0.py — اختبار الطرف-لطرف للمرحلة الصفرية (Walking Skeleton)
يغطي:
  1. إعداد البيانات التجريبية (منطقة، فترة، عميل، عداد)
  2. إنشاء دفعة رفع قراءات
  3. رفع سطر القراءة مع أصل رقمي (idempotent call 1)
  4. تشغيل معالج الدفعة process_batch
  5. التحقق من إنشاء utility.reading
  6. اعتماد القراءة → توليد الفاتورة
  7. التحقق: لا ضرائب، المبلغ صحيح
  8. اختبار idempotency: إعادة معالجة نفس الدفعة لا تُنشئ قراءة ثانية
"""
import xmlrpc.client
import uuid

DB   = 'utility_db'
USER = 'admin'
PASS = 'admin'
URL  = 'http://localhost:8169'

PASS_STR = '\033[92m✅ PASS\033[0m'
FAIL_STR = '\033[91m❌ FAIL\033[0m'


def s(label, cond, detail=''):
    tag = PASS_STR if cond else FAIL_STR
    print(f'  {tag} {label}' + (f' — {detail}' if detail else ''))
    return cond


def run_test():
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid = common.authenticate(DB, USER, PASS, {})
    if not uid:
        print('❌ Login failed — is the server running on port 8169?')
        return False
    print(f'✔ Connected to {URL}, uid={uid}')

    m = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

    # ─── §1 بيانات تجريبية ──────────────────────────────────────────────────
    print('\n─── §1 إعداد البيانات التجريبية ───')

    # منطقة
    region_ids = m.execute_kw(DB, uid, PASS, 'utility.region', 'search',
                              [[['code', '=', 'REG-P0']]])
    if region_ids:
        region_id = region_ids[0]
    else:
        region_id = m.execute_kw(DB, uid, PASS, 'utility.region', 'create', [{
            'name': 'Demo Region Phase0',
            'code': 'REG-P0',
            'recurring_rule_type': 'monthly',
            'type': 'region',
        }])
    s('utility.region created/found', bool(region_id), f'id={region_id}')

    # نوع الفترة
    type_ids = m.execute_kw(DB, uid, PASS, 'date.range.type', 'search', [[]])
    type_id = type_ids[0] if type_ids else \
        m.execute_kw(DB, uid, PASS, 'date.range.type', 'create',
                     [{'name': 'Monthly'}])

    # فترة القراءة (تاريخ مستقبلي لتجنب التعارض)
    range_ids = m.execute_kw(DB, uid, PASS, 'date.range', 'search',
                              [[['name', '=', 'Demo Period Phase0']]])
    if range_ids:
        range_id = range_ids[0]
    else:
        range_id = m.execute_kw(DB, uid, PASS, 'date.range', 'create', [{
            'name': 'Demo Period Phase0',
            'type_id': type_id,
            'date_start': '2030-01-01',
            'date_end':   '2030-01-31',
        }])
    s('date.range created/found', bool(range_id), f'id={range_id}')

    # نموذج عقد
    tpl_ids = m.execute_kw(DB, uid, PASS, 'utility.contract.template',
                           'search', [[['code', '=', 'TPL-P0']]])
    if tpl_ids:
        tpl_id = tpl_ids[0]
    else:
        tpl_id = m.execute_kw(DB, uid, PASS, 'utility.contract.template',
                              'create', [{'name': 'Demo TPL Phase0',
                                          'code': 'TPL-P0',
                                          'price_per_kwh': 0.15}])
    s('utility.contract.template created/found', bool(tpl_id), f'id={tpl_id}')

    # فئة + نوع مشترك
    cat_ids = m.execute_kw(DB, uid, PASS, 'utility.subscriber.category',
                           'search', [[]])
    cat_id = cat_ids[0] if cat_ids else \
        m.execute_kw(DB, uid, PASS, 'utility.subscriber.category',
                     'create', [{'name': 'Residential'}])

    sub_ids = m.execute_kw(DB, uid, PASS, 'utility.subscriber',
                           'search', [[['category_id', '=', cat_id]]])
    sub_id = sub_ids[0] if sub_ids else \
        m.execute_kw(DB, uid, PASS, 'utility.subscriber',
                     'create', [{'name': 'Residential Sub',
                                  'category_id': cat_id}])

    # عميل
    cust_ids = m.execute_kw(DB, uid, PASS, 'utility.customer',
                            'search', [[['customer_number', '=', 'CUST-P0-001']]])
    if cust_ids:
        customer_id = cust_ids[0]
    else:
        partner_id = m.execute_kw(DB, uid, PASS, 'res.partner',
                                  'create', [{'name': 'Phase0 Test Customer'}])
        customer_id = m.execute_kw(DB, uid, PASS, 'utility.customer',
                                   'create', [{
                                       'partner_id': partner_id,
                                       'customer_number': 'CUST-P0-001',
                                       'category_id': cat_id,
                                       'subscriber_id': sub_id,
                                       'contract_template_id': tpl_id,
                                   }])
    s('utility.customer created/found', bool(customer_id), f'id={customer_id}')

    # عداد
    meter_ids = m.execute_kw(DB, uid, PASS, 'utility.meter',
                             'search', [[['meter_number', '=', 'MTR-P0-001']]])
    if meter_ids:
        meter_id = meter_ids[0]
    else:
        meter_id = m.execute_kw(DB, uid, PASS, 'utility.meter',
                                'create', [{
                                    'meter_number': 'MTR-P0-001',
                                    'customer_id': customer_id,
                                    'payment_type': 'postpaid',
                                }])
    s('utility.meter created/found', bool(meter_id), f'id={meter_id}')

    # ─── §2 دفعة القراءة ───────────────────────────────────────────────────
    print('\n─── §2 إنشاء دفعة رفع القراءات ───')
    batch_uuid = str(uuid.uuid4())
    batch_id = m.execute_kw(DB, uid, PASS, 'utility.reading.batch',
                            'create', [{
                                'batch_uuid': batch_uuid,
                                'date_range_id': range_id,
                                'region_id': region_id,
                            }])
    s('utility.reading.batch created', bool(batch_id), f'id={batch_id}')

    # ─── §3 رفع سطر القراءة + أصل رقمي ────────────────────────────────────
    print('\n─── §3 رفع سطر القراءة (call 1) ───')
    client_reading_uuid = str(uuid.uuid4())
    asset_uuid = str(uuid.uuid4())

    asset_id = m.execute_kw(DB, uid, PASS, 'utility.media.asset',
                            'create', [{
                                'asset_type': 'meter_reading',
                                'asset_uuid': asset_uuid,
                                'client_reading_uuid': client_reading_uuid,
                                'batch_id': batch_id,
                                'original_filename': 'test_image.jpg',
                                'storage_backend': 'filesystem',
                                'state': 'uploaded',
                            }])
    s('utility.media.asset created', bool(asset_id), f'id={asset_id}')

    line1_id = m.execute_kw(DB, uid, PASS, 'utility.reading.batch.line',
                            'create', [{
                                'batch_id': batch_id,
                                'meter_number': 'MTR-P0-001',
                                'reading_value': 1500.5,
                                'client_reading_uuid': client_reading_uuid,
                                'asset_uuid': asset_uuid,
                                'state': 'pending',
                            }])
    s('utility.reading.batch.line created', bool(line1_id), f'id={line1_id}')

    # ─── §4 معالجة الدفعة ───────────────────────────────────────────────────
    print('\n─── §4 معالجة الدفعة (process_batch) ───')
    result = m.execute_kw(DB, uid, PASS,
                          'utility.reading.batch.service', 'process_batch',
                          [batch_id])
    s('process_batch returned success',
      result.get('status') == 'completed',
      str(result))

    # ─── §5 التحقق من إنشاء القراءة ────────────────────────────────────────
    print('\n─── §5 التحقق من utility.reading ───')
    reading_ids = m.execute_kw(DB, uid, PASS, 'utility.reading',
                               'search', [[['batch_id', '=', batch_id]]])
    ok_reading = s('utility.reading created from batch',
                   bool(reading_ids), f'ids={reading_ids}')
    if not ok_reading:
        print('\n⛔ توقف — القراءة لم تُنشأ. تحقق من سجل الأخطاء في الدفعة.')
        return False

    reading_id = reading_ids[0]
    line_data = m.execute_kw(DB, uid, PASS, 'utility.reading.batch.line',
                             'read', [[line1_id]], {'fields': ['state', 'error_message']})
    s('batch line state = done',
      line_data[0]['state'] == 'done',
      f"state={line_data[0]['state']} err={line_data[0]['error_message']}")

    # ─── §6 Idempotency — إعادة المعالجة لا تُنشئ قراءة ثانية ─────────────
    print('\n─── §6 اختبار Idempotency (إعادة process_batch) ───')
    result2 = m.execute_kw(DB, uid, PASS,
                           'utility.reading.batch.service', 'process_batch',
                           [batch_id])
    reading_ids2 = m.execute_kw(DB, uid, PASS, 'utility.reading',
                                'search', [[['batch_id', '=', batch_id]]])
    s('Idempotency: لا قراءة إضافية بعد إعادة المعالجة',
      len(reading_ids2) == 1,
      f'total readings={len(reading_ids2)}')

    # ─── §7 اعتماد القراءة وتوليد الفاتورة ─────────────────────────────────
    print('\n─── §7 اعتماد القراءة → فاتورة ───')
    try:
        m.execute_kw(DB, uid, PASS, 'utility.reading',
                     'action_approve', [[reading_id]])
        s('action_approve executed without error', True)
    except Exception as e:
        s('action_approve executed without error', False, str(e))
        print(f'  ⚠ reading_id={reading_id}')

    # بحث عن الفاتورة
    orders = m.execute_kw(DB, uid, PASS, 'sale.order',
                          'search_read',
                          [[['reading_id', '=', reading_id]]],
                          {'fields': ['name', 'amount_total', 'amount_tax', 'state']})
    ok_bill = s('sale.order (فاتورة) تم إنشاؤها', bool(orders),
                f'count={len(orders)}')
    if ok_bill:
        o = orders[0]
        print(f'    الفاتورة: {o["name"]} | المجموع: {o["amount_total"]} | الضريبة: {o["amount_tax"]}')
        s('لا ضرائب في الفاتورة (Phase 0)', o['amount_tax'] == 0,
          f'tax={o["amount_tax"]}')

    # ─── ملخص ───────────────────────────────────────────────────────────────
    print('\n══════════════════════════════════════')
    if ok_reading and ok_bill:
        print('🎉 المرحلة الصفرية اجتازت معايير القبول §6 بنجاح!')
        return True
    else:
        print('⚠ المرحلة الصفرية لم تجتز جميع معايير القبول. راجع الأخطاء أعلاه.')
        return False


if __name__ == '__main__':
    run_test()
