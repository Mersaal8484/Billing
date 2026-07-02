# خطة الفوترة المجدولة (Batch Billing Job)

## 1. مقدمة والهدف
عند قيام المؤسسة بإصدار فواتير لآلاف المشتركين في وقت واحد، فإن المعالجة اللحظية (Synchronous) لجميع القراءات قد تؤدي إلى:
1. بطء شديد في النظام.
2. انقطاع الاتصال (Timeout) قبل اكتمال العملية.
3. فشل العملية بأكملها إذا احتوت قراءة واحدة على خطأ برمجي أو نقص في البيانات.

لذا، تهدف هذه الخطة إلى نقل عملية الفوترة (توليد أوامر البيع من القراءات) إلى **خلفية النظام (Background Job)** باستخدام مجدول أودو (Cron). بحيث يتم معالجة القراءات على شكل دفعات (Batches)، وتحديداً **500 فاتورة في الدفعة الواحدة**.

## 2. التعديلات البرمجية المطلوبة

### أ. تعديل نموذج القراءات (`utility.reading`)
1. **إضافة حالة جديدة (State):** 
   سيتم إضافة حالة `queued` (في طابور الفوترة) إلى الحقل `state` لتصبح دورة حياة القراءة:
   `draft` -> `under_review` -> `approved` -> `queued` -> `billed`.
2. **إضافة حقل لرسائل الخطأ:**
   حقل نصي `billing_error` لتخزين أي رسالة خطأ تمنع إصدار الفاتورة لتلك القراءة، بدلاً من إيقاف السيرفر.
3. **تعديل زر "إنشاء فواتير" (Batch Action):**
   تحديث دالة `action_generate_bills_batch` لتقوم بتغيير حالة القراءات المحددة من "معتمدة" إلى "في طابور الفوترة" `queued` بدلاً من إصدار الفواتير فوراً.

### ب. إنشاء المجدول (Cron Job)
يتم إضافة ملف XML لتسجيل المهمة المجدولة `ir.cron`:
```xml
<record id="ir_cron_generate_batch_bills" model="ir.cron">
    <field name="name">Utility: Batch Generate Bills</field>
    <field name="model_id" ref="model_utility_reading"/>
    <field name="state">code</field>
    <field name="code">model._cron_generate_bills()</field>
    <field name="interval_number">15</field>
    <field name="interval_type">minutes</field>
    <field name="numbercall">-1</field>
    <field name="active" eval="True"/>
</record>
```

### ج. برمجة دالة الدفعات (Batch Processing Method)
تضاف دالة `@api.model def _cron_generate_bills(self):` في `utility_reading.py` وتقوم بالآتي:
1. **استدعاء الدفعة:**
   تقوم الدالة بالبحث عن القراءات التي تمتلك الحالة `queued`، مع وضع حد أقصى `limit=500` لتخفيف الضغط:
   ```python
   readings = self.search([('state', '=', 'queued')], limit=500)
   ```
2. **المعالجة الآمنة (Try-Except):**
   عمل تكرار (Loop) على القراءات، ومحاولة توليد الفاتورة لكل قراءة داخل كتلة `try...except`.
3. **حفظ التقدم (Commit):**
   لضمان حفظ الفواتير التي تمت بنجاح حتى لو انقطع السيرفر، يتم تنفيذ `self.env.cr.commit()` بعد إتمام الفوترة لكل مجموعة صغيرة (أو لكل قراءة).
   *مثال مبسط لآلية المعالجة:*
   ```python
   for reading in readings:
       try:
           reading.action_generate_bill()
           self.env.cr.commit()
       except Exception as e:
           self.env.cr.rollback()
           reading.write({
               'state': 'error',
               'remarks': f"خطأ أثناء الفوترة: {str(e)}"
           })
           self.env.cr.commit()
   ```

## 3. تعديل واجهات المستخدم (Views)
- **فلاتر البحث:** إضافة فلاتر في شاشة القراءات لإظهار "القراءات في الطابور" والقراءات التي بها "خطأ فوترة".
- **زر إعادة المحاولة:** في حال واجهت القراءة خطأ (مثل نقص إعدادات العقد)، يتمكن المستخدم من الدخول عليها، تعديل الخطأ، والضغط على زر "إعادة للطابور" (Requeue) لكي يلتقطها الـ Job في الدفعة القادمة.

## 4. إعدادات قابلة للتخصيص (System Parameters)
بدلاً من تثبيت الرقم 500 في الكود، يفضل استخدام إعدادات النظام `ir.config_parameter`:
```python
batch_size = int(self.env['ir.config_parameter'].sudo().get_param('utility.billing_batch_size', 500))
```
بحيث يمكن لمدير النظام رفع الرقم إلى 1000 أو تخفيضه إلى 200 مستقبلاً من خلال واجهة الإعدادات دون الحاجة لتعديل الكود البرمجي.
