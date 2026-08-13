from unittest.mock import MagicMock
from psycopg2 import OperationalError
from odoo.tests.common import TransactionCase


class TestReadingBatchConcurrency(TransactionCase):

    def test_reading_batch_process_batch_55p03_lock_contention(self):
        """التحقق من أن تنافس الحجز PostgreSQL 55P03 على دفعة القراءات يُعالج بسلاسة بدون تكرار الأسطر."""
        batch_service = self.env['utility.reading.batch.service']
        mock_cr = MagicMock()
        err = OperationalError()
        err.pgcode = '55P03'
        mock_cr.execute.side_effect = err

        original_cr = batch_service.env.cr
        try:
            batch_service.env.cr = mock_cr
            batch = self.env['utility.reading.batch'].create({
                'name': 'BATCH-LOCK-TEST',
                'batch_uuid': 'UUID-LOCK-TEST-001',
                'state': 'draft',
            })
            res = batch_service.process_batch(batch.id)
            self.assertEqual(res, {'status': 'locked', 'reason': 'batch_locked'})
        finally:
            batch_service.env.cr = original_cr
