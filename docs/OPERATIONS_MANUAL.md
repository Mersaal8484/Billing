# دليل التشغيل والتوثيق الفني الشامل لنظام Utility ERP

**الإصدار:** 16.0.2.3.0  
**نظام التشغيل المعتمد:** Odoo 16.0 Enterprise / Community  
**النطاق الوظيفي:** إدارة شركات توزيع الكهرباء والمياه (البيانات الأساسية، القراءات، الفوترة الآجلة، الدفع المسبق POS/STS، العمليات الميدانية، التكاملات الإلكترونية وبوابات الدفع).

---

## 1. نظرة عامة والمعمارية (Architecture & Modules)

يتكون نظام `utility_erp` من **6 موديولات متكاملة** تترابط بترتيب تثبيت محدد:

```
1. date_range (موديول Odoo قياسي للفترات)
   └── 2. utility_core (البيانات الأساسية والهيكل الجغرافي والإعدادات)
       ├── 3. utility_inventory (ربط العدادات بالمنتجات والأرقام التسلسلية)
       └── 4. utility_operations (العمليات الميدانية، أوامر الخدمة، واستبدال العدادات)
           └── 5. utility_billing (الفوترة الآجلة، القراءات، وبوابة الدفع الإلكتروني)
               └── 6. utility_prepaid (بيع الطاقة مسبقة الدفع STS ومحطات POS)
```

> [!NOTE]
> تم دمج موديول `utility_portal` بالكامل داخل `utility_billing` لتسهيل الصيانة وتقليل التبعيات التشغيلية.

---

## 2. دليل التشغيل للعمليات المالية والتحصيل

### 2.1 التحصيل الميداني واليدوي (Manual Field Collection)
تتم عمليات التحصيل اليدوي سواء من المكاتب أو عبر المحصلين الميدانيين وفق الضوابط التالية:
1. **يومية المتحصل الميداني (`collection_journal_id`)**:
   - ينشئ النظام لكل محصل ميداني/كاشير يومية نقدية شخصية تسمى `يومية تحصيل - [اسم الموظف]`.
   - عند ضغط زر **"تسجيل تحصيل"** على الفاتورة، يُوجَّه المبلغ تلقائياً إلى يومية المحصل الميداني الخاصة بالحساب الجاري للموظف.
2. **أنواع التحصيل اليدوي**:
   - **نقدي (`cash`)**: يُسجل المورد المالي مباشرة في صندوق المحصل الميداني.
   - **بنكي (`bank`)**: يُسجل كشيك أو تحويل بنكي ميداني.

### 2.2 التحصيل والدفع الإلكتروني (Electronic Payment Gateways)
يتكامل النظام مع بوابات الدفع الخارجية، المحافظ الإلكترونية (`Mobile Money`)، والخصم المباشر:
1. **مزودو التكامل (`utility.integration.provider`)**:
   - يتم تعريف المزود وتحديد اتجاه الدفع (`وارد inbound` / `صادر outbound` / `كلا الاتجاهين both`).
   - تحديد يوميات الدفع المخصصة للمزود (`inbound_journal_id` و `outbound_journal_id`).
   - تحديد أسلوب المصادقة (`Bearer Token`, `Basic Auth`, `API Key Header`, `HMAC`).
2. **دورة دفع الفواتير الإلكترونية**:
   - **إنشاء نية الدفع (`Payment Intent`)**: يرسل تطبيق الجوال طلب `/api/v1/utility/billing/payment_intent` فينشئ النظام معاملة `utility.payment.gateway.transaction` بحالة `pending`.
   - **تأكيد بوابة الدفع (`Webhook Callback`)**: تُرسل البوابة الإشعار إلى `/api/v1/utility/payment_gateway/webhook/<reference>` مع مرجع المزود التعديلي Token/HMAC.
   - **إنشاء وتأكيد سند الدفع آلياً**: يُنشئ النظام سند دفع `account.payment` مرتبط بالفاتورة بحالة `electronic` ويقوم بتأكيده وتسويته مع الفاتورة آلياً.

### 2.3 المدفوعات الصادرة والاسترداد (`outbound`)
يدعم النظام رد المبالغ والمستحقات للمشتركين (كالرصيد الزائد أو التعويضات):
- المعاملات ذات الاتجاه `outbound` تُنشئ سند دفع محاسبي بنوع `payment_type = 'outbound'` و `partner_type = 'customer'`.
- تُستخدم يومية الصرف الخاصة بالمزود أو اليومية البنكية المعتمدة.

---

## 3. دورة القراءة والفوترة الآجلة (Reading & Billing Cycle)

### 3.1 إدخال القراءات وتدقيقها
1. **القراءات اليدوية / تطبيق القارئ**:
   - يتم إدخال القراءة وتصوير العداد. تدخل القراءة بحالة `under_review` (تحت المراجعة).
   - بعد مراجعة الصورة والمطابقة من المشرف تتحول إلى `approved` (معتمدة).
2. **قراءات AMI العدادات الذكية**:
   - تصل عبر Webhook آلي إلى `/api/v1/utility/ami/reading_callback` وتُنشئ قراءة معتمدة فوراً.

### 3.2 إصدار الفواتير الدوري (Billing Cycle Execution)
1. الانتقال إلى قائمة **الفوترة ← دورات الفوترة (`utility.billing.cycle`)**.
2. اختيار الفترة والضغط على **"توليد الفواتير"**.
3. يقوم النظام بإنشاء مسودات أوامر البيع (`sale.order`) وتطبيق معادلات العقود والتعريفات، وتتحول حالة القراءة إلى `billed`.
4. يقوم محرك الأتمتة (`sale.workflow.process`) بتأكيد أوامر البيع وتوليد الفواتير المحاسبية وترحيلها تلقائياً.

---

## 4. المرجعية الفنية للـ REST APIs

جميع الواجهات البرمجية تستخدم التنسيق `application/json` وتطلب مصادقة `auth='user'` إلا في الـ Webhooks العامة (`auth='public'`).

### 4.1 الاستعلام عن رصيد الحساب والمديونية
```http
POST /api/v1/utility/billing/balance
Content-Type: application/json

{
  "customer_number": "ACC-100234"
}
```
**الاستجابة:**
```json
{
  "customer_number": "ACC-100234",
  "accounting_balance": 150.00,
  "debt": 450.50,
  "last_purchase_date": "2026-07-15"
}
```

### 4.2 إنشاء نية دفع / استرداد (Payment Intent)
```http
POST /api/v1/utility/billing/payment_intent
Content-Type: application/json

{
  "order_id": 1420,
  "amount": 200.00,
  "payment_direction": "inbound",
  "provider_id": 2
}
```
**الاستجابة:**
```json
{
  "transaction_id": 85,
  "reference": "PG/2026/00085",
  "payment_direction": "inbound",
  "state": "pending",
  "amount": 200.00
}
```

### 4.3 إشعار بوابة الدفع (Payment Webhook Callback)
```http
POST /api/v1/utility/payment_gateway/webhook/PG/2026/00085
Content-Type: application/json

{
  "token": "SECURE_ACCESS_TOKEN",
  "status": "success",
  "provider_reference": "BANK-TXN-99881122"
}
```

### 4.4 استقبال قراءات العدادات الذكية (AMI Reading Callback)
```http
POST /api/v1/utility/ami/reading_callback
Content-Type: application/json

{
  "secret": "AMI_WEBHOOK_SECRET",
  "meter_number": "MTR-88231",
  "reading_value": 45210.5
}
```

---

## 5. دليل الترقية والـ Migration

عند ترقية النظام أو التحديث إلى الإصدار `16.0.2.3.0`:

1. **تشغيل أمر الترقية من الطرفية**:
   ```bash
   odoo-bin -c odoo.conf -d <your_database> -u utility_billing --stop-after-init
   ```
2. **التحقق من سكريبت الترقية الآلي**:
   - يعمل سكريبت `pre-migrate.py` تلقائياً لنقل سجلات `ir.model.data` الخاصة بـ `utility.payment.gateway.transaction` من موديول `utility_portal` السابق إلى `utility_billing` لمنع فقدان البيانات أو يُصبح أي سجل ينيماً (Orphaned).
