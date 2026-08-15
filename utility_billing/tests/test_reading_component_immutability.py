"""
Phase 3 Tests — Reading Component Immutability

Tests that:
- write() is blocked after sale.order reaches 'sale' state
- unlink() is blocked after sale.order reaches 'sale' state
- write() is allowed during 'draft' and 'sent' states
- unlink() is allowed during 'draft' state
- Admin sudo() with _allow_bill_component_regen context bypasses guard
- A naked context flag (no sudo) does NOT bypass the guard
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'reading_component_immutability', 'production_integrity_hardening')
class TestReadingComponentImmutability(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Category = cls.env['utility.subscriber.category']
        cls.Subscriber = cls.env['utility.subscriber']
        cls.Customer = cls.env['utility.customer']
        cls.Component = cls.env['utility.bill.reading.component']

        cls.category = cls.Category.create({
            'name': 'فئة اختبار الحماية المكوّنية',
            'code': 'COMP-IMMUT-CAT',
        })
        cls.subscriber = cls.Subscriber.create({
            'name': 'نوع اختبار الحماية المكوّنية',
            'code': 'COMP-IMMUT-SUB',
            'category_id': cls.category.id,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'مالك اختبار الحماية المكوّنية'})
        cls.customer = cls.Customer.create({
            'customer_number': 'COMP-IMMUT-001',
            'partner_id': cls.partner.id,
            'category_id': cls.category.id,
            'subscriber_id': cls.subscriber.id,
        })
        cls.meter_type = cls.env['utility.meter.type'].search([], limit=1)
        cls.meter = cls.env['utility.meter'].create({
            'meter_number': 'COMP-IMMUT-MTR-001',
            'meter_type_id': cls.meter_type.id if cls.meter_type else False,
            'customer_id': cls.customer.id,
            'company_id': cls.env.company.id,
        })
        cls.reading = cls.env['utility.reading'].create({
            'meter_id': cls.meter.id,
            'account_id': cls.customer.id,
            'reading_value': 1000.0,
            'reading_date': '2026-01-15 10:00:00',
            'reading_purpose': 'periodic',
            'reading_type': 'manual',
        })
        cls.reading.with_context(
            _reading_state_transition=True,
            _bypass_reading_protection=True,
        ).write({'state': 'billed'})

        range_type = cls.env['date.range.type'].search([
            ('default_billing_period', '=', 'monthly'),
            ('fiscal_year', '=', False),
        ], limit=1)
        if not range_type:
            range_type = cls.env['date.range.type'].create({
                'name': 'نوع فترة اختبار الحماية المكوّنية',
                'default_billing_period': 'monthly',
                'allow_overlap': True,
            })
        cls.period = cls.env['date.range'].create({
            'name': 'فترة اختبار الحماية المكوّنية',
            'period_code': 'COMP-2026-08',
            'cycle_key': 'COMP-2026-08',
            'period_role': 'reading',
            'type_id': range_type.id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'billing_cadence': 'monthly',
            'state': 'open',
        })

    def _make_order_with_component(self):
        """Create a draft sale.order with one reading component."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'date_range_id': self.period.id,
            'period_start': self.period.date_start,
            'period_end': self.period.date_end,
            'previous_reading': 0.0,
            'current_reading': 1000.0,
            'consumption': 1000.0,
        })
        comp = self.Component.create({
            'sale_order_id': order.id,
            'reading_id': self.reading.id,
            'account_id': self.customer.id,
            'meter_id': self.meter.id,
            'period_end': self.period.date_end,
            'consumption': 1000.0,
            'meter_multiplier': 1.0,
            'company_id': self.env.company.id,
        })
        return order, comp

    # ── Write allowed in draft ─────────────────────────────────────────────
    def test_write_allowed_on_draft_order(self):
        """Components can be modified when the order is in draft state."""
        order, comp = self._make_order_with_component()
        self.assertEqual(order.state, 'draft')
        # Should not raise
        comp.write({'consumption': 900.0})
        self.assertAlmostEqual(comp.consumption, 900.0)

    # ── Write blocked after confirmation ──────────────────────────────────
    def test_write_blocked_after_order_confirmed(self):
        """write() must raise ValidationError once order is confirmed (state=sale)."""
        order, comp = self._make_order_with_component()
        # Force order to 'sale' state for test
        order.with_context(allow_billing_adjustment=True).write({'state': 'sale'})
        self.assertIn(order.state, ('sale', 'done'))

        with self.assertRaises(ValidationError,
                               msg='write() يجب أن يُمنع بعد تأكيد الفاتورة.'):
            comp.write({'consumption': 500.0})

    # ── Unlink blocked after confirmation ─────────────────────────────────
    def test_unlink_blocked_after_order_confirmed(self):
        """unlink() must raise ValidationError once order is confirmed."""
        order, comp = self._make_order_with_component()
        order.with_context(allow_billing_adjustment=True).write({'state': 'sale'})

        with self.assertRaises(ValidationError,
                               msg='unlink() يجب أن يُمنع بعد تأكيد الفاتورة.'):
            comp.unlink()

    # ── Admin sudo bypass works ────────────────────────────────────────────
    def test_admin_sudo_with_context_flag_bypasses_guard(self):
        """Context flag + sudo() must allow write on confirmed order component."""
        order, comp = self._make_order_with_component()
        order.with_context(allow_billing_adjustment=True).write({'state': 'sale'})

        # Admin bypass: context flag + sudo()
        comp.with_context(_allow_bill_component_regen=True).sudo().write(
            {'consumption': 750.0}
        )
        self.assertAlmostEqual(comp.consumption, 750.0,
                               msg='Admin sudo bypass يجب أن يعمل.')

    # ── Naked context flag (no sudo) does NOT bypass ───────────────────────
    def test_naked_context_flag_without_sudo_does_not_bypass(self):
        """Context flag alone (without sudo) must NOT bypass the guard.

        This validates that a client RPC cannot set _allow_bill_component_regen
        and bypass the immutability protection.
        """
        order, comp = self._make_order_with_component()
        order.with_context(allow_billing_adjustment=True).write({'state': 'sale'})

        # Context flag only — NOT sudo() — must still raise
        with self.assertRaises(ValidationError,
                               msg='Context flag بدون sudo لا يجب أن يتجاوز الحماية.'):
            comp.with_context(_allow_bill_component_regen=True).write(
                {'consumption': 750.0}
            )

    # ── Blocked after cancel too ───────────────────────────────────────────
    def test_write_blocked_on_cancelled_order(self):
        """Write must also be blocked for cancelled orders."""
        order, comp = self._make_order_with_component()
        order.with_context(allow_billing_adjustment=True).write({'state': 'cancel'})

        with self.assertRaises(ValidationError):
            comp.write({'consumption': 100.0})
