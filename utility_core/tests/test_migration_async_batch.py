from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestMigrationAsyncBatch(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.other_company = self.env['res.company'].create({'name': 'شركة اختبار الميجريشن'})

        # Setup master data for primary company
        self.region = self.env['utility.region'].create({
            'name': 'المنطقة الأولى',
            'code': 'REG-01',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.area = self.env['utility.region'].create({
            'name': 'الفرع الأول',
            'code': 'AREA-01',
            'type': 'area',
            'parent_id': self.region.id,
            'company_id': self.company.id,
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'سكني',
            'code': 'CAT-01',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك عادي',
            'code': 'SUB-01',
            'category_id': self.category.id,
        })
        self.contract_template = self.env['utility.contract.template'].create({
            'name': 'عقد توريد',
            'code': 'CNTR-01',
            'subscriber_category_ids': [(4, self.category.id)],
            'subscriber_ids': [(4, self.subscriber_type.id)],
            'region_ids': [(4, self.region.id)],
            'area_ids': [(4, self.area.id)],
        })
        self.meter_model_single = self.env['utility.meter.model'].create({
            'name': 'عداد أحادي',
            'code': 'MDL-1P',
            'phase': 'single',
        })
        self.company.legacy_single_phase_meter_model_id = self.meter_model_single

        # Setup code mappings
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'region',
            'legacy_code': 'REG01',
            'region_id': self.region.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'area',
            'legacy_code': 'AREA01',
            'area_id': self.area.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'category',
            'legacy_code': 'CAT01',
            'category_id': self.category.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'subscriber',
            'legacy_code': 'SUB01',
            'subscriber_type_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'contract',
            'legacy_code': 'CNTR01',
            'contract_template_id': self.contract_template.id,
            'company_id': self.company.id,
        })

    def test_01_upload_is_staging_only(self):
        """التحقق من أن إنشاء السجلات يقتصر على الـ Staging كمسودة فقط دون إنشاء بيانات رسمية."""
        cust = self.env['utility.migration.customer'].create({
            'name': 'عميل تجريبي',
            'customer_number': 'CUST-ASYNC-100',
            'meter_number': 'MTR-ASYNC-100',
            'phase': 'single',
            'legacy_region': 'REG01',
            'legacy_area': 'AREA01',
            'legacy_category': 'CAT01',
            'legacy_subscriber_type': 'SUB01',
            'legacy_contract': 'CNTR01',
            'company_id': self.company.id,
            'state': 'draft',
        })
        self.assertEqual(cust.state, 'draft')
        self.assertFalse(cust.region_id)
        self.assertFalse(cust.created_partner_id)
        self.assertFalse(cust.created_customer_id)
        self.assertFalse(cust.created_meter_id)

    def test_02_server_action_queueing_and_batch_creation(self):
        """التحقق من إنشاء دفعة تنفيذ عند طلب السيرفر أكشن وإضافة السجلات لقائمة الانتظار."""
        c1 = self.env['utility.migration.customer'].create({
            'name': 'عميل 1',
            'customer_number': 'CUST-Q-01',
            'meter_number': 'MTR-Q-01',
            'phase': 'single',
            'legacy_region': 'REG01',
            'legacy_area': 'AREA01',
            'legacy_category': 'CAT01',
            'legacy_subscriber_type': 'SUB01',
            'legacy_contract': 'CNTR01',
            'company_id': self.company.id,
        })
        c2 = self.env['utility.migration.customer'].create({
            'name': 'عميل 2',
            'customer_number': 'CUST-Q-02',
            'meter_number': 'MTR-Q-02',
            'phase': 'single',
            'legacy_region': 'REG01',
            'legacy_area': 'AREA01',
            'legacy_category': 'CAT01',
            'legacy_subscriber_type': 'SUB01',
            'legacy_contract': 'CNTR01',
            'company_id': self.company.id,
        })

        res = (c1 | c2).action_queue_migration()
        batch_id = res['res_id']
        batch = self.env['utility.migration.batch'].browse(batch_id)

        self.assertTrue(batch.exists())
        self.assertEqual(batch.migration_type, 'customer')
        self.assertEqual(batch.company_id, self.company)
        self.assertEqual(batch.record_count, 2)
        self.assertIn(c1.state, ('queued', 'imported'))

    def test_03_mixed_company_selection_rejected(self):
        """منع تحديد سجلات تنتمي لأكثر من شركة في دفعة واحدة."""
        c1 = self.env['utility.migration.customer'].create({
            'name': 'عميل شركة 1',
            'customer_number': 'CUST-MX-01',
            'company_id': self.company.id,
        })
        c2 = self.env['utility.migration.customer'].create({
            'name': 'عميل شركة 2',
            'customer_number': 'CUST-MX-02',
            'company_id': self.other_company.id,
        })

        with self.assertRaises(UserError):
            (c1 | c2).action_queue_migration()

    def test_04_partial_batch_execution(self):
        """اختبار المعالجة الجزئية: نجاح سجل وفشل سجل لغياب الترميز مع تغير حالة الدفعة إلى partial."""
        c1 = self.env['utility.migration.customer'].create({
            'name': 'عميل صحيح',
            'customer_number': 'CUST-OK-01',
            'meter_number': 'MTR-OK-01',
            'phase': 'single',
            'legacy_region': 'REG01',
            'legacy_area': 'AREA01',
            'legacy_category': 'CAT01',
            'legacy_subscriber_type': 'SUB01',
            'legacy_contract': 'CNTR01',
            'company_id': self.company.id,
        })
        c2 = self.env['utility.migration.customer'].create({
            'name': 'عميل ناقص ترميز',
            'customer_number': 'CUST-ERR-01',
            'meter_number': 'MTR-ERR-01',
            'phase': 'single',
            'legacy_region': 'UNKNOWN_REG',
            'company_id': self.company.id,
        })

        batch = self.env['utility.migration.batch'].create({
            'migration_type': 'customer',
            'company_id': self.company.id,
            'state': 'queued',
        })
        (c1 | c2).write({'state': 'queued', 'last_batch_id': batch.id})

        batch.action_process_batch()

        self.assertEqual(c1.state, 'imported')
        self.assertEqual(c2.state, 'error')
        self.assertTrue(c2.error_message)
        self.assertEqual(batch.state, 'partial')
        self.assertEqual(batch.success_count, 1)
        self.assertEqual(batch.error_count, 1)

    def test_05_retry_errored_record(self):
        """إعادة محاولة السجل الفاشل بعد تصحيح الترميز يرحّله بنجاح دون تكرار البيانات."""
        c2 = self.env['utility.migration.customer'].create({
            'name': 'عميل قابل للتصحيح',
            'customer_number': 'CUST-RETRY-01',
            'meter_number': 'MTR-RETRY-01',
            'phase': 'single',
            'legacy_region': 'REG01',
            'legacy_area': 'AREA01',
            'legacy_category': 'CAT01',
            'legacy_subscriber_type': 'SUB01',
            'legacy_contract': 'CNTR01',
            'company_id': self.company.id,
            'state': 'error',
            'error_message': 'Missing mapping',
        })

        res = c2.action_queue_migration()
        new_batch = self.env['utility.migration.batch'].browse(res['res_id'])

        self.assertEqual(c2.state, 'imported')
        self.assertEqual(new_batch.state, 'done')
        self.assertTrue(c2.created_customer_id)
        self.assertEqual(c2.created_customer_id.customer_number, 'CUST-RETRY-01')

        # Retry again on imported record does not duplicate
        c2.action_import_data()
        self.assertEqual(self.env['utility.customer'].search_count([('customer_number', '=', 'CUST-RETRY-01')]), 1)

    def test_06_feeder_and_transformer_async_batch(self):
        """اختبار الفيدرات والمحولات في مسار الدفعات والمعالجة الجزئية."""
        feeder_stg = self.env['utility.migration.feeder'].create({
            'name': 'خلية جديدة',
            'feeder_code': 'FDR-ASYNC-01',
            'feeder_name': 'خلية القناة الشمالية',
            'meter_number': 'MTR-FDR-01',
            'legacy_region': 'REG01',
            'legacy_area': 'AREA01',
            'company_id': self.company.id,
        })

        res_f = feeder_stg.action_queue_migration()
        batch_f = self.env['utility.migration.batch'].browse(res_f['res_id'])
        self.assertEqual(feeder_stg.state, 'imported')
        self.assertEqual(batch_f.state, 'done')
        self.assertTrue(feeder_stg.created_feeder_id)

        trans_stg = self.env['utility.migration.transformer'].create({
            'name': 'محول جديد',
            'reference': 'TRF-ASYNC-01',
            'transformer_code': 'TRF01',
            'transformer_name': 'محول حي السلام',
            'meter_number': 'MTR-TRF-01',
            'legacy_region': 'REG01',
            'legacy_area': 'AREA01',
            'company_id': self.company.id,
        })

        res_t = trans_stg.action_queue_migration()
        batch_t = self.env['utility.migration.batch'].browse(res_t['res_id'])
        self.assertEqual(trans_stg.state, 'imported')
        self.assertEqual(batch_t.state, 'done')
        self.assertTrue(trans_stg.created_transformer_id)
