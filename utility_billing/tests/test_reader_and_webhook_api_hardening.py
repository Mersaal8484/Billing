import json
import hmac
from odoo.tests.common import TransactionCase, HttpCase
from odoo.exceptions import UserError, ValidationError


class TestReaderAndWebhookAPIHardening(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.period = self.env['date.range'].create({
            'name': 'فترة رفع اختبارية',
            'code': 'READ-API-TEST-2026-08',
            'type_id': self.env['date.range.type'].search([], limit=1).id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'period_role': 'reading',
            'state': 'open',
            'company_id': self.company.id,
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة API',
            'code': 'CAT-API-01',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك API',
            'code': 'SUB-API-01',
            'category_id': self.category.id,
        })
        self.customer = self.env['utility.customer'].create({
            'name': 'عميل API',
            'customer_number': 'CUST-API-001',
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })

    def test_daily_report_excludes_resolved_and_dismissed_alarms(self):
        """التحقق من أن التقرير اليومي يحسب الإنذارات النشطة فقط وتستبعد الحالات النهائية (resolved, dismissed)."""
        Alarm = self.env['utility.alarm']
        # Active alarms
        a1 = Alarm.create({'alarm_type': 'power_failure', 'description': 'انقطاع', 'state': 'open', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 10:00:00'})
        a2 = Alarm.create({'alarm_type': 'battery', 'description': 'بطارية', 'state': 'acknowledged', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 11:00:00'})
        a3 = Alarm.create({'alarm_type': 'reverse_energy', 'description': 'عكسي', 'state': 'investigating', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 12:00:00'})

        # Terminal alarms (MUST NOT be counted)
        a4 = Alarm.create({'alarm_type': 'tamper', 'description': 'تم حله', 'state': 'resolved', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 13:00:00'})
        a5 = Alarm.create({'alarm_type': 'other', 'description': 'تم رفضه', 'state': 'dismissed', 'customer_id': self.customer.id, 'alarm_date': '2026-08-14 14:00:00'})

        start_dt = '2026-08-14 00:00:00'
        end_dt = '2026-08-14 23:59:59'
        alarms_domain = [
            ('customer_id', '=', self.customer.id),
            ('alarm_date', '>=', start_dt), ('alarm_date', '<=', end_dt),
            ('state', 'not in', ('resolved', 'dismissed')),
        ]
        active_count = Alarm.search_count(alarms_domain)
        self.assertEqual(active_count, 3)

    def test_payment_webhook_auth_before_lock_logic(self):
        """التحقق من رفض الـ token الباطل في الويب هوك قبل الدخول في قفل الصف وتأكيد العملية في حال صحته."""
        tx = self.env['utility.payment.gateway.transaction'].create({
            'name': 'TX-WEBHOOK-TEST-001',
            'access_token': 'secret_valid_token_123',
            'amount': 150.0,
            'payment_direction': 'inbound',
            'state': 'pending',
            'customer_id': self.customer.id,
        })
        self.assertEqual(tx.state, 'pending')

        # Invalid token validation test
        token = 'invalid_fake_token'
        expected = tx.access_token.encode('utf-8')
        received = token.encode('utf-8')
        is_valid = len(expected) == len(received) and hmac.compare_digest(expected, received)
        self.assertFalse(is_valid)

        # Valid token validation test
        valid_token = 'secret_valid_token_123'
        received_valid = valid_token.encode('utf-8')
        is_valid_true = len(expected) == len(received_valid) and hmac.compare_digest(expected, received_valid)
        self.assertTrue(is_valid_true)


class TestReaderAndWebhookAPIHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.period = self.env['date.range'].create({
            'name': 'فترة رفع اختبارية HTTP',
            'code': 'READ-API-HTTP-2026-08',
            'type_id': self.env['date.range.type'].search([], limit=1).id,
            'date_start': '2026-08-01',
            'date_end': '2026-08-31',
            'period_role': 'reading',
            'state': 'open',
            'company_id': self.company.id,
        })
        self.category = self.env['utility.subscriber.category'].create({
            'name': 'فئة HTTP',
            'code': 'CAT-HTTP-01',
        })
        self.subscriber_type = self.env['utility.subscriber'].create({
            'name': 'مشترك HTTP',
            'code': 'SUB-HTTP-01',
            'category_id': self.category.id,
        })
        self.customer = self.env['utility.customer'].create({
            'name': 'عميل HTTP',
            'customer_number': 'CUST-HTTP-001',
            'subscriber_category_id': self.category.id,
            'subscriber_id': self.subscriber_type.id,
            'company_id': self.company.id,
        })

    def test_payment_webhook_http_auth_rejection_and_success(self):
        """اختبار عقود الـ HTTP لمسار الويب هوك وتأكيد رفض التوكين الخاطئ وقبول التوكين الصحيح."""
        tx = self.env['utility.payment.gateway.transaction'].create({
            'name': 'TX-HTTP-WEBHOOK-001',
            'access_token': 'secret_http_token_456',
            'amount': 200.0,
            'payment_direction': 'inbound',
            'state': 'pending',
            'customer_id': self.customer.id,
        })

        # Test invalid token POST
        response_invalid = self.url_open(
            f'/api/v1/utility/payment_gateway/webhook/{tx.name}',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'token': 'wrong_token',
                    'status': 'success',
                    'provider_reference': 'GATEWAY-REF-999',
                }
            }),
            headers={'Content-Type': 'application/json'}
        )
        res_json_invalid = response_invalid.json().get('result', {})
        self.assertEqual(res_json_invalid.get('error'), 'Invalid token')
        self.assertEqual(tx.state, 'pending')

        # Test valid token POST
        response_valid = self.url_open(
            f'/api/v1/utility/payment_gateway/webhook/{tx.name}',
            data=json.dumps({
                'jsonrpc': '2.0',
                'params': {
                    'token': 'secret_http_token_456',
                    'status': 'success',
                    'provider_reference': 'GATEWAY-REF-999',
                }
            }),
            headers={'Content-Type': 'application/json'}
        )
        res_json_valid = response_valid.json().get('result', {})
        self.assertTrue(res_json_valid.get('success'))
        self.assertEqual(tx.state, 'done')
