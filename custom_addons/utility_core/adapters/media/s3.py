import logging
import os

from odoo import _
from odoo.exceptions import UserError, ValidationError

from .base import AbstractMediaStorageAdapter

_logger = logging.getLogger(__name__)


class S3MediaAdapter(AbstractMediaStorageAdapter):
    """S3-compatible media adapter contract.

    The adapter is intentionally disabled for production until a real S3 client
    is wired. It still follows the storage-agnostic contract: store() returns a
    storage key/path string, never an ir.attachment record.
    """

    PRODUCTION_READY = False

    def __init__(self, env):
        self.env = env
        self.endpoint_url = env['ir.config_parameter'].sudo().get_param('utility.s3_endpoint_url', '')
        self.bucket_name = env['ir.config_parameter'].sudo().get_param('utility.s3_bucket_name', '')
        self.access_key = os.environ.get('S3_ACCESS_KEY') or env['ir.config_parameter'].sudo().get_param('utility.s3_access_key', '')
        self.secret_key = os.environ.get('S3_SECRET_KEY') or env['ir.config_parameter'].sudo().get_param('utility.s3_secret_key', '')
        self.region_name = env['ir.config_parameter'].sudo().get_param('utility.s3_region_name', 'us-east-1')

        missing = []
        if not self.endpoint_url:
            missing.append('utility.s3_endpoint_url')
        if not self.bucket_name:
            missing.append('utility.s3_bucket_name')
        if not self.access_key:
            missing.append('utility.s3_access_key')
        if not self.secret_key:
            missing.append('utility.s3_secret_key')
        if missing:
            raise UserError(_("Incomplete S3 media configuration: %s") % ", ".join(missing))

    def store(self, *, file_data, filename, mimetype, metadata=None):
        if not file_data:
            raise ValidationError(_("File content is empty."))
        metadata = metadata or {}
        key = "/".join(filter(None, [
            'readings',
            str(metadata.get('period_code') or 'period_unknown'),
            str(metadata.get('batch_uuid') or metadata.get('asset_uuid') or 'batch_unknown'),
            str(metadata.get('variant') or 'original'),
            filename,
        ]))
        _logger.info("S3 placeholder accepted media key %s", key)
        return key

    def retrieve(self, asset, variant='original'):
        key = self._get_reference_for_variant(asset, variant)
        if key:
            _logger.info("S3 placeholder retrieve requested for key %s", key)
        return b''

    def delete(self, asset):
        if asset.original_path:
            _logger.info("S3 placeholder delete requested for key %s", asset.original_path)
        return True

    def exists(self, asset, variant='original'):
        return bool(self._get_reference_for_variant(asset, variant))

    def get_url(self, asset, variant='original'):
        key = self._get_reference_for_variant(asset, variant)
        return f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{key}" if key else ''

    def _get_reference_for_variant(self, asset, variant):
        if variant == 'thumbnail' and asset.thumbnail_path:
            return asset.thumbnail_path
        if variant == 'review' and asset.review_path:
            return asset.review_path
        return asset.original_path
