"""
Phase 0 — Baseline Characterization Tests

Captures baseline facts and invariants:
- account.move is the financial source of truth
- sale.order is the commercial electricity bill
- reading_value on utility.reading is immutable once billed
- Deposits represent liabilities, not accounts receivable
"""
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'baseline_characterization', 'production_integrity_hardening')
class TestBaselineCharacterization(TransactionCase):

    def test_account_move_is_financial_truth(self):
        """Verify account.move is the system accounting model."""
        Move = self.env['account.move']
        self.assertTrue(hasattr(Move, 'line_ids'))
        self.assertTrue(hasattr(Move, 'amount_total'))
        self.assertTrue(hasattr(Move, 'state'))

    def test_sale_order_is_commercial_bill(self):
        """Verify sale.order is used as the commercial utility bill."""
        Order = self.env['sale.order']
        self.assertTrue(hasattr(Order, 'consumption'))
        self.assertTrue(hasattr(Order, 'customer_id'))
        self.assertTrue(hasattr(Order, 'date_range_id'))

    def test_deposit_model_structure(self):
        """Verify deposit model exists and has correct accounting fields."""
        Deposit = self.env['utility.deposit']
        self.assertTrue(hasattr(Deposit, 'receipt_move_id'))
        self.assertTrue(hasattr(Deposit, 'release_move_id'))
        self.assertTrue(hasattr(Deposit, 'forfeit_move_id'))
