import json
from psycopg2 import OperationalError
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo.addons.utility_core.adapters.workflow.local import LocalWorkflowAdapter


class TestWorkflowAtomicClaim(TransactionCase):

    def setUp(self):
        super().setUp()
        self.adapter = LocalWorkflowAdapter(self.env)
        self.period = self.env['date.range'].create({
            'name': 'فترة يناير 2026',
            'code': '2026-01-LOCK-TEST',
            'type_id': self.env['date.range.type'].search([], limit=1).id,
            'date_start': '2026-01-01',
            'date_end': '2026-01-31',
        })

    def test_workflow_command_atomic_claim_executes_payload_exactly_once(self):
        """التحقق من أن الادعاء الذري للأمر (Atomic Claim) يضمن تنفيذ payload_func مرة واحدة فقط والتصدّي للتنفيذ المزدوج."""
        counter = {'calls': 0}

        def _payload():
            counter['calls'] += 1
            return {'status': 'success'}

        # First call: executes payload_func and transitions command state to executed
        res1 = self.adapter._dispatch_command(
            self.period, 'test_atomic_action',
            _payload,
            lambda r: "النتيجة الأولى",
            payload_data={'test': 1}
        )
        self.assertEqual(counter['calls'], 1)

        # Second call with same idempotency_key: returns cached summary without re-executing payload_func
        res2 = self.adapter._dispatch_command(
            self.period, 'test_atomic_action',
            _payload,
            lambda r: "النتيجة الثانية",
            payload_data={'test': 1}
        )
        self.assertEqual(counter['calls'], 1)  # Counter MUST remain 1!
        self.assertEqual(res2, "النتيجة الأولى")

    def test_workflow_command_processing_state_prevents_reclaim(self):
        """التحقق من أن الأمر في حالة processing لا يمكن استرجاعه أو إعادة تنفيذ الإجراء عليه من Worker آخر."""
        idempotency_key = f"TEST_PROC:{self.period.period_code}"
        cmd = self.env['utility.workflow.command'].create({
            'name': 'CMD-TEST-PROC',
            'idempotency_key': idempotency_key,
            'period_id': self.period.id,
            'action_type': 'test_proc',
            'state': 'processing',
            'result_summary': 'جاري المعالجة بواسطة Worker 1',
        })

        counter = {'calls': 0}
        res = self.adapter._dispatch_command(
            self.period, 'test_proc',
            lambda: counter.update(calls=counter['calls'] + 1),
            "ملخص اختباري"
        )
        self.assertEqual(counter['calls'], 0)  # Payload MUST NOT execute on processing command
        self.assertEqual(res, 'جاري المعالجة بواسطة Worker 1')
