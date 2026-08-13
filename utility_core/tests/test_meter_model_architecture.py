from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_core')
class TestMeterModelArchitecture(TransactionCase):

    def setUp(self):
        super().setUp()
        self.meter_type_sub = self.env['utility.meter.type'].create({
            'name': 'عداد مشترك (Subscriber Meter)',
            'code': 'SUB_MTR',
            'description': 'تصنيف تشغيلي لعدادات المشتركين الأفراد',
        })
        self.meter_type_feeder = self.env['utility.meter.type'].create({
            'name': 'عداد فيدر (Feeder Meter)',
            'code': 'FDR_MTR',
            'description': 'تصنيف تشغيلي لعدادات قياس الفيدرات',
        })

        self.meter_model = self.env['utility.meter.model'].create({
            'name': 'Landis+Gyr E650 3P 100A',
            'code': 'LGY-E650',
            'manufacturer': 'Landis+Gyr',
            'phase': 'three',
            'voltage': 400.0,
            'current_rating': 100.0,
            'power_rating': 40.0,
            'default_meter_type_id': self.meter_type_sub.id,
        })

    def test_01_meter_type_is_operational_classification(self):
        """utility.meter.type is pure operational/business classification."""
        self.assertEqual(self.meter_type_sub.code, 'SUB_MTR')
        self.assertFalse(hasattr(self.meter_type_sub, 'product_id'))

    def test_02_meter_model_is_technical_catalog(self):
        """utility.meter.model is technical catalog owned by utility_core."""
        self.assertEqual(self.meter_model.manufacturer, 'Landis+Gyr')
        self.assertEqual(self.meter_model.phase, 'three')
        self.assertEqual(self.meter_model.voltage, 400.0)
        self.assertEqual(self.meter_model.default_meter_type_id, self.meter_type_sub)

    def test_03_meter_inherits_technical_projections_readonly(self):
        """utility.meter projects technical specs from model_id as stored readonly fields."""
        meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-ARCH-001',
            'operational_number': 'OP-ARCH-001',
            'model_id': self.meter_model.id,
            'meter_type_id': self.meter_type_sub.id,
        })
        self.assertEqual(meter.manufacturer, 'Landis+Gyr')
        self.assertEqual(meter.phase, 'three')
        self.assertEqual(meter.voltage, 400.0)
        self.assertEqual(meter.current_rating, 100.0)
        self.assertEqual(meter.power_rating, 40.0)

    def test_04_meter_type_is_independent_operational_choice(self):
        """Same technical model can be assigned different operational meter types."""
        meter_feeder = self.env['utility.meter'].create({
            'meter_number': 'MTR-ARCH-FDR-002',
            'model_id': self.meter_model.id,
            'meter_type_id': self.meter_type_feeder.id,
        })
        self.assertEqual(meter_feeder.meter_type_id, self.meter_type_feeder)
        self.assertEqual(meter_feeder.phase, 'three')

    def test_05_legacy_meter_without_model_remains_operational(self):
        """Legacy meters without model_id remain 100% operational."""
        legacy_meter = self.env['utility.meter'].create({
            'meter_number': 'MTR-LEGACY-001',
            'operational_number': 'OP-LEGACY-001',
        })
        self.assertTrue(legacy_meter.id)
        self.assertFalse(legacy_meter.model_id)

    def test_06_utility_core_manifest_has_no_stock_dependency(self):
        """utility_core manifest must not list stock or product module dependencies."""
        manifest = self.env['ir.module.module'].search([('name', '=', 'utility_core')], limit=1)
        if manifest:
            dep_names = manifest.dependencies_id.mapped('name')
            self.assertNotIn('stock', dep_names)
            self.assertNotIn('product', dep_names)
