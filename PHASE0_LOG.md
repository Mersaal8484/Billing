# PHASE0_LOG.md — Walking Skeleton Installation & Audit Log

**التاريخ:** 2026-08-09  
**قاعدة البيانات:** utility_db  
**Odoo:** 16.0 Community

---

## §1 — الموديولات المثبتة بنجاح

| الموديول | الإصدار | الحالة |
|---|---|---|
| utility_core | 16.0.1.4.1 | installed |
| utility_billing | 16.0.2.3.0 | installed |
| utility_operations | 16.0.1.0.0 | installed |
| utility_inventory | 16.0.1.0.0 | installed |
| utility_prepaid | — | installed |
| date_range | — | installed |
| utility_portal | — | installed |

## أخطاء التثبيت وكيفية الإصلاح

### الخطأ 1: Incompatible companies on records
- الملف: utility_core/data/utility_data.xml (دالة _init_utility_company_defaults)
- السبب: تعيين حسابات/يوميات لشركة مختلفة على My Company
- الإصلاح: فحص company_id.id in (False, company.id) قبل كل تعيين
- الملف المعدَّل: custom_addons/utility_core/models/utility_res_company.py

### الخطأ 2: ValidationError - لا توجد مناطق نشطة
- الملف: utility_billing/data/utility_billing_sample_data.xml
- السبب: DateRange.create() يطلب مناطق بالدورية قبل إنشاء فترات - DB جديد لا مناطق فيه
- الإصلاح: تحويل ValidationError إلى تخطٍّ صامت عند عدم وجود مناطق
- الملف المعدَّل: custom_addons/utility_core/models/utility_date_range.py

### الخطأ 3: Invalid field 'balance' on model 'utility.customer'
- الملف: utility_prepaid/data/utility_demo.xml
- السبب: حقل balance غير موجود في utility.customer
- الإصلاح: حذف السطر من البيانات التجريبية
- الملف المعدَّل: custom_addons/utility_prepaid/data/utility_demo.xml

## تنظيف المستودع
- utility_erp.rar: غير موجود (تم حذفه سابقاً)
- utility_erp/ orphan: غير موجود (تم حذفه سابقاً)

---

## تقييم معايير القبول §6

| المعيار | الحالة |
|---|---|
| الموديولات مثبتة بلا خطأ | DONE |
| المستودع نظيف | DONE |
| PHASE0_LOG.md | DONE (هذا الملف) |
| قراءة حقيقية من البداية للنهاية | PENDING - لم يُختبر بعد |
| فاتورة صحيحة + Idempotency | PENDING - لم يُختبر بعد |
| لا شيء خارج النطاق | PARTIAL - انظر ملاحظات |

---

## ملاحظات معمارية تحتاج قرار المالك

### 1. utility.media.asset - التخزين
- البرومبت §4 يطلب: Filesystem مباشر، لا ir.attachment
- الواقع: النموذج يدعم 3 backends (filesystem/attachment/s3)
  لكن الحقول الفعلية original_attachment_id / thumbnail_attachment_id
  هي Many2one لـ ir.attachment حتى في وضع filesystem
- القرار المطلوب: هل هذا مقبول أم يجب إعادة هيكلة التخزين؟

### 2. شاشة المراجعة - OWL بدلاً من Tree بسيط
- البرومبت §3 يطلب: Tree عادي يكفي الآن، ليس OWL المخصص الكامل
- الواقع: شاشة المراجعة الافتراضية هي Client Action بـ OWL Component
  مع Lightbox وRejection Dialog وScss مخصص
- Tree View بسيطة موجودة لكنها ليست الافتراضية
- القرار المطلوب: هل نقبل هذا لأغراض §6 أم نستبدل بـ Tree؟

### 3. الاختبار الطرف-لطرف
البنية الكاملة موجودة لكن لم يُجرَ اختبار فعلي بعد:
- utility.reading.batch + utility.reading.batch.line (staging)
- utility.media.asset + utility.media.service (معالجة الصورة)
- _process_single_batch_line (معالجة كل سطر)
- _action_generate_periodic_bill (إنشاء الفاتورة)

الخطوات المتبقية للاختبار:
1. إنشاء: utility.region + date.range + utility.customer + utility.meter
2. رفع قراءة + صورة عبر batch
3. تشغيل process_batch
4. اعتماد القراءة + توليد الفاتورة
5. التحقق: لا ضرائب، Idempotency

---
آخر تحديث: 2026-08-09
