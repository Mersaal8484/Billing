from odoo.tests.common import TransactionCase


class TestUtilityBillingAdjustment(TransactionCase):
    """Transactional coverage for the posted-invoice correction workflow."""

    def test_partial_adjustment_creates_one_posted_credit_note(self):
        invoice = self.env['account.move'].search([
            ('utility_sale_order_id', '!=', False),
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
        ], limit=1)
        if not invoice:
            self.skipTest('لا توجد فاتورة كهرباء مرحّلة في قاعدة الاختبار.')

        adjustment = self.env['utility.billing.adjustment'].create({
            'customer_id': invoice.utility_customer_id.id,
            'billing_period_id': invoice.utility_sale_order_id.date_range_id.id,
            'sale_order_id': invoice.utility_sale_order_id.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'charge_correction',
            'reason': 'اختبار تصحيح جزئي',
            'corrected_amount': invoice.amount_total - 1.0,
        })
        original_total = invoice.amount_total

        adjustment.action_submit()
        adjustment.action_approve()
        adjustment.action_apply_correction()

        self.assertEqual(adjustment.state, 'applied')
        self.assertEqual(adjustment.credit_note_id.state, 'posted')
        self.assertEqual(adjustment.credit_note_id.reversed_entry_id, invoice)
        self.assertAlmostEqual(invoice.amount_total, original_total, places=2)
        self.assertEqual(len(invoice.reversal_move_id.filtered(lambda move: move.utility_adjustment_id == adjustment)), 1)

    def test_full_rebill_creates_traceable_replacement_chain(self):
        invoice = self.env['account.move'].search([
            ('utility_sale_order_id', '!=', False),
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
        ], limit=1)
        if not invoice:
            self.skipTest('لا توجد فاتورة كهرباء مرحّلة في قاعدة الاختبار.')

        adjustment = self.env['utility.billing.adjustment'].create({
            'customer_id': invoice.utility_customer_id.id,
            'billing_period_id': invoice.utility_sale_order_id.date_range_id.id,
            'sale_order_id': invoice.utility_sale_order_id.id,
            'invoice_id': invoice.id,
            'adjustment_type': 'consumption_correction',
            'reason': 'اختبار إعادة الفوترة الكاملة',
            'rebill': True,
            'corrected_consumption': invoice.utility_sale_order_id.consumption,
            'corrected_amount': 0.0,
        })
        adjustment.action_submit()
        adjustment.action_approve()
        adjustment.action_apply_correction()

        self.assertEqual(adjustment.state, 'applied')
        self.assertEqual(adjustment.credit_note_id.state, 'posted')
        self.assertEqual(adjustment.replacement_sale_order_id.replacement_of_id,
                         invoice.utility_sale_order_id)
        self.assertEqual(adjustment.replacement_invoice_id.state, 'posted')
        self.assertEqual(adjustment.replacement_invoice_id.utility_adjustment_id,
                         adjustment)
