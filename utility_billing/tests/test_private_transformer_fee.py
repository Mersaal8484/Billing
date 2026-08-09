from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPrivateTransformerFee(TransactionCase):
    """Deterministic tests for the recurring private transformer net fee."""

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
        print("DEBUG transformer created:", transformer.id if transformer else None,
              "is_private:", transformer.is_private if transformer else None)
        print("DEBUG user:", self.env.user.id, self.env.user.login,
              "sudo:", self.env.su)
        print("DEBUG has access group:", self.env.user.has_group('utility_core.group_utility_admin'))
        print("DEBUG sudo search:", self.env['utility.transformer'].sudo().search(
            [('code', '=', 'PRV-PTF-%s' % suffix)], limit=1).id)
        print("DEBUG search:", self.Transformer.search_count([('code', '=', 'PRV-PTF-%s' % suffix)]))
        print("DEBUG search no active:", self.env['utility.transformer'].with_context(active_test=False).search_count([('code', '=', 'PRV-PTF-%s' % suffix)]))
        print("DEBUG all transformers:", self.Transformer.search([], order='id desc', limit=5).ids)
        customer = self.Customer.create({
            'customer_number': 'PTF-%s' % suffix,
            'partner_id': owner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'contract_template_id': self.template.id,
            'private_transformer_fee': fee,
            'transformer_id': transformer.id if transformer else False,
        })
        print("DEBUG customer created:", customer.id,
              "transformer_id:", customer.transformer_id.id)
        return customer

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

    def test_private_transformer_with_fee_adds_exactly_one_fee_line(self):
        customer = self._create_customer('001', is_private=True, fee=2500.0)
        order = self._create_order(customer, consumption=1000.0)

        print("DEBUG2 pub create:",
              self.Transformer.sudo().create({
                  'name': 'محول عام 001', 'code': 'PUB-PTF-001',
              }).id)
        print("DEBUG2 priv create:",
              self.Transformer.sudo().create({
                  'name': 'محول خاص 002', 'code': 'PRV-PTF-002', 'is_private': True,
              }).id)
        print("DEBUG2 after:", self.Transformer.sudo().search([], order='id desc', limit=5).ids)

        print("DEBUG cust.transformer_id:", customer.transformer_id.id,
              "is_private:", customer.transformer_id.is_private,
              "fee:", customer.private_transformer_fee)
        print("DEBUG order.customer_id:", order.customer_id.id)
        print("DEBUG lines:", [(l.meter_line_type, l.price_unit) for l in order.order_line])
        print("DEBUG company product:", order.company_id.private_transformer_fee_product_id)

        fee_lines = self._fee_lines(order)
        self.assertEqual(len(fee_lines), 1)
        self.assertAlmostEqual(fee_lines.price_unit, 2500.0, places=2)
        self.assertAlmostEqual(fee_lines.price_subtotal, 2500.0, places=2)
        self.assertAlmostEqual(order.amount_private_transformer_fee, 2500.0, places=2)
        self.assertEqual(fee_lines.private_transformer_id, customer.transformer_id)

    def test_private_transformer_with_zero_fee_adds_no_fee_line(self):
        customer = self._create_customer('002', is_private=True, fee=0.0)
        order = self._create_order(customer, consumption=1000.0)

        self.assertEqual(len(self._fee_lines(order)), 0)
        self.assertAlmostEqual(order.amount_private_transformer_fee, 0.0, places=2)

    def test_regular_transformer_with_stale_fee_adds_no_fee_line(self):
        customer = self._create_customer('003', is_private=False, fee=2500.0)
        order = self._create_order(customer, consumption=1000.0)

        self.assertEqual(len(self._fee_lines(order)), 0)
        self.assertAlmostEqual(order.amount_private_transformer_fee, 0.0, places=2)

    def test_regeneration_does_not_duplicate_fee_line(self):
        customer = self._create_customer('004', is_private=True, fee=2500.0)
        order = self._create_order(customer, consumption=1000.0)

        order._calculate_amounts()
        order._calculate_amounts()

        fee_lines = self._fee_lines(order)
        self.assertEqual(len(fee_lines), 1)
        self.assertAlmostEqual(fee_lines.price_unit, 2500.0, places=2)

    def test_negative_fee_raises_validation_error(self):
        customer = self._create_customer('005', is_private=True, fee=100.0)
        with self.assertRaises(ValidationError):
            customer.private_transformer_fee = -1.0

    def test_fee_increases_total_without_changing_tariff(self):
        customer = self._create_customer('006', is_private=True, fee=2500.0)
        order = self._create_order(customer, consumption=1000.0)

        consumption_lines = order.order_line.filtered(
            lambda line: line.meter_line_type == 'consumption')
        self.assertTrue(consumption_lines)
        self.assertAlmostEqual(order.consumption, 1000.0, places=2)
        self.assertAlmostEqual(order.amount_energy, 5000.0, places=2)
        self.assertAlmostEqual(order.amount_total, 7500.0, places=2)
