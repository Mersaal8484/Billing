import threading
import time
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'utility_release', 'utility_concurrency')
class TestPaymentConcurrency(TransactionCase):

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
            'name': 'اختبار التزامن الخالي من التداخل',
            'property_account_receivable_id': receivable_account.id,
        })
        self.category = self.env['utility.subscriber.category'].search([
            ('code', '=', 'RES_CONC_REAL'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.category:
            self.category = self.env['utility.subscriber.category'].create({
                'name': 'سكني تزامن موثوق',
                'code': 'RES_CONC_REAL',
            })
        self.sub_type = self.env['utility.subscriber'].search([
            ('code', '=', 'RES_GEN_CONC_REAL'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.sub_type:
            self.sub_type = self.env['utility.subscriber'].create({
                'name': 'سكني عام تزامن موثوق',
                'code': 'RES_GEN_CONC_REAL',
                'category_id': self.category.id,
            })
        self.template = self.env['utility.contract.template'].search([
            ('code', '=', 'TPL_CONC_REAL'),
            ('company_id', 'in', (self.env.company.id, False)),
        ], limit=1)
        if not self.template:
            self.template = self.env['utility.contract.template'].create({
                'name': 'قالب عقد تزامن موثوق',
                'code': 'TPL_CONC_REAL',
                'subscriber_category_ids': [(6, 0, [self.category.id])],
                'subscriber_ids': [(6, 0, [self.sub_type.id])],
            })
        c_number = f'CUST-CONC-REAL-{self._testMethodName}'
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
            'name': 'فترة قراءات تزامن موثوق',
            'fiscal_year': False,
        })
        self.payment_range_type = self.env['date.range.type'].create({
            'name': 'فترة سداد تزامن موثوق',
            'fiscal_year': False,
        })
        self.date_range = self.env['date.range'].create({
            'name': 'يناير 2026 - تزامن موثوق',
            'type_id': self.date_range_type.id,
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
            'period_role': 'reading',
            'state': 'open',
        })
        self.payment_period = self.env['date.range'].create({
            'name': 'سداد يناير 2026 - تزامن موثوق',
            'type_id': self.payment_range_type.id,
            'date_start': '2026-01-01',
            'date_end': '2026-02-15',
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
            'name': 'طاقة كهربائية - تزامن موثوق',
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
                'price_unit': 500.0,
            })],
        })
        self.order.action_confirm()
        self.invoice = self.order._create_invoices()
        self.invoice.action_post()

        self.journal = self.env['account.journal'].create({
            'name': 'محفظة الدفع الإلكتروني',
            'code': 'GW02',
            'type': 'bank',
            'company_id': self.env.company.id,
        })
        self.provider = self.env['utility.integration.provider'].create({
            'name': 'مزود دفع إلكتروني',
            'provider_type': 'payment_gateway',
            'is_payment_capable': True,
            'payment_direction': 'inbound',
            'inbound_journal_id': self.journal.id,
            'active': True,
        })

    def test_concurrent_manual_vs_gateway_payment_race(self):
        """Test racing manual payment vs gateway payment against same invoice residual."""
        self.assertEqual(self.invoice.amount_residual, 500.0)

        # Create a pending gateway transaction for 300
        tx = self.env['utility.payment.gateway.transaction'].create({
            'provider_id': self.provider.id,
            'payment_direction': 'inbound',
            'sale_order_id': self.order.id,
            'utility_invoice_id': self.invoice.id,
            'amount': 300.0,
            'state': 'pending',
        })

        # Concurrent manual payment of 400 posted first (residual becomes 100)
        staff = self.env['utility.staff'].search([
            ('company_id', '=', self.company.id),
            ('user_role_id.code', '=', 'collector'),
        ], limit=1)
        if not staff:
            cash_journal = self.env['account.journal'].create({
                'name': 'يومية نقدية للمحصل للاختبار',
                'code': 'CSH01',
                'type': 'cash',
                'company_id': self.company.id,
            })
            role = self.env['utility.user.role'].create({'name': 'متحصل', 'code': 'collector'})
            staff = self.env['utility.staff'].create({
                'name': 'متحصل اختبار',
                'user_id': self.env.uid,
                'user_role_id': role.id,
                'collection_journal_id': cash_journal.id,
            })

        manual_payment = self.env['account.payment'].create({
            'partner_id': self.partner.id,
            'amount': 400.0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'journal_id': self.journal.id,
            'utility_sale_order_id': self.order.id,
            'utility_invoice_id': self.invoice.id,
            'utility_payment_method': 'bank',
            'date': self.date_range.date_start,
        })
        manual_payment.action_post()

        # Invalidate invoice cache to reflect new residual of 100
        self.invoice.invalidate_recordset()
        self.assertEqual(self.invoice.amount_residual, 100.0)

        # Now attempt to confirm gateway transaction for 300 -> MUST fail validation
        with self.assertRaises(ValidationError):
            tx.action_confirm_payment(provider_reference='REF-RACE-001')

        self.assertNotEqual(tx.state, 'done')
        self.assertEqual(self.invoice.amount_residual, 100.0)

    def test_real_two_cursor_invoice_lock_concurrency(self):
        """Test true PostgreSQL FOR UPDATE row locking across two concurrent database cursors."""
        self.env.flush_all()
        invoice_id = self.invoice.id
        provider_id = self.provider.id
        order_id = self.order.id
        registry = self.env.registry

        event_locked = threading.Event()
        event_release = threading.Event()
        thread_2_finished = threading.Event()
        thread_2_results = []

        def worker_1():
            cr1 = registry.cursor()
            try:
                cr1.execute("SELECT id FROM account_move WHERE id = %s FOR UPDATE", (invoice_id,))
                event_locked.set()
                # Hold row lock until thread 2 attempts lock, then wait for release signal
                event_release.wait(timeout=5)
                cr1.rollback()
            finally:
                cr1.close()

        def worker_2():
            # Wait until thread 1 has acquired FOR UPDATE row lock
            event_locked.wait(timeout=5)
            time.sleep(0.1)
            cr2 = registry.cursor()
            try:
                env2 = self.env(cr=cr2)
                tx2 = env2['utility.payment.gateway.transaction'].create({
                    'provider_id': provider_id,
                    'payment_direction': 'inbound',
                    'sale_order_id': order_id,
                    'utility_invoice_id': invoice_id,
                    'amount': 300.0,
                    'state': 'pending',
                })
                # This call will attempt FOR UPDATE on account.move and block until cr1 releases lock
                tx2.action_confirm_payment(provider_reference='REF-CONC-TH2')
                cr2.commit()
                thread_2_results.append('done')
            except Exception as e:
                cr2.rollback()
                thread_2_results.append(str(e))
            finally:
                cr2.close()
                thread_2_finished.set()

        t1 = threading.Thread(target=worker_1)
        t2 = threading.Thread(target=worker_2)

        t1.start()
        t2.start()

        # Confirm thread 1 acquired lock
        self.assertTrue(event_locked.wait(timeout=5))

        # Check that thread 2 is running and blocked on lock
        time.sleep(0.3)
        self.assertTrue(t2.is_alive(), "Thread 2 should be running and waiting on FOR UPDATE lock held by Thread 1")

        # Signal Thread 1 to release lock
        event_release.set()

        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertTrue(thread_2_finished.is_set())

        self.env.invalidate_all()
        self.assertEqual(self.invoice.amount_residual, 200.0)
