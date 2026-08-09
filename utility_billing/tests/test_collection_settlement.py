from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from psycopg2.errors import UniqueViolation


class TestUtilityCollectionSettlement(TransactionCase):
    """Regression tests for the collector custody lifecycle."""

    def _posted_collection(self):
        collection = self.env['utility.collection'].search([
            ('state', '=', 'posted'),
            ('collector_id', '!=', False),
        ], order='id', limit=1)
        if not collection:
            self.skipTest('A posted field collection fixture is required.')
        return collection

    def _settlement(self, collection, declared):
        return self.env['utility.collection.settlement'].create({
            'company_id': collection.company_id.id,
            'collector_id': collection.collector_id.id,
            'currency_id': collection.company_id.currency_id.id,
            'declared_amount': declared,
            'line_ids': [(0, 0, {
                'collection_id': collection.id,
                'amount': collection.amount,
            })],
        })

    def test_draft_settlement_does_not_reduce_collection_balance(self):
        collection = self.env['utility.collection'].new({
            'amount': 100.0,
            'currency_id': self.env.company.currency_id.id,
        })
        settlement = self.env['utility.collection.settlement'].new({
            'state': 'draft',
            'declared_amount': 100.0,
            'currency_id': self.env.company.currency_id.id,
        })
        line = self.env['utility.collection.settlement.line'].new({
            'amount': 100.0,
            'actual_settled_amount': 100.0,
        })
        line.settlement_id = settlement
        collection.settlement_line_ids = line
        collection._compute_settled_amount()

        self.assertAlmostEqual(collection.settled_amount, 0.0, places=2)
        self.assertAlmostEqual(collection.remaining_amount, 100.0, places=2)

    def test_shortage_is_reflected_as_actual_settlement(self):
        declared = 50.0
        settlement = self.env['utility.collection.settlement'].new({
            'declared_amount': declared,
            'currency_id': self.env.company.currency_id.id,
        })
        line = self.env['utility.collection.settlement.line'].new({
            'amount': 100.0,
            'actual_settled_amount': declared,
        })
        line.settlement_id = settlement
        settlement.line_ids = line
        settlement._compute_amounts()

        self.assertAlmostEqual(line.actual_settled_amount, declared, places=2)
        self.assertAlmostEqual(
            settlement.shortage_amount,
            50.0,
            places=2,
        )
        self.assertAlmostEqual(settlement.surplus_amount, 0.0, places=2)

    def test_collection_cannot_be_added_to_two_settlements(self):
        collection = self._posted_collection()
        first = self._settlement(collection, collection.amount)
        first_line = first.line_ids

        with self.cr.savepoint():
            with self.assertRaises(UniqueViolation):
                self._settlement(collection, collection.amount)

        self.assertEqual(first_line.collection_id, collection)

    def test_collection_settlement_requires_same_collector(self):
        collection = self._posted_collection()
        other = self.env['utility.staff'].search([
            ('company_id', '=', collection.company_id.id),
            ('id', '!=', collection.collector_id.id),
        ], limit=1)
        if not other:
            self.skipTest('A second staff fixture is required.')
        settlement = self.env['utility.collection.settlement'].create({
            'company_id': collection.company_id.id,
            'collector_id': other.id,
            'currency_id': collection.company_id.currency_id.id,
            'declared_amount': collection.amount,
            'line_ids': [(0, 0, {
                'collection_id': collection.id,
                'amount': collection.amount,
            })],
        })
        with self.assertRaises(ValidationError):
            settlement.action_confirm()

    def test_each_field_collector_gets_a_distinct_cash_journal_and_account(self):
        role = self.env.ref('utility_core.role_collector')
        first = self.env['utility.staff'].create({
            'name': 'متحصل اختبار أول',
            'company_id': self.env.company.id,
            'user_role_id': role.id,
        })
        second = self.env['utility.staff'].create({
            'name': 'متحصل اختبار ثان',
            'company_id': self.env.company.id,
            'user_role_id': role.id,
        })

        self.assertNotEqual(first.collection_journal_id, second.collection_journal_id)
        self.assertNotEqual(first.cash_account_id, second.cash_account_id)
        with self.assertRaises(ValidationError):
            second.write({'collection_journal_id': first.collection_journal_id.id})
