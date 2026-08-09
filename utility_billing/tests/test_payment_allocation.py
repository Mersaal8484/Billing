from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestUtilityPaymentAllocation(TransactionCase):
    """Regression coverage for exact, idempotent utility payment allocation."""

    def _posted_utility_payment(self):
        payment = self.env['account.payment'].search([
            ('utility_sale_order_id', '!=', False),
            ('utility_invoice_id', '!=', False),
            ('move_id.state', '=', 'posted'),
            ('payment_type', '=', 'inbound'),
        ], order='id', limit=1)
        if not payment:
            self.skipTest('No posted utility payment fixture is available.')
        return payment

    def test_manual_allocation_creation_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['utility.payment.allocation'].create({})

    def test_allocation_is_idempotent_and_exact(self):
        payment = self._posted_utility_payment()
        allocation_model = self.env['utility.payment.allocation']
        first = allocation_model.allocate_payment(payment)
        second = allocation_model.allocate_payment(payment)

        self.assertEqual(first, second)
        self.assertEqual(first.payment_id, payment)
        self.assertEqual(first.invoice_id, payment.utility_invoice_id)
        self.assertEqual(first.sale_order_id, payment.utility_sale_order_id)
        self.assertEqual(first.utility_customer_id, payment.utility_customer_id)
        self.assertEqual(first.partner_id, payment.utility_customer_id.partner_id)
        self.assertEqual(first.state, 'reconciled')
        self.assertAlmostEqual(
            first.residual_before - first.allocated_amount,
            first.residual_after,
            places=2,
        )

    def test_all_allocations_keep_account_partner_isolated(self):
        allocations = self.env['utility.payment.allocation'].search([
            ('state', '=', 'reconciled'),
        ])
        for allocation in allocations:
            self.assertEqual(
                allocation.partner_id,
                allocation.utility_customer_id.partner_id,
            )
            self.assertEqual(
                allocation.invoice_id.partner_id,
                allocation.utility_customer_id.partner_id,
            )
