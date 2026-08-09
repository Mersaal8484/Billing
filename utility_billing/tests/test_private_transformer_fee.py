from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPrivateTransformerFee(TransactionCase):
    """Deterministic tests for the recurring private transformer fee.

    Architecture under test:
      - General Settings (company) defines the PRODUCT used for the fee line
        (``company.private_transformer_fee_product_id``).
      - ``utility.customer.private_transformer_fee`` defines HOW MUCH that
        specific customer pays. There is no global/default fee amount.
      - The billing engine reads the fee strictly from the customer and the
        product strictly from the company, and raises a ValidationError when
        the company product is not configured.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.Customer = cls.env['utility.customer']
        cls.Partner = cls.env['res.partner']
        cls.Transformer = cls.env['utility.transformer']
        cls.Template = cls.env['utility.contract.template']
        cls.TemplateLine = cls.env['utility.contract.template.line']
        cls.Product = cls.env['product.product']

        cls.category = cls.Category.create({
            'name': 'فئة اختبار المحول الخاص',
            'code': 'PTF-FEE-CAT',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع اختبار المحول الخاص',
            'code': 'PTF-FEE-SUB',
            'category_id': cls.category.id,
        })
        cls.kwh_product = cls.Product.create({
            'name': 'كيلوواط/ساعة (اختبار)',
            'type': 'service',
        })
        cls.fee_product = cls.Product.create({
            'name': 'منتج رسوم المحول الخاص (اختبار)',
            'type': 'service',
        })
        cls.template = cls.Template.create({
            'name': 'قالب اختبار المحول الخاص',
            'code': 'PTF-FEE-TPL',
            'subscriber_category_ids': [(6, 0, [cls.category.id])],
            'subscriber_ids': [(6, 0, [cls.subscriber.id])],
            'price_per_kwh': 5.0,
            'service_charge': 0.0,
        })
        cls.TemplateLine.create({
            'template_id': cls.template.id,
            'product_id': cls.kwh_product.id,
            'name': 'استهلاك',
            'meter_line_type': 'consumption',
        })

        cls.company = cls.env.company
        cls.company.private_transformer_fee_product_id = cls.fee_product

        cls.period = cls._create_reading_period()

    @classmethod
    def _create_reading_period(cls):
        range_type = cls.env['date.range.type'].search([
            ('default_billing_period', '=', 'monthly'),
            ('fiscal_year', '=', False),
        ], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({
                'name': 'دورة شهرية (اختبار)',
                'default_billing_period': 'monthly',
                'allow_overlap': True,
            })
        return cls.env['date.range'].create({
            'name': 'فترة اختبار المحول الخاص 2026-08',
            'period_code': 'READ-PTF-2026-08',
            'cycle_key': 'PTF-2026-08',
            'period_role': 'reading',
            'type_id': range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'billing_cadence': 'monthly',
            'state': 'open',
        })

    def _create_customer(self, suffix, is_private=True, fee=0.0, with_transformer=True):
        owner = self.Partner.create({'name': 'مالك المحول الخاص %s' % suffix})
        transformer = False
        if with_transformer:
            transformer = self.Transformer.create({
                'name': 'محول خاص %s' % suffix,
                'code': 'PRV-PTF-%s' % suffix,
                'is_private': is_private,
            })
        return self.Customer.create({
            'customer_number': 'PTF-%s' % suffix,
            'partner_id': owner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': self.template.id,
            'private_transformer_fee': fee,
            'transformer_id': transformer.id if transformer else False,
        })

    def _create_order(self, customer, consumption=1000.0):
        order = self.env['sale.order'].create({
            'partner_id': customer.partner_id.id,
            'customer_id': customer.id,
            'date_range_id': self.period.id,
            'period_start': self.period.date_start,
            'period_end': self.period.date_end,
            'previous_reading': 0.0,
            'current_reading': consumption,
            'consumption': consumption,
            'contract_template_id': self.template.id,
        })
        order._calculate_amounts()
        return order

    def _fee_lines(self, order):
        return order.order_line.filtered(
            lambda line: line.meter_line_type == 'private_transformer_fee')

    def test_different_fees_same_product(self):
        """Customer A (2,000) and Customer B (5,000) use the same configured
        company product but each bill carries its own customer fee amount."""
        customer_a = self._create_customer('001', is_private=True, fee=2000.0)
        customer_b = self._create_customer('002', is_private=True, fee=5000.0)

        order_a = self._create_order(customer_a, consumption=1000.0)
        order_b = self._create_order(customer_b, consumption=1000.0)

        fee_lines_a = self._fee_lines(order_a)
        fee_lines_b = self._fee_lines(order_b)

        self.assertEqual(len(fee_lines_a), 1)
        self.assertEqual(len(fee_lines_b), 1)

        self.assertEqual(fee_lines_a.product_id, self.company.private_transformer_fee_product_id)
        self.assertEqual(fee_lines_b.product_id, self.company.private_transformer_fee_product_id)
        self.assertEqual(fee_lines_a.product_id, fee_lines_b.product_id)

        self.assertAlmostEqual(fee_lines_a.price_unit, 2000.0, places=2)
        self.assertAlmostEqual(fee_lines_a.price_subtotal, 2000.0, places=2)
        self.assertAlmostEqual(order_a.amount_private_transformer_fee, 2000.0, places=2)
        self.assertAlmostEqual(fee_lines_b.price_unit, 5000.0, places=2)
        self.assertAlmostEqual(fee_lines_b.price_subtotal, 5000.0, places=2)
        self.assertAlmostEqual(order_b.amount_private_transformer_fee, 5000.0, places=2)

        self.assertEqual(fee_lines_a.private_transformer_id, customer_a.transformer_id)
        self.assertEqual(fee_lines_b.private_transformer_id, customer_b.transformer_id)

    def test_fee_amount_not_exposed_at_company_or_settings(self):
        """The fee AMOUNT must live only on utility.customer — never on the
        company, settings, or transformer. Only the PRODUCT is global."""
        self.assertFalse(hasattr(self.env['res.company'], 'private_transformer_fee'))
        self.assertFalse(hasattr(self.env['res.config.settings'], 'private_transformer_fee'))
        self.assertFalse(hasattr(self.env['utility.transformer'], 'private_transformer_fee'))
        self.assertFalse(hasattr(self.env['utility.customer'], 'default_private_transformer_fee'))

        defaults = self.Customer.default_get(['private_transformer_fee'])
        self.assertAlmostEqual(defaults.get('private_transformer_fee', 0.0), 0.0, places=2)

    def test_customers_have_independent_fee_values(self):
        customer_a = self._create_customer('003', is_private=True, fee=2000.0)
        customer_b = self._create_customer('004', is_private=True, fee=7000.0)

        self.assertAlmostEqual(customer_a.private_transformer_fee, 2000.0, places=2)
        self.assertAlmostEqual(customer_b.private_transformer_fee, 7000.0, places=2)
        self.assertNotAlmostEqual(customer_a.private_transformer_fee,
                                  customer_b.private_transformer_fee, places=2)

    def test_zero_customer_fee_creates_no_line(self):
        customer = self._create_customer('005', is_private=True, fee=0.0)
        order = self._create_order(customer, consumption=1000.0)

        self.assertEqual(len(self._fee_lines(order)), 0)
        self.assertAlmostEqual(order.amount_private_transformer_fee, 0.0, places=2)

    def test_regular_transformer_with_stale_fee_creates_no_line(self):
        customer = self._create_customer('006', is_private=False, fee=2500.0)
        order = self._create_order(customer, consumption=1000.0)

        self.assertEqual(len(self._fee_lines(order)), 0)
        self.assertAlmostEqual(order.amount_private_transformer_fee, 0.0, places=2)

    def test_no_transformer_creates_no_line(self):
        customer = self._create_customer('007', is_private=True, fee=2500.0,
                                         with_transformer=False)
        order = self._create_order(customer, consumption=1000.0)

        self.assertEqual(len(self._fee_lines(order)), 0)
        self.assertAlmostEqual(order.amount_private_transformer_fee, 0.0, places=2)

    def test_missing_company_product_raises_validation_error(self):
        self.company.private_transformer_fee_product_id = False
        customer = self._create_customer('008', is_private=True, fee=2500.0)

        with self.assertRaises(ValidationError):
            self._create_order(customer, consumption=1000.0)

    def test_regeneration_does_not_duplicate_fee_line(self):
        customer = self._create_customer('009', is_private=True, fee=2500.0)
        order = self._create_order(customer, consumption=1000.0)

        order._calculate_amounts()
        order._calculate_amounts()

        fee_lines = self._fee_lines(order)
        self.assertEqual(len(fee_lines), 1)
        self.assertAlmostEqual(fee_lines.price_unit, 2500.0, places=2)

    def test_negative_fee_raises_validation_error(self):
        customer = self._create_customer('010', is_private=True, fee=100.0)
        with self.assertRaises(ValidationError):
            customer.private_transformer_fee = -1.0

    def test_fee_increases_total_without_changing_tariff(self):
        customer = self._create_customer('011', is_private=True, fee=2500.0)
        order = self._create_order(customer, consumption=1000.0)

        consumption_lines = order.order_line.filtered(
            lambda line: line.meter_line_type == 'consumption')
        self.assertTrue(consumption_lines)
        self.assertAlmostEqual(order.consumption, 1000.0, places=2)
        self.assertAlmostEqual(order.amount_energy, 5000.0, places=2)
        self.assertAlmostEqual(order.amount_total, 7500.0, places=2)

    def test_posted_historical_invoice_remains_unchanged(self):
        """The fee amount is snapshotted on the sale order at billing time.
        Later changes to the customer fee must not alter an existing bill."""
        customer = self._create_customer('012', is_private=True, fee=2000.0)
        order = self._create_order(customer, consumption=1000.0)

        self.assertAlmostEqual(order.amount_private_transformer_fee, 2000.0, places=2)
        self.assertAlmostEqual(self._fee_lines(order).price_unit, 2000.0, places=2)

        order.bill_state = 'paid'
        customer.private_transformer_fee = 5000.0

        self.assertAlmostEqual(order.amount_private_transformer_fee, 2000.0, places=2)
        self.assertAlmostEqual(self._fee_lines(order).price_unit, 2000.0, places=2)
