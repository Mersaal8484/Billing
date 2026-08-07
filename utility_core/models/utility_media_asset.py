import uuid
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class UtilityMediaAsset(models.Model):
    _name = 'utility.media.asset'
    _description = 'أصل وسائط رقمية (Canonical Utility Media Asset)'
    _order = 'uploaded_at desc, id desc'

    name = fields.Char('اسم الأصل الرقمي', compute='_compute_name', store=True)
    asset_uuid = fields.Char(
        string='رمز المعرف الفريد (Asset UUID)',
        required=True,
        copy=False,
        index=True,
        default=lambda self: str(uuid.uuid4())
    )
    asset_type = fields.Selection([
        ('meter_reading', 'صورة قراءة عداد'),
        ('tamper_evidence', 'إثبات مخالفة/تعدي'),
        ('batch_attachment', 'مرفق دفعة رفع'),
        ('other', 'أخرى'),
    ], string='نوع الأصل الرقمي', default='meter_reading', required=True, index=True)

    reading_id = fields.Many2one('utility.reading', string='القراءة المرتبطة', index=True, ondelete='cascade')
    batch_id = fields.Many2one('utility.reading.batch', string='الدفعة المرتبطة', index=True, ondelete='set null')

    original_filename = fields.Char('اسم الملف الأصلي', required=True)
    mime_type = fields.Char('نوع الملف MIME', default='image/jpeg', required=True)
    file_size = fields.Integer('حجم الملف بالبايت', default=0)
    sha256 = fields.Char('بصمة المجموع التفريقي SHA256', index=True)

    state = fields.Selection([
        ('uploading', 'قيد الرفع'),
        ('uploaded', 'تم الرفع'),
        ('processing', 'قيد المعالجة وتوليد النسخ'),
        ('ready', 'جاهز وقابل للعرض'),
        ('failed', 'فشل المعالجة'),
        ('archived', 'مؤرشف'),
        ('deleted', 'محذوف'),
    ], string='حالة الأصل الرقمي', default='uploaded', required=True, index=True)

    revision = fields.Integer('رقم التعديل', default=1, required=True)
    storage_backend = fields.Selection([
        ('attachment', 'مرفقات Odoo الرسمية (ir.attachment)'),
        ('filesystem', 'نظام ملفات الخادم المباشر (Filesystem)'),
        ('s3', 'تخزين سحابي S3/MinIO'),
    ], string='خادم التخزين الرقمي', default='attachment', required=True, index=True)

    # ===== روابط المرفقات المحلية (Development Phase) =====
    original_attachment_id = fields.Many2one('ir.attachment', string='المرفق الأصلي الكامل', ondelete='set null')
    review_attachment_id = fields.Many2one('ir.attachment', string='مرفق المعاينة والتكبير (Medium)', ondelete='set null')
    thumbnail_attachment_id = fields.Many2one('ir.attachment', string='المرفق المصغر (Thumbnail)', ondelete='set null')

    # ===== مراجع التخزين الخارجي المستقبلي (Production Phase) =====
    external_original_reference = fields.Char('مرجع التخزين الخارجي الأصلي')
    external_review_reference = fields.Char('مرجع التخزين الخارجي للمعاينة')
    external_thumbnail_reference = fields.Char('مرجع التخزين الخارجي للمصغر')

    uploaded_at = fields.Datetime('تاريخ الرفع', default=fields.Datetime.now, required=True)
    processed_at = fields.Datetime('تاريخ اكتمال المعالجة وتوليد النسخ')

    error_code = fields.Char('رمز الخطأ')
    error_message = fields.Text('رسالة الخطأ')

    # ===== روابط للعرض السريع في الواجهات (URL Helpers) =====
    original_url = fields.Char('رابط الصورة الأصلية', compute='_compute_urls')
    review_url = fields.Char('رابط صورة المعاينة المكبرة', compute='_compute_urls')
    thumbnail_url = fields.Char('رابط المصغر للتداول والسجلات', compute='_compute_urls')

    _sql_constraints = [
        ('unique_asset_uuid', 'unique(asset_uuid)', 'رمز المعرف الفريد للأصل (Asset UUID) يجب أن يكون فريداً!'),
    ]

    @api.depends('original_filename', 'asset_uuid')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.original_filename or f"Asset-{rec.asset_uuid[:8]}"

    @api.depends('original_attachment_id', 'review_attachment_id', 'thumbnail_attachment_id', 'storage_backend')
    def _compute_urls(self):
        for rec in self:
            rec.original_url = rec.get_variant_url('original')
            rec.review_url = rec.get_variant_url('review')
            rec.thumbnail_url = rec.get_variant_url('thumbnail')

    def get_variant_url(self, variant='original'):
        self.ensure_one()
        if self.storage_backend == 'attachment':
            if variant == 'thumbnail' and self.thumbnail_attachment_id:
                return f"/web/image/{self.thumbnail_attachment_id.id}"
            elif variant == 'review' and self.review_attachment_id:
                return f"/web/image/{self.review_attachment_id.id}"
            elif self.original_attachment_id:
                return f"/web/image/{self.original_attachment_id.id}"
            return ''
        elif self.storage_backend == 'filesystem':
            ref = getattr(self, f"external_{variant}_reference", False) or self.external_original_reference
            return f"/media/file/{ref}" if ref else ''
        elif self.storage_backend == 's3':
            ref = getattr(self, f"external_{variant}_reference", False) or self.external_original_reference
            return f"https://s3.amazonaws.com/utility-media/{ref}" if ref else ''
        return ''

    def check_user_access_security(self, user=None):
        """التحقق من صلاحية الوصول للأصل الرقمي وفق النطاق الجغرافي للمستخدم.

        Admin فقط unrestricted. كل الأدوار الأخرى تخضع لـ assigned_region_ids.
        Default-Deny: مستخدم بدون مناطق لا يصل لوسائط القراءات المرتبطة.
        يدعم: قراءة مشترك → account_id.region_id
               قراءة شبكية  → meter_id.transformer_id.region_id / feeder_id.region_id
        """
        self.ensure_one()
        user = user or self.env.user
        # Admin فقط unrestricted
        if user.has_group('utility_core.group_utility_admin'):
            return True

        regions = user.assigned_region_ids
        reading = self.reading_id
        if not reading:
            return True

        if not regions:
            raise AccessError(_("عذراً، ليس لديك مناطق جغرافية محددة للوصول لوسائط القراءات."))

        # تحديد المنطقة: مشترك → شبكي
        region = False
        if reading.account_id and reading.account_id.region_id:
            region = reading.account_id.region_id
        elif reading.meter_id:
            if reading.meter_id.transformer_id and hasattr(reading.meter_id.transformer_id, 'region_id'):
                region = reading.meter_id.transformer_id.region_id
            elif reading.meter_id.feeder_id and hasattr(reading.meter_id.feeder_id, 'region_id'):
                region = reading.meter_id.feeder_id.region_id

        if region and region not in regions:
            raise AccessError(_("عذراً، ليس لديك صلاحية للوصول لوسائط المنطقة التشغيلية المحددة."))
        return True

