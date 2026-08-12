import threading
import time
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_idempotency')
class TestGatewayIdempotency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        receivable_account = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
            ('company_id', 'in', (self.env.company.id, False))
        ], limit=1)
        if not receivable_account:
            receivable_account = self.env['account.account'].create({
                'name': 'حساب مدينون للاختبار',
                'code': '110000.TEST',
                'account_type': 'asset_receivable',
                'reconcile': True,
                'company_id': self.env.company.id,
            })
        self.partner = self.env['res.partner'].create({
            'name': 'اختبار تكافؤ التكرار',
            'property_account_receivable_id': receivable_account.id,
        })
        self.category = self.env['utility.subscriber.category'].search([
            ('code', '=', 'RES_IDEMPOTENCY'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.category:
            self.category = self.env['utility.subscriber.category'].create({
                'name': 'سكني تكرار',
                'code': 'RES_IDEMPOTENCY',
            })
        self.sub_type = self.env['utility.subscriber'].search([
            ('code', '=', 'RES_GEN_IDEMP'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.sub_type:
            self.sub_type = self.env['utility.subscriber'].create({
                'name': 'سكني عام تكرار',
                'code': 'RES_GEN_IDEMP',
                'category_id': self.category.id,
            })
        self.template = self.env['utility.contract.template'].search([
            ('code', '=', 'TPL_IDEM_REAL'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.template:
            self.template = self.env['utility.contract.template'].create({
                'name': 'قالب عقد تكافؤ الإطارات',
                'code': 'TPL_IDEM_REAL',
                'subscriber_category_ids': [(6, 0, [self.category.id])],
                'subscriber_ids': [(6, 0, [self.sub_type.id])],
            })
        c_number = f'CUST-IDEM-{self._testMethodName}'
        self.customer = self.env['utility.customer'].search([
            ('customer_number', '=', c_number),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not self.customer:
            self.customer = self.env['utility.customer'].create({
                'customer_number': c_number,
                'partner_id': self.partner.id,
                'category_id': self.category.id,
                'subscriber_id': self.sub_type.id,
                'contract_template_id': self.template.id,
            })
        self.date_range_type = self.env['date.range.type'].create({
            'name': 'فترة قراءات تكرار',
            'fiscal_year': False,
        })
        self.payment_range_type = self.env['date.range.type'].create({
            'name': 'فترة سداد تكرار',
            'fiscal_year': False,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'فبراير 2026 - تكرار',
            'type_id': self.date_range_type.id,
            'date_start': '2026-02-01',
            'date_end': '2026-02-28',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد فبراير 2026 - تكرار',
            'type_id': self.payment_range_type.id,
            'date_start': '2026-02-01',
            'date_end': '2026-03-15',
            'period_role': 'payment',
            'reading_period_id': self.date_range.id,
            'state': 'open',
        })
        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', 'in', (self.env.company.id, False))
        ], limit=1)
        if not income_account:
            income_account = self.env['account.account'].create({
                'name': 'إيرادات مبيعات الكهرباء للاختبار',
                'code': '400000.TEST',
                'account_type': 'income',
                'company_id': self.env.company.id,
            })
        self.product = self.env['product.product'].create({
            'name': 'خدمة كهرباء - تكرار',
            'type': 'service',
            'property_account_income_id': income_account.id,
        })
        self.order = self.env['sale.order'].create({
            'customer_id': self.customer.id,
            'partner_id': self.partner.id,
            'date_range_id': self.date_range.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 300.0,
            })],
        })
        self.order.action_confirm()
        self.invoice = self.order._create_invoices()
        self.invoice.action_post()

        self.journal = self.env['account.journal'].create({
            'name': 'بنك المحفظة الإلكترونية',
            'code': 'GW01',
            'type': 'bank',
            'company_id': self.env.company.id,
        })
        self.provider = self.env['utility.integration.provider'].create({
            'name': 'مزود دفع إلكتروني تكرار',
            'provider_type': 'payment_gateway',
            'is_payment_capable': True,
            'payment_direction': 'inbound',
            'inbound_journal_id': self.journal.id,
            'active': True,
        })
        self.tx = self.env['utility.payment.gateway.transaction'].create({
            'provider_id': self.provider.id,
            'payment_direction': 'inbound',
            'sale_order_id': self.order.id,
            'utility_invoice_id': self.invoice.id,
            'amount': 300.0,
            'state': 'pending',
        })

    def test_duplicate_callback_idempotency(self):
        """Test that confirming a transaction twice does not duplicate account.payment records."""
        self.tx.action_confirm_payment(provider_reference='REF-GATEWAY-1001')
        self.assertEqual(self.tx.state, 'done')
        payment_id_1 = self.tx.payment_id.id
        self.assertTrue(payment_id_1)

        # Call again on done transaction
        self.tx.action_confirm_payment(provider_reference='REF-GATEWAY-1001')
        self.assertEqual(self.tx.state, 'done')
        self.assertEqual(self.tx.payment_id.id, payment_id_1)

        # Verify only 1 payment was created
        payments = self.env['account.payment'].search([('utility_sale_order_id', '=', self.order.id)])
        self.assertEqual(len(payments), 1)

    def test_concurrent_duplicate_gateway_callback(self):
        """Test that two simultaneous gateway callbacks on the same transaction are serialized by FOR UPDATE, creating exactly 1 payment."""
        self.env.flush_all()
        tx_id = self.tx.id
        registry = self.env.registry

        event_start = threading.Event()
        worker_results = []

        def worker(ref):
            event_start.wait(timeout=5)
            cr = registry.cursor()
            try:
                env_local = self.env(cr=cr)
                tx_local = env_local['utility.payment.gateway.transaction'].browse(tx_id)
                tx_local.action_confirm_payment(provider_reference=ref)
                cr.commit()
                worker_results.append('success')
            except Exception as e:
                cr.rollback()
                worker_results.append('serialized')
            finally:
                cr.close()

        t1 = threading.Thread(target=worker, args=('REF-SIMUL-001',))
        t2 = threading.Thread(target=worker, args=('REF-SIMUL-002',))

        t1.start()
        t2.start()

        # Trigger both threads simultaneously
        event_start.set()

        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertIn('success', worker_results)
        self.assertEqual(len(worker_results), 2)

        self.env.invalidate_all()
        self.assertEqual(self.tx.state, 'done')

        payments = self.env['account.payment'].search([('utility_sale_order_id', '=', self.order.id)])
        self.assertEqual(len(payments), 1, "Exactly one account.payment should be created despite simultaneous webhooks")
