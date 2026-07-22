from odoo.tests.common import TransactionCase
from odoo.fields import Date


class TestCustomerStatementWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'مشترك اختبار كشف الحساب',
            'open_balance': 500.0,
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة سكني اختبار',
            'code': 'RES_TEST',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'نوع عائلات اختبار',
            'category_id': self.category.id,
        })
        self.customer = self.env['utility.customer'].create({
            'customer_number': 'CUST-TEST-001',
            'partner_id': self.partner.id,
            'category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
        })
        self.wizard_model = self.env['utility.customer.statement.wizard']

    def test_opening_balance_without_date(self):
        """التحقق من أن الرصيد الافتتاحي يسترجع القيمة الأساسية للعميل عند عدم تحديد تاريخ بداية"""
        wizard = self.wizard_model.create({
            'customer_id': self.customer.id,
        })
        opening = wizard._get_opening_balance()
        self.assertEqual(opening, 500.0, "الرصيد الافتتاحي يجب أن يساوي 500.0")

    def test_statement_totals_and_running_balance(self):
        """التحقق من احتساب الرصيد التراكمي وإجمالي كشف الحساب"""
        wizard = self.wizard_model.create({
            'customer_id': self.customer.id,
            'date_from': Date.from_string('2026-01-01'),
            'date_to': Date.from_string('2026-12-31'),
        })
        totals = wizard._get_statement_totals()
        self.assertIn('opening', totals)
        self.assertIn('closing', totals)
        self.assertEqual(totals['opening'], 500.0)
