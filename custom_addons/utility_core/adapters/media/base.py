class AbstractMediaStorageAdapter:
    """كلاس مجرد ينظم واجهة خادم التخزين الرقمي (Media Storage Adapter Interface)"""

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
