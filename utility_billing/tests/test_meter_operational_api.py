from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.utility_billing.controllers import utility_billing_api
from odoo.addons.utility_billing.controllers import utility_reader_api


class TestMeterOperationalBillingAPI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة اختبار API الرقم التشغيلي',
            'code': 'OPS-API-CATEGORY',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع اختبار API الرقم التشغيلي',
            'code': 'OPS-API-SUBSCRIBER',
            'category_id': cls.category.id,
        })
        cls.income = cls.env['account.account'].search([
            ('company_id', '=', cls.env.company.id),
            ('account_type', '=', 'income'),
        ], limit=1)
        cls.journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        range_type = cls.env['date.range.type'].create({
            'name': 'نوع فترة اختبار API الرقم التشغيلي',
            'default_billing_period': 'monthly',
            'allow_overlap': True,
        })
        cls.period = cls.env['date.range'].create({
            'name': 'فترة اختبار API الرقم التشغيلي',
            'period_code': 'OPS-API-2026-08',
            'cycle_key': 'OPS-API-2026-08',
            'period_role': 'reading',
            'type_id': range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'billing_cadence': 'monthly',
            'state': 'open',
        })

    def _meter_and_customer(self, suffix='001', external_qr_reference=False):
        partner = self.env['res.partner'].create({
            'name': 'عميل API بدون جوال %s' % suffix,
            'mobile': False,
        })
        meter = self.env['utility.meter'].create({
            'meter_number': 'OPS-API-METER-%s' % suffix,
            'operational_number': 'OPS-API-NUMBER-%s' % suffix,
            'payment_type': 'postpaid',
        })
        customer = self.env['utility.customer'].create({
            'customer_number': 'OPS-API-CUSTOMER-%s' % suffix,
            'external_qr_reference': external_qr_reference,
            'partner_id': partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber.id,
            'meter_id': meter.id,
        })
        meter.write({
            'customer_id': customer.id,
            'connection_type': 'subscriber',
        })
        return meter, customer

    def _request(self, params):
        return SimpleNamespace(env=self.env, jsonrequest=params)

    def test_billing_invoice_works_without_mobile(self):
        if not self.income or not self.journal:
            self.skipTest('Accounting demo accounts are not available.')
        meter, customer = self._meter_and_customer('BILL')
        order = self.env['sale.order'].create({
            'partner_id': customer.partner_id.id,
            'customer_id': customer.id,
            'meter_id': meter.id,
            'date_range_id': self.period.id,
            'period_start': self.period.date_start,
            'period_end': self.period.date_end,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': self.journal.id,
            'partner_id': customer.partner_id.id,
            'utility_customer_id': customer.id,
            'utility_sale_order_id': order.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'فاتورة اختبار بدون جوال',
                'quantity': 1.0,
                'price_unit': 100.0,
                'account_id': self.income.id,
            })],
        })
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertFalse(customer.mobile)

    def test_reader_lookup_by_operational_number_returns_it(self):
        meter, _customer = self._meter_and_customer('LOOKUP')
        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'operational_number': meter.operational_number})):
            result = controller.meter_lookup()
        self.assertTrue(result['success'])
        self.assertEqual(result['meter']['id'], meter.id)
        self.assertEqual(result['meter']['operational_number'], meter.operational_number)

    def test_reader_lookup_conflicting_identifiers_is_rejected(self):
        first, _customer = self._meter_and_customer('MISMATCH-A')
        second, _customer = self._meter_and_customer('MISMATCH-B')
        controller = utility_reader_api.UtilityReaderAPI()
        with patch.object(utility_reader_api, 'request', self._request({
                'meter_id': first.id,
                'operational_number': second.operational_number})):
            result = controller.meter_lookup()
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'METER_IDENTIFIER_MISMATCH')

    def test_customer_lookup_by_external_qr_reference(self):
        _meter, customer = self._meter_and_customer('CUSTOMER-LOOKUP', 'QR-CUSTOMER-LOOKUP')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'external_qr_reference': 'QR-CUSTOMER-LOOKUP'})):
            result = controller.customer_lookup()
        self.assertTrue(result['success'])
        self.assertEqual(result['customer']['customer_id'], customer.id)
        self.assertEqual(result['customer']['external_qr_reference'], 'QR-CUSTOMER-LOOKUP')

    def test_customer_lookup_matching_identifiers_succeeds(self):
        _meter, customer = self._meter_and_customer('CUSTOMER-MATCH', 'QR-CUSTOMER-MATCH')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'customer_number': customer.customer_number,
                'external_qr_reference': customer.external_qr_reference})):
            result = controller.customer_lookup()
        self.assertTrue(result['success'])

    def test_customer_lookup_conflicting_identifiers_is_rejected(self):
        _meter, first = self._meter_and_customer('CUSTOMER-MISMATCH-A', 'QR-CUSTOMER-A')
        _meter, _second = self._meter_and_customer('CUSTOMER-MISMATCH-B', 'QR-CUSTOMER-B')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'customer_number': first.customer_number,
                'external_qr_reference': 'QR-CUSTOMER-B'})):
            result = controller.customer_lookup()
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'CUSTOMER_IDENTIFIER_MISMATCH')

    def test_customer_qr_update_is_idempotent_and_editable(self):
        _meter, customer = self._meter_and_customer('CUSTOMER-UPDATE', 'QR-UPDATE-OLD')
        controller = utility_billing_api.UtilityBillingAPI()
        for reference in ('QR-UPDATE-OLD', 'QR-UPDATE-NEW'):
            with patch.object(utility_billing_api, 'request', self._request({
                    'customer_number': customer.customer_number,
                    'new_external_qr_reference': reference})):
                result = controller.update_customer_qr_reference()
            self.assertTrue(result['success'])
            self.assertEqual(result['customer']['external_qr_reference'], reference)

    def test_customer_qr_update_rejects_another_customers_qr(self):
        _meter, first = self._meter_and_customer('CUSTOMER-OWNER-A', 'QR-OWNER-A')
        _meter, second = self._meter_and_customer('CUSTOMER-OWNER-B', 'QR-OWNER-B')
        controller = utility_billing_api.UtilityBillingAPI()
        with patch.object(utility_billing_api, 'request', self._request({
                'customer_number': second.customer_number,
                'new_external_qr_reference': first.external_qr_reference})):
            result = controller.update_customer_qr_reference()
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'QR_REFERENCE_ALREADY_ASSIGNED')
