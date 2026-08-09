import uuid

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class UtilityMediaAsset(models.Model):
    _name = 'utility.media.asset'
    _description = 'Canonical Utility Media Asset'
    _order = 'uploaded_at desc, id desc'

    name = fields.Char('Media Asset', compute='_compute_name', store=True)
    asset_uuid = fields.Char(
        'Asset UUID',
        required=True,
        copy=False,
        index=True,
        default=lambda self: str(uuid.uuid4()),
    )
    batch_id = fields.Many2one(
        'utility.reading.batch',
        string='Reading Batch',
        index=True,
        ondelete='set null',
    )
    reading_uuid = fields.Char('Client Reading UUID', index=True, copy=False)
    reading_id = fields.Many2one(
        'utility.reading',
        string='Linked Reading',
        index=True,
        ondelete='cascade',
    )
    asset_type = fields.Selection([
        ('meter_reading', 'Meter Reading Evidence'),
        ('tamper_evidence', 'Tamper Evidence'),
        ('batch_attachment', 'Batch Attachment'),
        ('other', 'Other'),
    ], string='Asset Type', default='meter_reading', required=True, index=True)

    original_filename = fields.Char('Original Filename', required=True)
    original_path = fields.Char('Original Path', index=True)
    review_path = fields.Char('Review Path')
    thumbnail_path = fields.Char('Thumbnail Path')
    sha256 = fields.Char('SHA256', index=True)
    mime_type = fields.Char('MIME Type', default='image/jpeg', required=True)
    file_size = fields.Integer('File Size', default=0)
    state = fields.Selection([
        ('uploading', 'Uploading'),
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ], string='State', default='uploaded', required=True, index=True)
    storage_backend = fields.Selection([
        ('filesystem', 'Filesystem'),
        ('s3', 'S3 Compatible'),
    ], string='Storage Backend', default='filesystem', required=True, index=True)
    revision = fields.Integer('Revision', default=1, required=True)
    uploaded_at = fields.Datetime('Uploaded At', default=fields.Datetime.now, required=True)
    processed_at = fields.Datetime('Processed At')
    error_code = fields.Char('Error Code')
    error_message = fields.Text('Error Message')

    original_url = fields.Char('Original URL', compute='_compute_urls')
    review_url = fields.Char('Review URL', compute='_compute_urls')
    thumbnail_url = fields.Char('Thumbnail URL', compute='_compute_urls')

    _sql_constraints = [
        ('unique_asset_uuid', 'unique(asset_uuid)', 'Asset UUID must be unique.'),
        ('unique_batch_reading_uuid',
         'unique(batch_id, reading_uuid)',
         'Client reading UUID must be unique inside the same batch.'),
    ]

    @api.depends('original_filename', 'asset_uuid')
    def _compute_name(self):
        for asset in self:
            asset.name = asset.original_filename or f"Asset-{(asset.asset_uuid or '')[:8]}"

    @api.depends('original_path', 'review_path', 'thumbnail_path', 'storage_backend', 'revision')
    def _compute_urls(self):
        for asset in self:
            asset.original_url = asset.get_variant_url('original')
            asset.review_url = asset.get_variant_url('review')
            asset.thumbnail_url = asset.get_variant_url('thumbnail')

    def get_variant_path(self, variant='original'):
        self.ensure_one()
        if variant == 'thumbnail' and self.thumbnail_path:
            return self.thumbnail_path
        if variant == 'review' and self.review_path:
            return self.review_path
        return self.original_path or ''

    def get_variant_url(self, variant='original'):
        self.ensure_one()
        path = self.get_variant_path(variant)
        if not path:
            return ''
        if self.storage_backend == 'filesystem':
            return f"/utility/media/{self.asset_uuid}/{variant}"
        if self.storage_backend == 's3':
            return f"/utility/media/{self.asset_uuid}/{variant}"
        return ''

    def check_user_access_security(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if user.has_group('utility_core.group_utility_admin'):
            return True

        reading = self.reading_id
        if not reading:
            return True

        regions = user.assigned_region_ids
        if not regions:
            raise AccessError(_("You do not have an assigned geographic scope for reading media."))

        region = False
        if reading.account_id and reading.account_id.region_id:
            region = reading.account_id.region_id
        elif reading.meter_id:
            if reading.meter_id.transformer_id and hasattr(reading.meter_id.transformer_id, 'region_id'):
                region = reading.meter_id.transformer_id.region_id
            elif reading.meter_id.feeder_id and hasattr(reading.meter_id.feeder_id, 'region_id'):
                region = reading.meter_id.feeder_id.region_id

        if not region:
            raise AccessError(_("Unable to resolve the operational region for this media asset."))
        if region not in regions:
            raise AccessError(_("You do not have access to this region media asset."))
        return True
