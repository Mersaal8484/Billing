from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_inventory')
class TestMeterStockIntegrity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.category = self.env['product.category'].create({'name': 'عدادات كهربائية'})
        self.product_serial = self.env['product.product'].create({
            'name': 'عداد رقمي ذكي',
            'type': 'product',
            'tracking': 'serial',
            'categ_id': self.category.id,
        })
        self.product_none = self.env['product.product'].create({
            'name': 'كيبل توصيل غير مهدأ',
            'type': 'consu',
            'tracking': 'none',
        })
        self.lot_1 = self.env['stock.lot'].create({
            'name': 'SN-MTR-9001',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })
        self.lot_2 = self.env['stock.lot'].create({
            'name': 'SN-MTR-9002',
            'product_id': self.product_serial.id,
            'company_id': self.env.company.id,
        })

    def test_meter_product_lot_mismatch_raises(self):
        """Test that assigning a lot from product A to meter with product B raises ValidationError."""
        product_other = self.env['product.product'].create({
            'name': 'عداد ميكانيكي',
            'type': 'product',
            'tracking': 'serial',
        })
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-TEST-901',
                'product_id': product_other.id,
                'lot_id': self.lot_1.id,
            })

    def test_meter_product_not_serial_raises(self):
        """Test that assigning a product without serial tracking raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-TEST-902',
                'product_id': self.product_none.id,
            })

    def test_meter_serial_unique_active_constraint(self):
        """Test that a physical stock lot cannot be assigned to two active utility meters."""
        meter_1 = self.env['utility.meter'].create({
            'meter_number': 'MTR-TEST-903',
            'product_id': self.product_serial.id,
            'lot_id': self.lot_1.id,
        })
        self.assertTrue(meter_1.id)
        with self.assertRaises(ValidationError):
            self.env['utility.meter'].create({
                'meter_number': 'MTR-TEST-904',
                'product_id': self.product_serial.id,
                'lot_id': self.lot_1.id,
            })
