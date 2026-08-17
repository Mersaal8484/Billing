class AbstractMediaStorageAdapter:
    """كلاس مجرد ينظم واجهة خادم التخزين الرقمي (Media Storage Adapter Interface)"""

    VARIANTS = ('original', 'review', 'thumbnail')

    def store(self, *, file_data, filename, mimetype, metadata=None):
        """تخزين الملف وإرجاع المعرف المرجعي لعملية التخزين"""
        raise NotImplementedError

    def retrieve(self, asset, variant='original'):
        """استرجاع محتوى الملف ثنائي البايت (Bytes) للفئة/المتغير المحدد"""
        raise NotImplementedError

    def delete(self, asset):
        """حذف الأصل والتنظيف من خادم التخزين"""
        raise NotImplementedError

    def exists(self, asset, variant='original'):
        """التحقق من وجود الأصل في الباك إند"""
        raise NotImplementedError

    def get_url(self, asset, variant='original'):
        """إرجاع رابط URL مباشر للوصول للملف"""
        raise NotImplementedError

    def _get_attachment_for_variant(self, asset, variant):
        if variant not in self.VARIANTS:
            raise ValueError("Unsupported media variant: %s" % variant)
        attachment = getattr(asset, '%s_attachment_id' % variant, False)
        return attachment or asset.original_attachment_id
