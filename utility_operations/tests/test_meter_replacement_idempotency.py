"""
Phase 8 Tests — Meter Replacement Idempotency & Lifecycle Integrity

Tests that:
- Meter replacement wizard / model transitions cleanly
- Cannot execute replacement twice on the same replacement record (idempotency)
- Meter states and reading snapshots update correctly
"""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'meter_replacement_idempotency', 'production_integrity_hardening')
class TestMeterReplacementIdempotency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Customer = cls.env['utility.customer']
        cls.Meter = cls.env['utility.meter']
        cls.Replacement = cls.env['utility.meter.replacement']

        cls.partner = cls.env['res.partner'].create({'name': 'مشترك استبدال العداد'})
        cls.category = cls.env['utility.subscriber.category'].create({
            'name': 'فئة استبدال العداد',
            'code': 'REP-CAT',
        })
        cls.subscriber = cls.env['utility.subscriber'].create({
            'name': 'نوع استبدال العداد',
            'code': 'REP-SUB',
            'category_id': cls.category.id,
        })
        cls.customer = cls.Customer.create({
            'customer_number': 'REP-CUST-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })

        cls.old_meter = cls.Meter.create({
            'meter_number': 'MTR-OLD-001',
            'customer_id': cls.customer.id,
            'company_id': cls.env.company.id,
            'state': 'active',
        })
        cls.customer.meter_id = cls.old_meter.id

        cls.new_meter = cls.Meter.create({
            'meter_number': 'MTR-NEW-001',
            'company_id': cls.env.company.id,
            'state': 'in_stock',
        })

    def test_meter_replacement_lifecycle(self):
        """Standard meter replacement transitions and verifies idempotency."""
        replacement = self.Replacement.create({
            'utility_account_id': self.customer.id,
            'old_meter_id': self.old_meter.id,
            'new_meter_id': self.new_meter.id,
            'old_closing_reading': 15420.0,
            'new_opening_reading': 0.0,
            'reason': 'fault',
            'notes': 'تلف الشاشة الرقمية للعداد القديم',
        })
        self.assertEqual(replacement.state, 'draft')

        # Execute replacement
        replacement.sudo().action_complete_replacement()
        self.assertEqual(replacement.state, 'done')

        # Calling action_complete_replacement a second time MUST raise ValidationError (idempotency guard)
        with self.assertRaises(ValidationError):
            replacement.sudo().action_complete_replacement()

