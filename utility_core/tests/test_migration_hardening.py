import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestMigrationHardening(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.other_company = self.env['res.company'].create({'name': 'شركة الاختبار الثانوية'})

        # Setup master data for primary company
        self.region = self.env['utility.region'].create({
            'name': 'المنطقة الشمالية',
            'code': 'REG-NORTH',
            'type': 'region',
            'company_id': self.company.id,
        })
        self.area = self.env['utility.region'].create({
            'name': 'فرع المركز',
            'code': 'AREA-CENTER',
            'type': 'area',
            'parent_id': self.region.id,
            'company_id': self.company.id,
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'سكني',
            'code': 'RESIDENTIAL',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك عادي',
            'code': 'NORMAL',
            'category_id': self.category.id,
        })
        self.contract_template = self.env['utility.contract.template'].create({
            'name': 'قالب توريد الطاقة',
            'code': 'TMPL-POWER',
            'subscriber_category_ids': [(4, self.category.id)],
            'subscriber_ids': [(4, self.subscriber_type.id)],
            'region_ids': [(4, self.region.id)],
            'area_ids': [(4, self.area.id)],
        })
        self.meter_model_single = self.env['utility.meter.model'].create({
            'name': 'عداد أحادي 1P',
            'code': 'MDL-1P',
            'phase': 'single',
        })

        # Setup master data for other company
        self.region_b = self.env['utility.region'].create({
            'name': 'المنطقة الجنوبية',
            'code': 'REG-SOUTH',
            'type': 'region',
            'company_id': self.other_company.id,
        })

    def test_mapping_orm_constraints_and_normalization(self):
        """اختبار القيود والقواعد لنموذج جدول الترميز واستقلالية الشركات."""
        # 1. Whitspace normalization
        mapping = self.env['utility.migration.mapping'].create({
            'mapping_type': 'region',
            'legacy_code': '  REG_001  ',
            'region_id': self.region.id,
            'company_id': self.company.id,
        })
        self.assertEqual(mapping.legacy_code, 'REG_001')

        # 2. Duplicate code in same company is rejected
        with self.assertRaises(Exception):
            self.env['utility.migration.mapping'].create({
                'mapping_type': 'region',
                'legacy_code': 'REG_001',
                'region_id': self.region.id,
                'company_id': self.company.id,
            })

        # 3. Target company consistency: linking company B mapping to company A region must fail
        with self.assertRaises(ValidationError):
            self.env['utility.migration.mapping'].create({
                'mapping_type': 'region',
                'legacy_code': 'REG_002',
                'region_id': self.region.id,  # Company A region
                'company_id': self.other_company.id,  # Company B
            })

        # 4. Correct multi-company mapping is allowed
        other_mapping = self.env['utility.migration.mapping'].create({
            'mapping_type': 'region',
            'legacy_code': 'REG_003',
            'region_id': self.region_b.id,
            'company_id': self.other_company.id,
        })
        self.assertTrue(other_mapping.id)

        # 5. Target field constraint validation (Exactly one target matching mapping_type)
        with self.assertRaises(ValidationError):
            self.env['utility.migration.mapping'].create({
                'mapping_type': 'area',
                'legacy_code': 'AREA_ERR',
                'company_id': self.company.id,
            })

        with self.assertRaises(ValidationError):
            self.env['utility.migration.mapping'].create({
                'mapping_type': 'region',
                'legacy_code': 'MULTI_TARGET_ERR',
                'region_id': self.region.id,
                'area_id': self.area.id,  # Two targets set!
                'company_id': self.company.id,
            })

    def test_customer_migration_execution_and_idempotency(self):
        """اختبار تهيئة المشترك والعداد وقراءة الافتتاح 0 وتوفّر created_reading_id."""
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'region',
            'legacy_code': 'LEG_REG',
            'region_id': self.region.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'area',
            'legacy_code': 'LEG_AREA',
            'area_id': self.area.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'category',
            'legacy_code': 'LEG_CAT',
            'category_id': self.category.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'subscriber',
            'legacy_code': 'LEG_SUB',
            'subscriber_type_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })
        self.env['utility.migration.mapping'].create({
            'mapping_type': 'contract',
            'legacy_code': 'LEG_CON',
            'contract_template_id': self.contract_template.id,
            'company_id': self.company.id,
        })

        staging = self.env['utility.migration.customer'].create({
            'name': 'أحمد علي (ميجريشن)',
            'customer_number': 'CUST-MIG-001',
            'meter_number': 'MTR-MIG-001',
            'last_reading': 0.0,  # Zero opening reading is VALID
            'phase': 'single',
            'legacy_region': 'LEG_REG',
            'legacy_area': 'LEG_AREA',
            'legacy_category': 'LEG_CAT',
            'legacy_subscriber_type': 'LEG_SUB',
            'legacy_contract': 'LEG_CON',
            'is_active': True,
            'company_id': self.company.id,
        })

        staging.action_import_data()
        self.assertEqual(staging.state, 'imported')
        self.assertTrue(staging.created_customer_id)
        self.assertTrue(staging.created_meter_id)
        self.assertTrue(staging.created_reading_id)  # Field created_reading_id verified

        # Meter model should be set to single phase model
        self.assertEqual(staging.created_meter_id.model_id, self.meter_model_single)
        self.assertEqual(staging.created_meter_id.phase, 'single')
        self.assertEqual(staging.created_meter_id.meter_number, 'MTR-MIG-001')
        self.assertEqual(staging.created_meter_id.operational_number, 'MTR-MIG-001')

        # Opening reading value 0 is created
        self.assertEqual(staging.created_reading_id.reading_value, 0.0)
        self.assertEqual(staging.created_reading_id.reading_purpose, 'opening')
        self.assertEqual(staging.created_reading_id.reading_category, 'customer')

        # Test idempotency
        cust_id = staging.created_customer_id.id
        meter_id = staging.created_meter_id.id
        staging.state = 'draft'
        staging.action_import_data()

        self.assertEqual(staging.created_customer_id.id, cust_id)
        self.assertEqual(staging.created_meter_id.id, meter_id)

    def test_customer_migration_ambiguous_meter_model(self):
        """اختبار التنبيه عند خطأ غموض موديل العداد."""
        self.env['utility.meter.model'].create({
            'name': 'عداد أحادي ثانوي',
            'code': 'MDL-1P-2',
            'phase': 'single',
        })

        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل موديل غامض',
            'customer_number': 'CUST-AMB-001',
            'meter_number': 'MTR-AMB-001',
            'phase': 'single',
            'is_active': True,
            'category_id': self.category.id,
            'subscriber_type_id': self.subscriber_type.id,
            'contract_template_id': self.contract_template.id,
            'company_id': self.company.id,
        })

        staging.action_import_data()
        self.assertEqual(staging.state, 'error')
        self.assertIn('AMBIGUOUS_METER_MODEL', staging.error_message)

    def test_feeder_migration_execution(self):
        """اختبار تهيئة الفيدر وعداد الرصد وقراءة الافتتاح الصفرية."""
        staging_feeder = self.env['utility.migration.feeder'].create({
            'name': 'فيدر المصانع الشمالي',
            'feeder_code': 'FDR-NORTH-01',
            'meter_number': 'MTR-FDR-001',
            'current_reading': 0.0,
            'company_id': self.company.id,
        })

        staging_feeder.action_import_data()
        self.assertEqual(staging_feeder.state, 'imported')
        self.assertTrue(staging_feeder.created_feeder_id)
        self.assertTrue(staging_feeder.created_meter_id)
        self.assertEqual(staging_feeder.created_meter_id.meter_number, 'MTR-FDR-001')
        self.assertEqual(staging_feeder.created_meter_id.operational_number, 'MTR-FDR-001')
        self.assertTrue(staging_feeder.created_reading_id)

        self.assertEqual(staging_feeder.created_reading_id.meter_id, staging_feeder.created_meter_id)
        self.assertEqual(staging_feeder.created_reading_id.feeder_id, staging_feeder.created_feeder_id)
        self.assertEqual(staging_feeder.created_reading_id.reading_category, 'feeder')
        self.assertEqual(staging_feeder.created_reading_id.reading_purpose, 'opening')
        self.assertEqual(staging_feeder.created_reading_id.reading_value, 0.0)

    def test_feeder_production_area_classification_is_explicit_and_idempotent(self):
        staging = self.env['utility.migration.feeder'].create({
            'name': 'فيدر إنتاج صريح',
            'feeder_code': 'FDR-PROD-01',
            'meter_number': 'MTR-PROD-001',
            'is_production_area': True,
            'company_id': self.company.id,
        })
        staging.action_import_data()
        self.assertEqual(staging.state, 'imported')
        feeder_id = staging.created_feeder_id.id
        self.assertEqual(staging.created_feeder_id.feeder_type, 'production_area')

        staging.state = 'draft'
        staging.action_import_data()
        self.assertEqual(staging.created_feeder_id.id, feeder_id)
        self.assertEqual(self.env['utility.feeder'].search_count([('code', '=', 'FDR-PROD-01'), ('company_id', '=', self.company.id)]), 1)

    def test_transformer_migration_execution(self):
        """اختبار تهيئة المحول وتحديد الهوية المرجعية واختيار قراءة بداية الاشتراك (150.5)."""
        staging_feeder = self.env['utility.migration.feeder'].create({
            'name': 'فيدر الخلايا',
            'feeder_code': 'FDR-CELL-01',
            'meter_number': 'MTR-CELL-001',
            'company_id': self.company.id,
        })
        staging_feeder.action_import_data()

        staging_trans = self.env['utility.migration.transformer'].create({
            'name': 'محول حي السلام',
            'reference': 'TR-SALAM-01',
            'meter_number': 'MTR-TR-001',
            'cell_meter_number': 'MTR-CELL-001',
            'opening_reading': 150.5,
            'company_id': self.company.id,
        })

        staging_trans.action_import_data()
        self.assertEqual(staging_trans.state, 'imported')
        self.assertTrue(staging_trans.created_transformer_id)
        self.assertEqual(staging_trans.created_transformer_id.feeder_id, staging_feeder.created_feeder_id)
        self.assertEqual(staging_trans.created_meter_id.meter_number, 'MTR-TR-001')
        self.assertEqual(staging_trans.created_meter_id.operational_number, 'MTR-TR-001')
        self.assertEqual(staging_trans.created_reading_id.reading_category, 'transformer')
        self.assertEqual(staging_trans.created_reading_id.reading_value, 150.5)

    def test_wizard_blank_vs_zero_and_presence_semantics(self):
        """اختبار دقة معالج الاستيراد في التمييز بين الخلية الفارغة وقيمة الصفر."""
        wizard = self.env['utility.migration.import.wizard'].create({
            'import_type': 'transformer',
            'import_file': base64.b64encode(b'dummy_excel_data'),
            'file_name': 'test.xlsx'
        })
        # 1. Blank cell parsing
        self.assertFalse(wizard._has_cell_value(None))
        self.assertFalse(wizard._has_cell_value('   '))
        self.assertTrue(wizard._has_cell_value(0))
        self.assertTrue(wizard._has_cell_value('0.0'))
        self.assertTrue(wizard._has_cell_value('150.5'))

        # 2. Invalid numeric parsing raises ValidationError
        with self.assertRaises(ValidationError):
            wizard.parse_float('15O.5')

        # 3. Staging model creation without reading fields maintains has_opening_reading = False
        staging_blank = self.env['utility.migration.transformer'].create({
            'name': 'محول فارغ القراءة',
            'reference': 'TR-BLANK-01',
            'company_id': self.company.id,
        })
        self.assertFalse(staging_blank.has_current_reading)
        self.assertFalse(staging_blank.has_opening_reading)
        self.assertIsNone(staging_blank._get_staging_opening_reading_value())

        # 4. Staging model creation with opening_reading = 150.5 sets has_opening_reading = True
        staging_val = self.env['utility.migration.transformer'].create({
            'name': 'محول بقراءة افتتاحية',
            'reference': 'TR-VAL-01',
            'opening_reading': 150.5,
            'company_id': self.company.id,
        })
        self.assertTrue(staging_val.has_opening_reading)
        self.assertEqual(staging_val._get_staging_opening_reading_value(), 150.5)

    def test_upload_mapping_flexible_vs_import_data_strict(self):
        """اختبار مرونة مطابقة الرموز في الـ Upload مقابل الصرامة التامة عند الاعتماد."""
        staging = self.env['utility.migration.customer'].create({
            'name': 'عميل بترميز مفقود',
            'customer_number': 'CUST-MISSING-01',
            'meter_number': 'MTR-MISSING-01',
            'legacy_region': 'LEG_UNKNOWN_REG',
            'company_id': self.company.id,
        })

        # 1. Upload-time mapping (strict=False) records error message without raising exception
        staging.action_map_codes(strict=False)
        self.assertIn('MISSING_REGION_MAPPING', staging.error_message)

        # 2. Strict mapping raises ValidationError directly
        with self.assertRaises(ValidationError):
            staging.action_map_codes(strict=True)

        # 3. Business import (action_import_data) catches the error, sets state to 'error' and updates error_message
        staging.action_import_data()
        self.assertEqual(staging.state, 'error')
        self.assertIn('MISSING_REGION_MAPPING', staging.error_message)
