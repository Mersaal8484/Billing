import base64
import os

from odoo.tests.common import TransactionCase


class TestIrAttachmentStructuredStorage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Attachment = self.env['ir.attachment']
        self.image_bytes = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        )

    def test_binary_attachment_uses_module_model_year_month_path(self):
        attachment = self.Attachment.create({
            'name': 'structured.png',
            'raw': self.image_bytes,
            'mimetype': 'image/png',
            'res_model': 'utility.media.asset',
        })

        path_parts = attachment.store_fname.replace('\\', '/').split('/')
        self.assertEqual(path_parts[0], 'utility_core')
        self.assertEqual(path_parts[1], 'utility_media_asset')
        self.assertRegex(path_parts[2], r'^20\d{2}$')
        self.assertRegex(path_parts[3], r'^(0[1-9]|1[0-2])$')
        self.assertRegex(path_parts[4], r'^(0[1-9]|[12]\d|3[01])$')
        self.assertEqual(len(path_parts[5]), 40)
        self.assertEqual(
            os.path.normpath(attachment.custom_storage_path),
            os.path.normpath(os.path.dirname(attachment._full_path(attachment.store_fname))),
        )
        self.assertEqual(attachment.raw, self.image_bytes)

    def test_create_multi_keeps_records_and_buckets_separate(self):
        attachments = self.Attachment.create([
            {
                'name': 'utility.png',
                'raw': self.image_bytes,
                'mimetype': 'image/png',
                'res_model': 'utility.media.asset',
            },
            {
                'name': 'partner.png',
                'raw': self.image_bytes,
                'mimetype': 'image/png',
                'res_model': 'res.partner',
            },
        ])

        self.assertEqual(len(attachments), 2)
        self.assertTrue(attachments[0].store_fname.startswith('utility_core/utility_media_asset/'))
        self.assertTrue(attachments[1].store_fname.startswith('base/res_partner/'))
        self.assertEqual(attachments[0].raw, self.image_bytes)
        self.assertEqual(attachments[1].raw, self.image_bytes)
