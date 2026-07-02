# خطة رفع القراءات والصور المجدولة (Readings Upload Job)

## 1. مقدمة والهدف
عندما يقوم الجباة أو قارئو العدادات في الميدان برفع مئات القراءات (التي تحتوي على صور العدادات) في نفس اللحظة عبر التطبيق أو أجهزة الـ (Handheld)، فإن محاولة إنشاء السجلات في جدول القراءات الأساسي `utility.reading` بشكل لحظي (Synchronous API) قد يؤدي إلى:
1. استهلاك ضخم للذاكرة (Memory Exhaustion) بسبب حجم الصور.
2. انقطاع الاتصال (Timeout) في التطبيق الميداني.
3. قفل الجداول (Table Locks) مما يبطئ النظام بأكمله.

---

## 2. البدائل الهندسية المتاحة

### الطريقة (أ): استخدام مكتبة Queue Job (OCA)
تعتمد على تثبيت موديول خارجي شهير في أودو اسمه `queue_job`. عند استلام القراءة من الموبايل، يرسلها النظام فوراً إلى "طابور مهام" لتعمل في الخلفية لاحقاً.

**المميزات:**
- لا تحتاج لإنشاء أي جداول إضافية (أكواد أقل).
- توفر شاشات جاهزة (UI) مدمجة ممتازة لتتبع المهام (التي نجحت، والتي فشلت، وقيد الانتظار).
- ميزة **إعادة المحاولة التلقائية** (Auto-Retry) في حال فشل أي قراءة.
- مدعومة من مجتمع OCA ومُجربة في مشاريع كبيرة.

**العيوب:**
- تتطلب تثبيت موديول خارجي (تبعية إضافية).
- تحتاج إلى إعداد خاص في سيرفر أودو (ضبط Workers و Channels) لتعمل بأعلى كفاءة.
- صعوبة التصحيح (Debugging) في بعض الحالات لأن المعالجة تتم بشكل غير متزامن.

---

### الطريقة (ب): نموذج الدفعات / الجلسات (Batch / Session Model) ⭐ مُوصى بها
بدلاً من أن يقوم تطبيق الموبايل بالاتصال بالـ API مع كل قراءة منفردة، يقوم بتجميع قراءات اليوم في **دفعة واحدة (Batch)** تتكون من:
1. **ملف JSON خفيف** يحتوي على بيانات القراءات فقط (بدون صور) — حجمه لا يتجاوز بضع كيلوبايتات.
2. **الصور كمرفقات منفصلة** (Attachments) مرتبطة بسجل الدفعة — كل صورة ملف مستقل.

ثم يقوم الـ Cron Job بفك الملف وإنشاء القراءات الحقيقية على دفعات.

**حساب الأحجام:**
| العنصر | الحجم | ملاحظة |
|--------|-------|--------|
| صورة واحدة (قبل Base64) | ≤ 100 KB | الحد الأقصى المسموح |
| صورة واحدة (بعد Base64) | ≤ 133 KB | Base64 يزيد الحجم ~33% |
| ملف JSON لـ 100 قراءة (بدون صور) | ~50 KB | بيانات نصية فقط |
| 100 صورة كمرفقات منفصلة | ~10 MB | تُخزن في Filestore |
| **إجمالي الدفعة الواحدة** | **~10 MB** | مقبول جداً لأي سيرفر حديث |

```python
class UtilityReadingBatch(models.Model):
    _name = 'utility.reading.batch'
    _description = 'دفعة رفع قراءات'
    _order = 'upload_date desc'

    name = fields.Char('رقم الدفعة', readonly=True)
    user_id = fields.Many2one('res.users', 'القارئ / الجابي',
                              default=lambda self: self.env.user)
    upload_date = fields.Datetime('تاريخ الرفع', default=fields.Datetime.now)
    date_range_id = fields.Many2one('date.range', string='الفترة (الشهر)',
                                    required=True)
    region_id = fields.Many2one('utility.region', string='المنطقة')
    
    # بيانات القراءات (JSON خفيف بدون صور)
    # تُخزن في مسار مستقل: {filestore}/utility_batches/json/
    data_file = fields.Binary('ملف البيانات (JSON)', attachment=True)
    
    # الصور كمرفقات منفصلة مرتبطة بالسجل
    # تُخزن في مسار مستقل: {filestore}/utility_batches/images/
    image_ids = fields.One2many('ir.attachment', 'res_id',
                                domain=[('res_model', '=', 'utility.reading.batch')],
                                string='صور العدادات')
    
    total_readings = fields.Integer('إجمالي القراءات')
    processed_count = fields.Integer('تمت معالجتها', default=0)
    error_count = fields.Integer('فشلت', default=0)
    state = fields.Selection([
        ('uploaded', 'تم الرفع'),
        ('processing', 'قيد المعالجة'),
        ('done', 'مكتمل'),
        ('partial', 'مكتمل جزئياً'),
        ('error', 'خطأ'),
    ], default='uploaded', string='الحالة')
    error_log = fields.Text('سجل الأخطاء')
```

**هيكل ملف JSON المرسل من الموبايل (بدون صور):**
```json
{
  "batch_info": {
    "reader_uid": 5,
    "date_range_id": 12,
    "region_id": 3,
    "upload_timestamp": "2026-07-01T14:30:00"
  },
  "readings": [
    {
      "seq": 1,
      "meter_number": "MTR-001234",
      "reading_value": 1523.5,
      "reading_date": "2026-07-01T09:15:00",
      "reading_category": "customer",
      "image_filename": "MTR-001234_20260701.jpg",
      "remarks": ""
    },
    {
      "seq": 2,
      "meter_number": "MTR-005678",
      "reading_value": 872.0,
      "reading_date": "2026-07-01T09:22:00",
      "reading_category": "customer",
      "image_filename": "MTR-005678_20260701.jpg",
      "remarks": "عداد في مكان صعب الوصول"
    }
  ]
}
```

**المميزات:**
- **أداء خارق:** اتصال واحد فقط بالخادم لرفع 100 قراءة بدلاً من 100 اتصال متزامن.
- **فصل الصور عن البيانات:** ملف الـ JSON خفيف (~50 KB)، والصور تُرفع كمرفقات منفصلة — مما يسهّل إعادة المحاولة إذا فشل رفع صورة واحدة.
- تتبع أداء الجباة بشكل ممتاز (جلسة الموظف أحمد: 100 قراءة، نجح 95، فشل 5).
- لا تبعيات خارجية (لا حاجة لموديول OCA).

**العيوب:**
- تتطلب تعديلاً من طرف فريق تطوير تطبيق الموبايل.

---

### الطريقة (ج): الإدخال المباشر وتأجيل العمليات (Direct Insert + Deferred Compute)
يتم إنشاء القراءات مباشرة في الجدول الأصلي `utility.reading`، ولكن بحالة مبدئية جديدة `uploaded` (تم الرفع). يتم تعطيل الدوال الحسابية الثقيلة (Computes) عند الإنشاء لضمان سرعة الحفظ. لاحقاً، يقوم الـ Cron Job بأخذ القراءات بحالة `uploaded` ويشغل عليها الحسابات ويحولها إلى `draft`.

**المميزات:**
- **أسهل وأسرع طريقة برمجياً:** لا جداول وسيطة ولا موديولات خارجية ولا ملفات JSON.
- القراءة تظهر فوراً في الجدول الرئيسي.
- أقل كمية أكواد جديدة مطلوبة.

**العيوب:**
- إذا أرسل تطبيق الموبايل آلاف الصور في نفس الثانية، فقد يتأثر الخادم.
- يتطلب إضافة `context` خاص في جميع دوال `@api.depends` لمنع الحسابات المبكرة.
- لا توجد آلية تتبع مُجمعة ("من رفع ماذا ومتى").

---

## 3. جدول المقارنة

| المعيار | (أ) Queue Job OCA | (ب) نموذج الدفعات ⭐ | (ج) إدخال مباشر |
|---------|:-:|:-:|:-:|
| **سهولة التطوير** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **الأداء عند الرفع** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **التتبع والتقارير** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **عدم الحاجة لتبعيات خارجية** | ❌ | ✅ | ✅ |
| **عدم الحاجة لتعديل تطبيق الموبايل** | ✅ | ❌ | ✅ |
| **معالجة الأخطاء** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **قابلية الصيانة** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **ملائمة لعدد كبير جداً (+10,000)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 4. التوصية النهائية

> الطريقة **(ب) نموذج الدفعات** هي الأفضل لبيئة عمل شركات الكهرباء، لأنها تجمع بين الأداء العالي والتتبع الممتاز والاستقلالية عن أي مكتبات خارجية.

---

## 5. توصيات لفريق تطوير تطبيق الموبايل

### 5.1 هيكل الاتصال بالـ API

| الخطوة | الوصف | النقطة (Endpoint) | الطريقة |
|--------|-------|-------------------|---------|
| 1 | إنشاء سجل الدفعة | `/api/reading.batch/create` | POST |
| 2 | رفع ملف JSON (البيانات) | `/api/reading.batch/{id}/upload_data` | POST (multipart) |
| 3 | رفع الصور (واحدة تلو الأخرى) | `/api/reading.batch/{id}/upload_image` | POST (multipart) |
| 4 | تأكيد اكتمال الرفع | `/api/reading.batch/{id}/confirm` | POST |

### 5.2 قواعد الصور

| القاعدة | القيمة |
|---------|--------|
| الحد الأقصى لحجم الصورة الواحدة | **100 كيلوبايت** |
| الصيغ المقبولة | JPEG, PNG, WebP |
| أبعاد الصورة المُوصى بها | 640×480 بكسل (كافية لقراءة أرقام العداد) |
| الضغط المطلوب قبل الرفع | JPEG Quality 70% أو WebP Quality 60% |
| اسم الملف | `{meter_number}_{YYYYMMDD}.jpg` (مثال: `MTR-001234_20260701.jpg`) |
| الحد الأقصى لعدد الصور في الدفعة | **100 صورة** |

### 5.3 آلية العمل المطلوبة في التطبيق

```
┌─────────────────────────────────────────────────┐
│              تطبيق الموبايل (Offline Mode)       │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. الجابي يسجل القراءات طوال اليوم محلياً     │
│     (SQLite أو ملفات محلية)                     │
│                                                 │
│  2. عند توفر الاتصال (أو نهاية الوردية):       │
│     ┌───────────────────────────────────┐       │
│     │ تجميع القراءات في ملف JSON واحد  │       │
│     │ (بدون صور — بيانات نصية فقط)     │       │
│     └──────────────┬────────────────────┘       │
│                    │                            │
│     ┌──────────────▼────────────────────┐       │
│     │ ضغط الصور (JPEG 70% / WebP 60%) │       │
│     │ الحد الأقصى: 100 KB لكل صورة     │       │
│     └──────────────┬────────────────────┘       │
│                    │                            │
│     ┌──────────────▼────────────────────┐       │
│     │ رفع الملف JSON أولاً             │       │
│     │ ← استلام batch_id من الخادم      │       │
│     └──────────────┬────────────────────┘       │
│                    │                            │
│     ┌──────────────▼────────────────────┐       │
│     │ رفع الصور واحدة تلو الأخرى      │       │
│     │ مع ربطها بـ batch_id              │       │
│     │ (إعادة المحاولة 3 مرات لكل صورة) │       │
│     └──────────────┬────────────────────┘       │
│                    │                            │
│     ┌──────────────▼────────────────────┐       │
│     │ تأكيد اكتمال الرفع (Confirm)     │       │
│     │ ← الخادم يبدأ المعالجة           │       │
│     └───────────────────────────────────┘       │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 5.4 معالجة حالات الفشل (Error Handling)

| الحالة | السلوك المطلوب |
|--------|----------------|
| فشل رفع ملف الـ JSON | إعادة المحاولة 3 مرات، ثم حفظ الدفعة محلياً لمحاولة لاحقة |
| فشل رفع صورة واحدة | تخطي الصورة ومتابعة رفع الباقي، ثم إعادة محاولة الصور الفاشلة لاحقاً |
| انقطاع الاتصال أثناء الرفع | حفظ حالة التقدم محلياً (أي صور تم رفعها وأيها لم ترفع بعد) واستكمال الرفع عند عودة الاتصال |
| الخادم يرفض قراءة (عداد غير موجود) | عدم إيقاف العملية؛ يقوم الخادم بتسجيل الخطأ في `error_log` والمتابعة |

### 5.5 حقول JSON الإلزامية والاختيارية

| الحقل | النوع | إلزامي | الوصف |
|-------|-------|:------:|-------|
| `meter_number` | String | ✅ | رقم العداد كما هو مسجل في النظام |
| `reading_value` | Float | ✅ | قيمة القراءة الظاهرة على العداد |
| `reading_date` | DateTime (ISO 8601) | ✅ | تاريخ ووقت أخذ القراءة |
| `reading_category` | String | ✅ | `customer` أو `transformer` أو `feeder` |
| `image_filename` | String | ✅ | اسم ملف الصورة المرتبط (لربطها بالمرفق) |
| `seq` | Integer | ✅ | رقم تسلسلي للقراءة داخل الدفعة |
| `remarks` | String | ❌ | ملاحظات الجابي (مكان صعب، عداد تالف، إلخ) |
| `gps_lat` | Float | ❌ | خط العرض (إن توفر) |
| `gps_lng` | Float | ❌ | خط الطول (إن توفر) |

### 5.6 معايير الأداء المستهدفة

| المعيار | القيمة المستهدفة |
|---------|-----------------|
| زمن رفع ملف JSON واحد (100 قراءة) | < 2 ثانية |
| زمن رفع صورة واحدة (100 KB) | < 1 ثانية |
| إجمالي زمن رفع دفعة كاملة (100 قراءة + 100 صورة) | < 3 دقائق |
| حد أقصى لحجم الدفعة الواحدة | 100 قراءة |
| حد أقصى لعدد الدفعات اليومية لكل جابي | غير محدود |

---

## 6. إعدادات مشتركة (System Parameters)
- حقل الصورة `meter_image` يجب أن يكون `attachment=True` لتخزين الصور في الـ Filestore.
- حقل الفترة `date_range_id` إلزامي عند الرفع لربط القراءة بفترة الفوترة الصحيحة.
- حجم الدفعة يُخزن في `ir.config_parameter`:
  - `utility.reading_upload_batch_size` = 100 (حجم الدفعة عند الرفع)
  - `utility.billing_batch_size` = 500 (حجم الدفعة عند الفوترة — راجع BATCH_BILLING_JOB_PLAN.md)
  - `utility.max_image_size_kb` = 100 (الحد الأقصى لحجم الصورة بالكيلوبايت)
  - `utility.batch_file_retention_days` = 30 (عدد أيام الاحتفاظ بملفات الدفعات قبل الحذف التلقائي)
  - `utility.batch_filestore_path` = `utility_batches` (اسم المجلد المستقل داخل الـ Filestore)

---

## 7. إدارة التخزين (Filestore Management)

### 7.1 مسار تخزين مستقل
بدلاً من خلط ملفات الدفعات مع باقي مرفقات أودو (الفواتير، المستندات، إلخ)، يتم تخصيص مجلد فرعي مستقل داخل الـ Filestore:

```
{odoo_filestore}/
├── 00/                          ← مرفقات أودو العادية
├── 01/
├── ...
└── utility_batches/             ← مجلد مستقل للدفعات
    ├── json/                    ← ملفات بيانات القراءات
    │   ├── 2026-07/
    │   │   ├── BATCH-0001.json
    │   │   └── BATCH-0002.json
    │   └── 2026-08/
    └── images/                  ← صور العدادات
        ├── 2026-07/
        │   ├── MTR-001234_20260701.jpg
        │   └── MTR-005678_20260701.jpg
        └── 2026-08/
```

**التنفيذ البرمجي — تجاوز دالة `_file_write` في `ir.attachment`:**
```python
import os
from odoo import models, api

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def _get_utility_batch_store_path(self, month_folder):
        """إرجاع مسار التخزين المستقل لملفات الدفعات"""
        base_path = self.env['ir.config_parameter'].sudo().get_param(
            'utility.batch_filestore_path', 'utility_batches')
        filestore = self._filestore()
        path = os.path.join(filestore, base_path, month_folder)
        os.makedirs(path, exist_ok=True)
        return path

    def _compute_store_fname(self, vals):
        """توجيه مرفقات الدفعات إلى مسار مستقل"""
        if vals.get('res_model') == 'utility.reading.batch':
            from datetime import datetime
            month = datetime.now().strftime('%Y-%m')
            subfolder = 'json' if vals.get('name', '').endswith('.json') else 'images'
            base = self._get_utility_batch_store_path(f'{subfolder}/{month}')
            # إنشاء اسم فريد للملف
            fname = f"{vals.get('name', 'file')}_{os.urandom(8).hex()}"
            return os.path.join(base, fname)
        return super()._compute_store_fname(vals)
```

### 7.2 التنظيف التلقائي (Auto-Cleanup Cron)
بعد اكتمال معالجة الدفعة ونقل البيانات والصور إلى جدول `utility.reading` الفعلي، تصبح ملفات الدفعة الأصلية (JSON + صور) غير ضرورية. يتم حذفها تلقائياً بعد فترة احتفاظ محددة (افتراضياً **30 يوماً**).

**مهمة مجدولة (Cron Job) للتنظيف:**
```xml
<record id="ir_cron_cleanup_batch_files" model="ir.cron">
    <field name="name">Utility: Cleanup Old Batch Files</field>
    <field name="model_id" ref="model_utility_reading_batch"/>
    <field name="state">code</field>
    <field name="code">model._cron_cleanup_old_batches()</field>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="numbercall">-1</field>
    <field name="active" eval="True"/>
</record>
```

**دالة التنظيف:**
```python
from datetime import timedelta

@api.model
def _cron_cleanup_old_batches(self):
    """حذف ملفات الدفعات المكتملة بعد انتهاء فترة الاحتفاظ"""
    retention_days = int(self.env['ir.config_parameter'].sudo().get_param(
        'utility.batch_file_retention_days', 30))
    cutoff_date = fields.Datetime.now() - timedelta(days=retention_days)

    # البحث عن الدفعات المكتملة القديمة التي لا تزال تحتوي على ملفات
    old_batches = self.search([
        ('state', 'in', ('done', 'partial')),
        ('upload_date', '<', cutoff_date),
        '|',
        ('data_file', '!=', False),
        ('image_ids', '!=', False),
    ])

    for batch in old_batches:
        # 1. حذف ملف الـ JSON من الهارد ديسك
        if batch.data_file:
            json_attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'utility.reading.batch'),
                ('res_id', '=', batch.id),
                ('res_field', '=', 'data_file'),
            ], limit=1)
            if json_attachment:
                json_attachment.unlink()  # يحذف من الـ Filestore تلقائياً
            batch.data_file = False

        # 2. حذف الصور المرفقة من الهارد ديسك
        if batch.image_ids:
            batch.image_ids.unlink()  # يحذف من الـ Filestore تلقائياً

        # 3. تسجيل عملية التنظيف
        batch.message_post(
            body=f'تم حذف ملفات الدفعة تلقائياً بعد {retention_days} يوماً من الرفع.'
        )

    # تنظيف المجلدات الفارغة في الـ Filestore
    self._cleanup_empty_dirs()
```

**دالة تنظيف المجلدات الفارغة:**
```python
def _cleanup_empty_dirs(self):
    """حذف المجلدات الفارغة من مسار التخزين المستقل"""
    import os
    base_path = self.env['ir.config_parameter'].sudo().get_param(
        'utility.batch_filestore_path', 'utility_batches')
    filestore = self.env['ir.attachment']._filestore()
    batch_root = os.path.join(filestore, base_path)
    
    if not os.path.exists(batch_root):
        return
    
    for dirpath, dirnames, filenames in os.walk(batch_root, topdown=False):
        if not dirnames and not filenames and dirpath != batch_root:
            os.rmdir(dirpath)
```

### 7.3 مثال عملي على دورة حياة الملفات

| التاريخ | الحدث | حالة الملفات |
|---------|-------|-------------|
| 1 يوليو | الجابي يرفع دفعة BATCH-0050 (100 قراءة + 100 صورة) | JSON + صور موجودة في `utility_batches/` |
| 1 يوليو | الـ Cron يعالج الدفعة → ينشئ 100 سجل في `utility.reading` (مع نسخ الصور كمرفقات) | JSON + صور أصلية لا تزال موجودة (للرجوع إليها) |
| 1 أغسطس | الـ Cron اليومي يكتشف أن الدفعة مضى عليها 30 يوماً | **يحذف** ملف JSON + الصور الأصلية من `utility_batches/` |
| — | صور العدادات المنسوخة إلى `utility.reading` | **تبقى** كمرفقات عادية في Filestore الرئيسي |

> **ملاحظة مهمة:** الصور المنسوخة إلى القراءات الفعلية `utility.reading` لا تتأثر بعملية التنظيف. الذي يُحذف هو فقط ملفات الدفعة الأصلية (النسخة الخام المرفوعة من الموبايل).

---

## 8. دليل التنفيذ لفريق تطوير Flutter

### 8.1 المكتبات المطلوبة (pubspec.yaml)
```yaml
dependencies:
  # اتصال بـ Odoo XML-RPC
  xml_rpc: ^0.3.0              # أو http مباشرة
  dio: ^5.4.0                  # HTTP client مع دعم retry و multipart
  
  # التخزين المحلي (Offline)
  sqflite: ^2.3.0              # قاعدة بيانات محلية SQLite
  path_provider: ^2.1.0        # مسارات التخزين المحلية
  
  # الكاميرا وضغط الصور
  image_picker: ^1.0.0         # التقاط الصور
  flutter_image_compress: ^2.1.0  # ضغط الصور قبل الرفع
  
  # إدارة الاتصال
  connectivity_plus: ^5.0.0    # كشف حالة الشبكة
  
  # إدارة الحالة
  riverpod: ^2.5.0             # أو provider حسب المشروع
```

### 8.2 نموذج البيانات (Dart Models)

```dart
// ===== نموذج القراءة المحلية =====
class MeterReading {
  final int? localId;           // معرف SQLite المحلي
  final String meterNumber;     // رقم العداد
  final double readingValue;    // قيمة القراءة
  final DateTime readingDate;   // تاريخ ووقت القراءة
  final String readingCategory; // customer | transformer | feeder
  final String? imagePath;      // مسار الصورة المحلية (بعد الضغط)
  final String? imageFilename;  // اسم الملف: MTR-001234_20260701.jpg
  final String? remarks;        // ملاحظات الجابي
  final bool isSynced;          // هل تم رفعها للسيرفر؟

  MeterReading({
    this.localId,
    required this.meterNumber,
    required this.readingValue,
    required this.readingDate,
    this.readingCategory = 'customer',
    this.imagePath,
    this.imageFilename,
    this.remarks,
    this.isSynced = false,
  });

  Map<String, dynamic> toJson() => {
    'seq': localId,
    'meter_number': meterNumber,
    'reading_value': readingValue,
    'reading_date': readingDate.toIso8601String(),
    'reading_category': readingCategory,
    'image_filename': imageFilename ?? '',
    'remarks': remarks ?? '',
  };

  Map<String, dynamic> toSqlite() => {
    'meter_number': meterNumber,
    'reading_value': readingValue,
    'reading_date': readingDate.toIso8601String(),
    'reading_category': readingCategory,
    'image_path': imagePath,
    'image_filename': imageFilename,
    'remarks': remarks,
    'is_synced': isSynced ? 1 : 0,
  };
}

// ===== نموذج الدفعة =====
class ReadingBatch {
  final int readerUid;          // معرف المستخدم في Odoo
  final int dateRangeId;        // معرف الفترة
  final int? regionId;          // معرف المنطقة
  final List<MeterReading> readings;

  ReadingBatch({
    required this.readerUid,
    required this.dateRangeId,
    this.regionId,
    required this.readings,
  });

  Map<String, dynamic> toJson() => {
    'batch_info': {
      'reader_uid': readerUid,
      'date_range_id': dateRangeId,
      'region_id': regionId,
      'upload_timestamp': DateTime.now().toIso8601String(),
    },
    'readings': readings.map((r) => r.toJson()).toList(),
  };
}
```

### 8.3 ضغط الصور قبل الرفع (Image Compression)

```dart
import 'dart:io';
import 'package:flutter_image_compress/flutter_image_compress.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

class ImageCompressor {
  /// الحد الأقصى لحجم الصورة: 100 KB
  static const int maxSizeKB = 100;
  
  /// ضغط صورة العداد مع ضمان عدم تجاوز الحد الأقصى
  static Future<File?> compressMeterImage({
    required String sourcePath,
    required String meterNumber,
  }) async {
    final dir = await getTemporaryDirectory();
    final timestamp = DateTime.now().toIso8601String().split('T').first.replaceAll('-', '');
    final targetPath = p.join(dir.path, '${meterNumber}_$timestamp.jpg');

    // المرحلة 1: ضغط بجودة 70% وتصغير الأبعاد إلى 640x480
    var result = await FlutterImageCompress.compressAndGetFile(
      sourcePath,
      targetPath,
      quality: 70,
      minWidth: 640,
      minHeight: 480,
      format: CompressFormat.jpeg,
    );

    if (result == null) return null;

    // المرحلة 2: إذا لا يزال الحجم أكبر من 100 KB، نخفض الجودة تدريجياً
    int quality = 60;
    while (await result!.length() > maxSizeKB * 1024 && quality > 20) {
      result = await FlutterImageCompress.compressAndGetFile(
        sourcePath,
        targetPath,
        quality: quality,
        minWidth: 640,
        minHeight: 480,
        format: CompressFormat.jpeg,
      );
      quality -= 10;
    }

    return File(result!.path);
  }
}
```

### 8.4 قاعدة البيانات المحلية (SQLite - Offline Storage)

```dart
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

class ReadingDatabase {
  static Database? _db;

  static Future<Database> get database async {
    _db ??= await _initDB();
    return _db!;
  }

  static Future<Database> _initDB() async {
    final path = join(await getDatabasesPath(), 'readings.db');
    return openDatabase(path, version: 1, onCreate: (db, version) async {
      await db.execute('''
        CREATE TABLE readings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          meter_number TEXT NOT NULL,
          reading_value REAL NOT NULL,
          reading_date TEXT NOT NULL,
          reading_category TEXT DEFAULT 'customer',
          image_path TEXT,
          image_filename TEXT,
          remarks TEXT,
          is_synced INTEGER DEFAULT 0,
          batch_id INTEGER,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
      ''');
    });
  }

  /// حفظ القراءة محلياً (أثناء العمل الميداني)
  static Future<int> insertReading(MeterReading reading) async {
    final db = await database;
    return db.insert('readings', reading.toSqlite());
  }

  /// جلب القراءات غير المرفوعة
  static Future<List<MeterReading>> getUnsyncedReadings() async {
    final db = await database;
    final maps = await db.query('readings', where: 'is_synced = 0');
    return maps.map((m) => MeterReading(
      localId: m['id'] as int,
      meterNumber: m['meter_number'] as String,
      readingValue: m['reading_value'] as double,
      readingDate: DateTime.parse(m['reading_date'] as String),
      readingCategory: m['reading_category'] as String? ?? 'customer',
      imagePath: m['image_path'] as String?,
      imageFilename: m['image_filename'] as String?,
      remarks: m['remarks'] as String?,
    )).toList();
  }

  /// تحديث حالة القراءات بعد الرفع
  static Future<void> markAsSynced(List<int> ids) async {
    final db = await database;
    await db.update('readings', {'is_synced': 1},
        where: 'id IN (${ids.join(",")})');
  }
}
```

### 8.5 خدمة المزامنة مع Odoo (Sync Service)

```dart
import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';

class OdooSyncService {
  final Dio _dio;
  final String baseUrl;    // مثال: https://erp.company.com
  final String dbName;     // اسم قاعدة بيانات Odoo
  final int uid;           // معرف المستخدم
  final String password;   // كلمة المرور أو API Key

  OdooSyncService({
    required this.baseUrl,
    required this.dbName,
    required this.uid,
    required this.password,
  }) : _dio = Dio(BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 30),
    receiveTimeout: const Duration(seconds: 60),
  ));

  /// ===== الخطوة 1: إنشاء سجل الدفعة في Odoo =====
  Future<int> createBatch({
    required int dateRangeId,
    int? regionId,
    required int totalReadings,
  }) async {
    final response = await _callOdoo('utility.reading.batch', 'create', [
      {
        'date_range_id': dateRangeId,
        'region_id': regionId,
        'total_readings': totalReadings,
      }
    ]);
    return response as int; // يرجع batch_id
  }

  /// ===== الخطوة 2: رفع ملف JSON (البيانات فقط) =====
  Future<void> uploadBatchData({
    required int batchId,
    required ReadingBatch batch,
  }) async {
    final jsonString = jsonEncode(batch.toJson());
    final base64Data = base64Encode(utf8.encode(jsonString));

    await _callOdoo('utility.reading.batch', 'write', [
      [batchId],
      {'data_file': base64Data},
    ]);
  }

  /// ===== الخطوة 3: رفع الصور كمرفقات منفصلة =====
  Future<bool> uploadImage({
    required int batchId,
    required String filePath,
    required String filename,
    int retries = 3,
  }) async {
    for (int attempt = 1; attempt <= retries; attempt++) {
      try {
        final bytes = await File(filePath).readAsBytes();
        final base64Image = base64Encode(bytes);

        await _callOdoo('ir.attachment', 'create', [
          {
            'name': filename,
            'datas': base64Image,
            'res_model': 'utility.reading.batch',
            'res_id': batchId,
            'mimetype': 'image/jpeg',
          }
        ]);
        return true; // نجحت
      } catch (e) {
        if (attempt == retries) return false; // فشلت بعد كل المحاولات
        await Future.delayed(Duration(seconds: attempt * 2)); // Backoff
      }
    }
    return false;
  }

  /// ===== الخطوة 4: تأكيد اكتمال الرفع =====
  Future<void> confirmBatch(int batchId) async {
    await _callOdoo('utility.reading.batch', 'action_confirm', [
      [batchId]
    ]);
  }

  /// ===== استدعاء Odoo XML-RPC =====
  Future<dynamic> _callOdoo(String model, String method, List args) async {
    final response = await _dio.post(
      '/xmlrpc/2/object',
      data: _buildXmlRpcPayload(model, method, args),
      options: Options(contentType: 'text/xml'),
    );
    return _parseXmlRpcResponse(response.data);
  }

  // ... (دوال XML-RPC المساعدة)
}
```

### 8.6 تدفق المزامنة الكامل (Full Sync Flow)

```dart
class SyncManager {
  final OdooSyncService _odoo;

  SyncManager(this._odoo);

  /// تنفيذ المزامنة الكاملة
  Future<SyncResult> syncReadings({
    required int dateRangeId,
    int? regionId,
    Function(double progress, String message)? onProgress,
  }) async {
    // 1. جلب القراءات غير المرفوعة من SQLite
    final readings = await ReadingDatabase.getUnsyncedReadings();
    if (readings.isEmpty) {
      return SyncResult(success: true, message: 'لا توجد قراءات جديدة');
    }

    onProgress?.call(0.05, 'جارٍ إنشاء الدفعة...');

    // 2. إنشاء سجل الدفعة على الخادم
    final batchId = await _odoo.createBatch(
      dateRangeId: dateRangeId,
      regionId: regionId,
      totalReadings: readings.length,
    );

    onProgress?.call(0.1, 'جارٍ رفع بيانات القراءات...');

    // 3. رفع ملف JSON (بيانات فقط — بدون صور)
    final batch = ReadingBatch(
      readerUid: _odoo.uid,
      dateRangeId: dateRangeId,
      regionId: regionId,
      readings: readings,
    );
    await _odoo.uploadBatchData(batchId: batchId, batch: batch);

    onProgress?.call(0.2, 'جارٍ رفع الصور...');

    // 4. رفع الصور واحدة تلو الأخرى
    int uploaded = 0;
    int failed = 0;
    final failedImages = <String>[];

    for (int i = 0; i < readings.length; i++) {
      final reading = readings[i];
      if (reading.imagePath != null && reading.imageFilename != null) {
        final success = await _odoo.uploadImage(
          batchId: batchId,
          filePath: reading.imagePath!,
          filename: reading.imageFilename!,
        );
        if (success) {
          uploaded++;
        } else {
          failed++;
          failedImages.add(reading.imageFilename!);
        }
      }

      final progress = 0.2 + (0.7 * (i + 1) / readings.length);
      onProgress?.call(progress, 'تم رفع $uploaded من ${readings.length} صورة');
    }

    onProgress?.call(0.95, 'جارٍ تأكيد الدفعة...');

    // 5. تأكيد اكتمال الرفع
    await _odoo.confirmBatch(batchId);

    // 6. تحديث SQLite محلياً
    final ids = readings.map((r) => r.localId!).toList();
    await ReadingDatabase.markAsSynced(ids);

    onProgress?.call(1.0, 'اكتملت المزامنة');

    return SyncResult(
      success: failed == 0,
      totalReadings: readings.length,
      uploadedImages: uploaded,
      failedImages: failed,
      failedImageNames: failedImages,
      message: failed == 0
          ? 'تم رفع ${readings.length} قراءة بنجاح'
          : 'تم رفع $uploaded صورة، فشل $failed صورة',
    );
  }
}

class SyncResult {
  final bool success;
  final int totalReadings;
  final int uploadedImages;
  final int failedImages;
  final List<String> failedImageNames;
  final String message;

  SyncResult({
    required this.success,
    this.totalReadings = 0,
    this.uploadedImages = 0,
    this.failedImages = 0,
    this.failedImageNames = const [],
    required this.message,
  });
}
```

### 8.7 ملخص قواعد فريق Flutter

| # | القاعدة | التفاصيل |
|---|---------|----------|
| 1 | **التخزين المحلي أولاً** | كل قراءة تُحفظ في SQLite فوراً. لا يُفقد أي شيء حتى لو أُغلق التطبيق |
| 2 | **ضغط الصور إلزامي** | JPEG 70% بأبعاد 640×480. لا يُسمح بتجاوز 100 KB لكل صورة |
| 3 | **الـ JSON بدون صور** | ملف البيانات يحتوي على أسماء الصور فقط (`image_filename`)، وليس محتواها |
| 4 | **رفع الصور منفردة** | كل صورة تُرفع كـ `ir.attachment` مستقل مرتبط بـ `batch_id` |
| 5 | **إعادة المحاولة 3 مرات** | مع Exponential Backoff (2s, 4s, 6s) لكل صورة تفشل |
| 6 | **عدم حظر الواجهة** | كل عمليات المزامنة تتم في `Isolate` أو `compute()` منفصل |
| 7 | **شريط تقدم واضح** | يعرض للمستخدم: "تم رفع 45 من 100 صورة..." |
| 8 | **تسمية الملفات** | `{meter_number}_{YYYYMMDD}.jpg` — اسم فريد قابل للتتبع |
| 9 | **لا ترسل دفعة أكبر من 100** | إذا كان لدى الجابي 250 قراءة، يتم تقسيمها إلى 3 دفعات |
| 10 | **التأكيد النهائي** | لا يتم استدعاء `action_confirm` إلا بعد اكتمال رفع كل الصور |
