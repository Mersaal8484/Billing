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

    def test_financial_settlement_in_statement(self):
        """التحقق من ظهور التسويات المالية (مدين ودائن) في كشف الحساب والارصدة التراكمية"""
        # إنشاء تسوية دائنة (خصم)
        settlement_credit = self.env['utility.financial.settlement'].create({
            'account_id': self.customer.id,
            'settlement_type': 'credit',
            'amount': 100.0,
            'reason': 'تسوية دائنة خصم استهلاك',
            'date': Date.from_string('2026-02-01'),
            'state': 'applied',
        })
        # إنشاء تسوية مدينة (إضافة)
        settlement_debit = self.env['utility.financial.settlement'].create({
            'account_id': self.customer.id,
            'settlement_type': 'debit',
            'amount': 50.0,
            'reason': 'تسوية مدينة تعديل تعرفة',
            'date': Date.from_string('2026-03-01'),
            'state': 'applied',
        })

        wizard = self.wizard_model.create({
            'customer_id': self.customer.id,
            'date_from': Date.from_string('2026-01-01'),
            'date_to': Date.from_string('2026-12-31'),
        })
        lines = wizard._get_statement_lines()
        settlement_lines = [l for l in lines if l['kind'] == 'settlement']
        self.assertEqual(len(settlement_lines), 2, "يجب أن تظهر تسويتان في كشف الحساب")
        
        credit_line = next(l for l in settlement_lines if l['ref'] == settlement_credit.name)
        self.assertEqual(credit_line['credit'], 100.0)
        self.assertEqual(credit_line['debit'], 0.0)

        debit_line = next(l for l in settlement_lines if l['ref'] == settlement_debit.name)
        self.assertEqual(debit_line['debit'], 50.0)
        self.assertEqual(debit_line['credit'], 0.0)
