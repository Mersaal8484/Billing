# سير العمل المتكامل — دورة حياة مشروع المقاولات

## من عميل متوقع (CRM) ← ٤٢٪ إنجاز ← محاسبة

```
المدة: ٣ أشهر (فبراير → مايو ٢٠٢٦)
قيمة العقد: ١٨,٥٠٠,٠٠٠ ريال
نسبة الإنجاز: ٤٢٪
```

---

## 🧭 خريطة التدفق والتواريخ والأثر

```
   CRM ──(1)──▶ Project ──(2)──▶ BOQ ──(3)──▶ SO ──(4)──▶ Budget ──(5)──▶ crossovered.budget
                                │
                                ├──▶ Tasks (17 مهمة)
                                │
                                └──(6)──▶ MR ──▶ PO (المشتريات)
                                │
                           (7)──▶ Progress (٤٢٪) ──(8)──▶ Variation
                                │
                           (9)──▶ IPC ──▶ Invoice (فاتورة)
                                │
                      (10)──▶ Cost Entry ──▶ Cost Control (cron)
                      (11)──▶ Forecast + Cashflow
                      (12)──▶ Analytic Lines
                      (13)──▶ Dashboard
```

---

## ① عميل متوقع ← مشروع مقاولات

| الحقل | القيمة |
|---|---|
| **التاريخ** | ٠١ فبراير ٢٠٢٦ |
| **الاسم** | مشروع إنشاء مجمع سكني - SBC 2026 |
| **العميل** | شركة القدية للاستثمار |
| **الإيراد المتوقع** | ١٨,٥٠٠,٠٠٠ ريال |
| **المنطقة** | الرياض، حي المغرزات |

```
crm.lead ── action_create_construction_project() ──▶ construction.project (PRJ-00008)
                                                            │
                  config: auto_create_analytic = True ──────┤
                                                            │
                                                            ▼
                                              account.analytic.account
                                              "[PRJ-00008] مشروع إنشاء..."

                  config: auto_create_project = True ──────▶ project.project
                                                            "[PRJ-00008] ..."

```

**الأثر**: تم إنشاء الحساب التحليلي ومشروع Odoo تلقائياً.

---

## ② الموارد

| # | الاسم | النوع | وحدة | التكلفة |
|---|---|---|---|---|
| 1 | اسمنت بورتلاندي | مادة | طن | ٤٤٠ |
| 2 | حديد تسليح ١٦مم | مادة | طن | ٢,٩٠٠ |
| 3 | خرسانة جاهزة ٣٠٠ كجم/م٣ | مادة | م³ | ٣٨٠ |
| 4 | بلوك خرساني مجوف ٢٠سم | مادة | وحدة | ٣.٥٠ |
| 5 | عامل بناء ماهر | عمالة | ساعة | ٢٨ |
| 6 | خلاطة خرسانة | معدات | ساعة | ٢٠٠ |

---

## ③ مقايسة الكميات (BOQ)

| التاريخ | ٠١ فبراير ٢٠٢٦ |
|---|---|
| **BOQ** | BOQ-2026-001 |
| **الحالة** | Draft ← Submitted ← **Approved** |

### القسم ①: أعمال الخرسانة (C)

| الكود | البند | الكمية | السعر | الإجمالي |
|---|---|---|---|---|
| C.01 | حفر وردم للأساسات | ١,٢٠٠ م³ | ٥٥ | ٦٦,٠٠٠ |
| C.02 | خرسانة عادية نظافة | ٢٠٠ م³ | ٣٢٠ | ٦٤,٠٠٠ |
| C.03 | خرسانة مسلحة للأساسات ٣٠٠ كجم/م³ | ٩٠٠ م³ | ٥٢٠ | ٤٦٨,٠٠٠ |
| C.04 | خرسانة مسلحة للأعمدة ٣٥٠ كجم/م³ | ٦٥٠ م³ | ٥٨٠ | ٣٧٧,٠٠٠ |
| C.05 | خرسانة مسلحة للأسقف ٣٥٠ كجم/م³ | ٥٥٠ م³ | ٥٩٠ | ٣٢٤,٥٠٠ |
| C.06 | حديد تسليح عالي المقاومة | ٢٨٠ طن | ٣,٢٠٠ | ٨٩٦,٠٠٠ |

### القسم ②: أعمال البناء (M)

| الكود | البند | الكمية | السعر | الإجمالي |
|---|---|---|---|---|
| M.01 | بلوك خرساني ٢٠ سم خارجي | ٣,٢٠٠ م² | ٩٥ | ٣٠٤,٠٠٠ |
| M.02 | بلوك خرساني ١٥ سم داخلي | ٢,٥٠٠ م² | ٧٥ | ١٨٧,٥٠٠ |

### القسم ③: أعمال التشطيب (F)

| الكود | البند | الكمية | السعر | الإجمالي |
|---|---|---|---|---|
| F.01-F.09 | محارة، دهان، سيراميك، أبواب، نوافذ، مطابخ | متنوع | ٣٠-١٨,٠٠٠ | ٢,٢٧١,٠٠٠ |

```
action_approve()
  │
  ├──▶ BOQ state = approved
  │
  └──▶ config: auto_create_tasks = True
         │
         └──▶ action_create_tasks_from_boq()
                │
                └──▶ 17 project.task (مهمة في Odoo)
```

**الأثر**: ١٧ مهمة أوتوماتيكياً في مشروع Odoo (مهمة لكل بند BOQ).

---

## ④ أمر البيع (Sale Order)

| الحقل | القيمة |
|---|---|
| **التاريخ** | ٠١ فبراير ٢٠٢٦ |
| **أمر البيع** | S00009 |
| **القيمة** | ٤,٥٩٠,٥٠٠ ريال |
| **البنود** | ١٧ |
| **الحالة** | Draft ← **Sale** (confirmed) |

```
BOQ (approved)
  │
  └──▶ action_create_sale_order()
         │
         ├──▶ يبحث عن/ينشئ منتج خدمي (Construction Works)
         ├──▶ ينشئ sale.order مع ١٧ بند
         │
         └──▶ action_confirm()
                │
                └──▶ sale.order.state = sale
```

**الرّبط**: `sale_order.construction_boq_id` ← BOQ ، `sale_order.construction_project_id` ← Project

**الأثر المحاسبي**: لا يوجد أثر محاسبي مباشر (أمر بيع غير مفوتر)، لكنه يوثق الالتزام التعاقدي.

---

## ⑤ الميزانية ← Accounting Budget Bridge

| الحقل | القيمة |
|---|---|
| **التاريخ** | ٠١ فبراير ٢٠٢٦ |
| **الميزانية** | الميزانية المعتمدة |
| **النوع** | Original |
| **الإجمالي** | ١٤,٩٥٠,٠٠٠ ريال |
| **الاحتياطي** | ٣٪ (٤٤٨,٥٠٠ ريال) |

### بنود الميزانية القياسية

| البند (Cost Code) | المبلغ | budget_post_id (account.budget.post) |
|---|---|---|
| موازنة تكاليف المواد (MAT) | ٦,٥٠٠,٠٠٠ | #27 - MAT |
| موازنة الأجور والعمالة (LAB) | ٢,٨٠٠,٠٠٠ | #28 - LAB |
| موازنة المعدات (EQP) | ١,٢٠٠,٠٠٠ | #29 - EQP |
| موازنة مصاريف الموقع (SIT) | ٩٥٠,٠٠٠ | #30 - SIT |
| موازنة مقاولي الباطن (SUB) | ٣,٥٠٠,٠٠٠ | #31 - SUB |

```
construction.budget (approved)
  │
  └──▶ action_create_crossovered_budget()
         │
         ├──▶ يحصل على الحساب التحليلي للمشروع
         ├──▶ لكل بند budget line:
         │      ├──▶ _get_or_create_budget_post(line)
         │      │      ├──▶ line.budget_post_id موجود؟ → استخدمه
         │      │      └──▶ لا؟ → ابحث/أنشئ account.budget.post
         │      │              ثم line.budget_post_id = bpost.id
         │      │
         │      └──▶ أنشئ crossovered.budget.line
         │             ├── general_budget_id ← budget_post
         │             ├── analytic_account_id ← حساب المشروع التحليلي
         │             └── planned_amount ← line.amount
         │
         └──▶ crossovered.budget (5 بنود)
```

**الرّبط**: `construction.budget.line` ↔ `account.budget.post` (ثنائي الاتجاه)
- `budget_post_id` (Many2one على construction.budget.line)
- `construction_budget_line_ids` (One2many على account.budget.post)

**الأثر المحاسبي**: إنشاء ميزانية محاسبية في `crossovered.budget` مرتبطة ببنود الموازنة عبر `account.budget.post`.

---

## ⑥ طلب شراء ← أمر شراء (MR → PO)

| الحقل | القيمة |
|---|---|
| **تاريخ الطلب** | ٠٥ فبراير ٢٠٢٦ |
| **تاريخ الاحتياج** | ٢٠ فبراير ٢٠٢٦ |
| **MR** | طلب شراء مواد المرحلة الأولى |
| **البنود** | ١٠٠ طن حديد (٢٩٠,٠٠٠) + ٥٠٠ م³ خرسانة (١٩٠,٠٠٠) |
| **أمر الشراء** | P00007 |
| **قيمة PO** | ٤٨٠,٠٠٠ ريال |
| **الحالة** | approved ← **purchase** (confirmed) |

```
MR (approved)
  │
  └──▶ action_create_purchase_order()
         │
         ├──▶ يرشح lines حيث product_id موجود والكمية > 0
         ├──▶ ينشئ purchase.order
         │      └── order_line: product_id, qty, uom, price_unit
         │
         └──▶ MR.state = ordered
                │
                └──▶ button_confirm()
                       └──▶ PO.state = purchase
```

**الرّبط**: `purchase_order.construction_material_request_id` ← MR
`purchase_order_line.construction_boq_item_id` ← BOQ Item

**الأثر المحاسبي**: إنشاء أمر شراء مؤكد ينتظر الاستلام والفواتير.

---

## ⑦ حصر الأعمال (Progress) — ٤٢٪

| الحقل | القيمة |
|---|---|
| **تاريخ الحصر** | ٣٠ أبريل ٢٠٢٦ |
| **الفترة** | شهرية (فبراير ← أبريل) |
| **العمالة في الموقع** | ٣٥ عامل |
| **المعدات** | ٦ معدة |
| **نسبة التنفيذ** | ٤٢.٠٪ |

### بنود الحصر

| الكود | البند | الإجمالي | المنفذ | % |
|---|---|---|---|---|
| C.01 | حفر وردم | ١,٢٠٠ م³ | **٩٠٠ م³** | ٧٥٪ |
| C.03 | خرسانة أساسات | ٩٠٠ م³ | **٥٠٠ م³** | ٥٦٪ |
| C.04 | خرسانة أعمدة | ٦٥٠ م³ | **٢٠٠ م³** | ٣١٪ |
| C.06 | حديد تسليح | ٢٨٠ طن | **١٢٠ طن** | ٤٣٪ |
| M.01 | بلوك خارجي | ٣,٢٠٠ م² | **٨٠٠ م²** | ٢٥٪ |

```
progress.line
  │
  ├── boq_item_id ← بند BOQ
  ├── total_quantity ← الكمية الإجمالية (من BOQ)
  ├── previous_quantity ← 0 (أول حصر)
  ├── current_quantity ← الكمية المنفذة هذا الشهر
  │
  └── executed_percent = (total_executed / total_quantity) × 100
```

---

## ⑧ أمر التغيير (Variation)

| الحقل | القيمة |
|---|---|
| **التاريخ** | ١٥ مارس ٢٠٢٦ |
| **النوع** | استشاري (Consultant) |
| **السبب** | متطلبات سلامة إنشائية |
| **الأولوية** | عالية |
| **صافي التغيير** | +٥٤,٠٠٠ ريال |

### تفاصيل التغيير

| البند | التغيير | الأصلي | المعدّل |
|---|---|---|---|
| C.03 خرسانة أساسات | تغيير سعر (rate) | ٥٢٠ ريال/م³ | ٥٨٠ ريال/م³ |

```
variation.line
  │
  ├── original_quantity ↔ revised_quantity
  ├── original_rate ↔ revised_rate
  │
  └── net_change = (revised - original) لكل بند
```

**الأثر**: زيادة في قيمة العقد +٥٤,٠٠٠ ريال.

---

## ⑨ IPC ← فاتورة عميل

| الحقل | القيمة |
|---|---|
| **التاريخ** | ٠٥ مايو ٢٠٢٦ |
| **الفترة** | ٠١ فبراير ← ٣٠ أبريل ٢٠٢٦ |
| **رقم IPC** | ١ |
| **الحالة** | Certified |
| **نسبة الحجز** | ٥٪ |

### تفاصيل IPC

| البند | الأعمال السابقة | الحالي | الكمية التراكمية | السعر | الإجمالي |
|---|---|---|---|---|---|
| C.01 | ٠ | ٩٠٠ | ٩٠٠ | ٥٥ | ٤٩,٥٠٠ |
| C.03 | ٠ | ٥٠٠ | ٥٠٠ | ٥٨٠ | ٢٩٠,٠٠٠ |
| C.04 | ٠ | ٢٠٠ | ٢٠٠ | ٥٨٠ | ١١٦,٠٠٠ |
| C.06 | ٠ | ١٢٠ | ١٢٠ | ٣,٢٠٠ | ٣٨٤,٠٠٠ |
| M.01 | ٠ | ٨٠٠ | ٨٠٠ | ٩٥ | ٧٦,٠٠٠ |

| البيان | المبلغ |
|---|---|
| إجمالي الأعمال | ٩١٥,٥٠٠ |
| حجز ٥٪ | (٤٥,٧٧٥) |
| **الصافي** | **٨٦٩,٧٢٥** |

### إنشاء الفاتورة

```
IPC (certified)
  │
  └──▶ action_create_invoice()
         │
         ├─── _get_income_account() → يبحث عن أول حساب دخل
         ├─── ينشئ account.move (out_invoice)
         │      ├── invoice_line_ids: name, qty, price_unit, account_id
         │      └── move_type = 'out_invoice'
         │
         └─── IPC.invoice_id = invoice.id
                │
                └─── action_post()
                       └── invoice.state = posted
```

**الفاتورة**: مستخلص رقم (4) — مجمع فلل — مرحلة الهيكل (١,٠٥٢,٨٢٥ ريال)

**الرّبط**: `sale_order_line.construction_ipc_line_id` ← IPC Line

**الأثر المحاسبي**: فاتورة عميل مرحلة (posted) تزيد في حساب العملاء (المدين) وحساب الإيراد (الدائن).

---

## ⑩ إدخالات التكاليف ← الرقابة على التكاليف

| # | التاريخ | البيان | البند | المبلغ |
|---|---|---|---|---|
| ١ | ٢٠ فبراير | فاتورة حديد تسليح | C.06 (حديد) | ٢٩٠,٠٠٠ |
| ٢ | ٠٥ مارس | فاتورة خرسانة جاهزة | C.03 (خرسانة أساسات) | ١٩٠,٠٠٠ |
| ٣ | ٠١ مارس | تكلفة حفر وردم | C.01 (حفر) | ٤٩,٥٠٠ |
| ٤ | ١٠ أبريل | فاتورة بلوك | M.01 (بلوك خارجي) | ٢,٨٠٠ |

```
cost.entry (إدخال يدوي)
  │
  └──▶ cron_update_costs() (مهمة مجدولة يومياً)
         │
         ├── يقرأ: × جميع cost entries للمشروع
         │         × purchase.order (المواد المشتراة)
         │         × timesheet (ساعات العمل)
         │         × material issue (صرف المخازن)
         │
         └──▶ ينشئ/يحدث cost.control records (١٧ سجل)
                │
                └── project_id + boq_item_id + resource_id → planned vs actual
```

**الأثر**: ١٧ سجل رقابة تكاليف تغطي كل بنود المشروع بالمقارنة بين المخطط والفعلي.

---

## ⑪ التوقعات والتدفقات النقدية

### التوقعات (Forecast)

| التاريخ | النوع | المخطط | التوقع | الفعلي |
|---|---|---|---|---|
| ٣٠ يونيو ٢٠٢٦ | تكلفة | ٤,٢٠٠,٠٠٠ | ٤,٤٠٠,٠٠٠ | ٥٣٢,٣٠٠ |
| ٣١ ديسمبر ٢٠٢٦ | تكلفة | ٦,٥٠٠,٠٠٠ | ٦,٨٠٠,٠٠٠ | — |
| ٣١ مارس ٢٠٢٧ | تكلفة | ٧,٥٠٠,٠٠٠ | ٧,٨٠٠,٠٠٠ | — |

### التدفقات النقدية (Cashflow)

| التاريخ | النوع | الفئة | المتوقع | الفعلي | تم الاستلام؟ |
|---|---|---|---|---|---|
| ١٥ مايو ٢٠٢٦ | إيراد | دفعة عميل | ٦٢٥,٠٠٠ | ٦٢٥,٠٠٠ | لا |
| ١٥ مايو ٢٠٢٦ | مصروف | مواد | ٤٥٠,٠٠٠ | ٤٨٢,٣٠٠ | — |
| ١٥ يونيو ٢٠٢٦ | مصروف | عمالة | ٢٨٠,٠٠٠ | — | — |
| ١٥ أغسطس ٢٠٢٦ | إيراد | دفعة عميل | ١,٢٠٠,٠٠٠ | — | — |
| ١٥ أغسطس ٢٠٢٦ | مصروف | مقاولي باطن | ٦٠٠,٠٠٠ | — | — |

---

## ⑫ بنود تحليلية (Timesheets)

| التاريخ | البيان | ساعات | المبلغ | البند |
|---|---|---|---|---|
| — | صرف حديد للموقع | ٨ | -٢٩٠,٠٠٠ | C.06 |
| — | صب خرسانة أساسات | ٤٠ | -١٩٠,٠٠٠ | C.03 |

```
account.analytic.line
  │
  ├── project_id ← project.project (مشروع Odoo)
  ├── account_id ← analytic account
  ├── employee_id ← موظف
  ├── unit_amount ← ساعات
  ├── amount ← المبلغ
  │
  └── construction_project_id ← construction.project
      construction_boq_item_id ← BOQ Item
      cost_type ← 'material'
```

---

## ⑬ لوحة المعلومات (Dashboard)

```
env['construction.dashboard'].init()
  │
  └──▶ CREATE OR REPLACE VIEW construction_dashboard AS (
         │
         ├── project_id, date, contract_amount
         ├── executed_value ← SUM(ipc.total_approved_amount)
         ├── remaining_value ← contract - executed
         ├── budget_cost ← SUM(budget.grand_total)
         ├── actual_cost ← SUM(cost_entry.amount)
         └── progress_percent ← project.progress_percent
       )
```

---

## 📊 جدول تلخيصي للتسلسل والتواريخ

| # | الخطوة | التاريخ | الحالة | المبلغ (ريال) |
|---|---|---|---|---|
| ① | CRM → مشروع | ٠١ فبراير | Execution | — |
| ② | الموارد | ٠١ فبراير | نشط | — |
| ③ | BOQ | ٠١ فبراير | **Approved** | — |
| ④ | أمر بيع | ٠١ فبراير | **Sale** | ٤,٥٩٠,٥٠٠ |
| ⑤ | الميزانية | ٠١ فبراير | **Approved** | ١٤,٩٥٠,٠٠٠ |
| ⑥ | MR → PO | ٠٥ فبراير ← ٢٠ فبراير | **Purchase** | ٤٨٠,٠٠٠ |
| ⑦ | حصر الأعمال | ٣٠ أبريل | **Approved** | ٤٢٪ إنجاز |
| ⑧ | أمر تغيير | ١٥ مارس | **Approved** | +٥٤,٠٠٠ |
| ⑨ | IPC → فاتورة | ٠٥ مايو | **Certified / Posted** | ٨٦٩,٧٢٥ |
| ⑩ | تكاليف | ٢٠ فبراير ← ١٠ أبريل | مسجلة | ٥٣٢,٣٠٠ |
| ⑪ | توقعات + تدفقات | ٣٠ يونيو ← ١٥ أغسطس | متوقعة | ١٥,٣٥٠,٠٠٠ |
| ⑫ | بنود تحليلية | فوري | مرحلة | ٤٨ ساعة |
| ⑬ | Dashboard | فوري | مُحدَّث | ٤٢٪ إنجاز |

---

## 🔗 مصفوفة الربط بين الكيانات

```
crm.lead ─────────────────────────────▶ construction.project
                                            │
            ┌───────────────────────────────┼───────────────────────────────┐
            │                               │                               │
            ▼                               ▼                               ▼
   account.analytic.account         project.project              sale.order (BOQ)
            │                               │                               │
            ▼                               ▼                               ▼
   crossovered.budget              project.task (×17)            account.move (Invoice)
            │                                                               │
            ▼                                                               ▼
   account.budget.post ◀── budget_post_id ──▶ construction.budget.line   analytic lines
                                                    │
            ┌───────────────────────────────────────┼───────────────────────────────┐
            │                                       │                               │
            ▼                                       ▼                               ▼
   purchase.order ◀── MR ──▶ construction.project   construction.progress ←─── construction.progress.line
            │                                               │
            ▼                                               ▼
   cost.entry ──▶ cost.control                        construction.ipc ◀─── ipc.line
                                                               │
                                                               ▼
                                                         account.move (out_invoice)
```

---

## 💡 ملاحظات التنفيذ

| الميزة | أين تطبق؟ | الملخص |
|---|---|---|
| **Auto-create analytic** | `project.py` write() | عند تعيين `project_stage` → ينشئ analytic account |
| **Auto-create Odoo project** | `project.py` write() | عند تعيين `project_stage` إلى "awarded/execution" |
| **Auto-create tasks** | `boq.py` action_approve() | ١٧ مهمة من BOQ عند الموافقة |
| **Budget → crossovered** | `budget.py` action_create_crossovered_budget() | زر "Push to Accounting" في واجهة الميزانية |
| **MR → PO** | `material_request.py` action_create_purchase_order() | زر "Create Purchase Order" |
| **IPC → Invoice** | `ipc.py` action_create_invoice() | زر "Create Invoice" ينشئ فاتورة عميل |
| **Cost control cron** | `cost_control.py` cron_update_costs() | يومياً: يجمع من entries + مشتريات + timesheets |
| **Dashboard SQL view** | `dashboard.py` init() | CREATE OR REPLACE VIEW بعد كل تغيير |
| **Budget Post link** | `budget.py` + `budget_post_inherit.py` | budget_post_id على line + inverse على account.budget.post |
