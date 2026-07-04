# شامل بيانات الـ ERP — كل ما يتم تحميله عند التثبيت

> آخر تحديث: يوليو 2026

---

## فهرس الملفات

| # | الملف | noupdate | عدد السجلات |
|---|-------|----------|-------------|
| 1 | `utility_core/data/utility_subscriber_data.xml` | ✅ 1 | 8 فئات + 8 مشتركين + 3 معادلات |
| 2 | `utility_core/data/utility_data.xml` | ✅ 1 | 4 أنواع عدادات + 5 حالات + 5 أنواع توصيل |
| 3 | `utility_core/data/utility_sequence.xml` | ✅ 1 | 3 تسلسلات رقمية |
| 4 | `utility_core/data/utility_user_role_data.xml` | ✅ 1 | 6 أدوار مستخدمين |
| 5 | `utility_core/data/utility_sample_data.xml` | ❌ 0 | شركة + منتجات + مناطق + قوالب + عملاء + عدادات |
| 6 | `utility_billing/data/utility_sequence.xml` | ✅ 1 | 4 تسلسلات رقمية |
| 7 | `utility_billing/data/utility_demo.xml` | ❌ 0 | 2 قراءة + 1 أمر بيع |
| 8 | `utility_billing/data/utility_cron.xml` | ✅ 1 | 1 مهمة مجدولة |
| 9 | `utility_billing/data/utility_cron_extras.xml` | ✅ 1 | 7 مهام مجدولة |
| 10 | `utility_billing/data/utility_cron_batch.xml` | ❌ 0 | 3 مهام + 1 تسلسل |
| 11 | `utility_billing/data/utility_billing_sample_data.xml` | ❌ 0 | أنواع دورات + دورات فوترة + قراءات + فواتير + مدفوعات + غرامات + ودائع + تسويات + إعفاءات |
| 12 | `utility_prepaid/data/utility_sequence.xml` | ✅ 1 | 5 تسلسلات رقمية |
| 13 | `utility_prepaid/data/utility_demo.xml` | ❌ 0 | شريك + حساب + عداد + قالب + وردية + توكن |
| 14 | `utility_operations/data/utility_sequence.xml` | ✅ 1 | 6 تسلسلات رقمية |
| 15 | `utility_operations/data/utility_demo.xml` | ❌ 0 | أمر خدمة + إنذار + حالة تلاعب + أمر عمل |
| 16 | `utility_inventory/data/utility_inventory_data.xml` | ✅ 1 | 2 موقع مخزني + 1 تصنيف منتج |
| 17 | `utility_portal/data/utility_portal_data.xml` | ✅ 1 | (فارغ) |
| 18 | `date_range/data/ir_cron_data.xml` | ✅ 1 | 1 مهمة مجدولة |

---

## 1. فئات المشتركين (`utility.subscriber.category`)

| المعرف | الاسم | الكود | الترتيب |
|--------|-------|-------|---------|
| `cat_public` | أهالي | `CAT_PUB` | 5 |
| `cat_large` | كبار مستهلكين | `CAT_LARGE` | 15 |
| `cat_government` | حكومي | `CAT_GOV` | 25 |

## 2. أنواع المشتركين (`utility.subscriber`)

| المعرف | الاسم | الكود | الفئة | مدعوم؟ |
|--------|-------|-------|-------|--------|
| `sub_category_public` | أهالي | `PUB` | CAT_PUB | نعم (100 وحدة، 100%) |
| `sub_category_large` | كبار مستهلكين | `LARGE` | CAT_LARGE | لا |
| `sub_category_government_new` | حكومي | `GOV_NEW` | CAT_GOV | لا |

## 3. معادلات الفوترة (`utility.formula`)

| المعرف | الاسم |
|--------|-------|
| `formula_fixed_fee` | رسوم اشتراك ثابت (0 إذا الاستهلاك 0) |
| `formula_consumption` | استهلاك كهرباء (`result = consumption`) |
| `formula_discount` | خصم استهلاك مدعوم (أول 100 kWh) |

## 4. أنواع العدادات (`utility.meter.type`)

| المعرف | الاسم | الكود | الطور |
|--------|-------|-------|-------|
| `meter_type_single_sts` | Single Phase STS | `SP_STS` | single |
| `meter_type_three_sts` | Three Phase STS | `TP_STS` | three |
| `meter_type_smart_single` | Smart Single Phase | `SMART_SP` | single |
| `meter_type_smart_three` | Smart Three Phase | `SMART_TP` | three |

## 5. حالات العدادات (`utility.meter.status`)

| المعرف | الاسم | الكود |
|--------|-------|-------|
| `meter_status_active` | Active | `ACTIVE` |
| `meter_status_inactive` | Inactive | `INACTIVE` |
| `meter_status_faulty` | Faulty | `FAULTY` |
| `meter_status_tampered` | Tampered | `TAMPERED` |
| `meter_status_decommissioned` | Decommissioned | `DECOMM` |

## 6. أنواع التوصيل (`utility.connection.type`)

| المعرف | الاسم | الكود | الجهد | الطور |
|--------|-------|-------|-------|-------|
| `connection_type_new` | New Connection | `NEW` | lv | single |
| `connection_type_residential` | Residential | `RES` | lv | single |
| `connection_type_commercial` | Commercial | `COM` | lv | three |
| `connection_type_industrial` | Industrial | `IND` | mv | three |
| `connection_type_agricultural` | Agricultural | `AGR` | lv | single |

## 7. أدوار المستخدمين (`utility.user.role`)

| المعرف | الاسم | الكود | المجموعة |
|--------|-------|-------|----------|
| `role_inspector` | مفتش ميداني (Inspector) | inspector | group_utility_field_inspector |
| `role_cashier` | أمين صندوق (Cashier) | cashier | group_utility_cashier |
| `role_collector` | متحصل ميداني (Collector) | collector | group_utility_collector |
| `role_supervisor` | مشرف (Supervisor) | supervisor | group_utility_supervisor |
| `role_technician` | فني (Technician) | technician | group_utility_technician |
| `role_manager` | مدير (Manager) | manager | group_utility_revenue_manager |

## 8. التسلسلات الرقمية (`ir.sequence`)

### utility_core

| المعرف | الاسم | الكود | البادئة | الطول |
|--------|-------|-------|---------|-------|
| `seq_utility_customer` | Utility Customer Number | `utility.customer` | `CUS/%(year)s/` | 6 |
| `seq_utility_meter` | Utility Meter Number | `utility.meter` | `MET/%(year)s/` | 6 |
| `seq_utility_connection` | Utility Connection Number | `utility.connection` | `CON/%(year)s/` | 6 |

### utility_billing

| المعرف | الاسم | الكود | البادئة |
|--------|-------|-------|---------|
| `seq_utility_reading` | Utility Reading | `utility.reading` | `RD/%(year)s/` |
| `seq_utility_writeoff` | Utility Writeoff | `utility.writeoff` | `WO/%(year)s/` |
| `seq_utility_deposit` | Utility Deposit | `utility.deposit` | `DEP/%(year)s/` |
| `seq_utility_collector_shift` | Utility Collector Shift | `utility.collector.shift` | `CS/%(year)s/` |
| `seq_utility_reading_batch` | Utility Reading Batch | `utility.reading.batch` | `BATCH-` |

### utility_prepaid

| المعرف | الاسم | الكود | البادئة |
|--------|-------|-------|---------|
| `seq_utility_token` | Utility Token | `utility.token` | `TKN/%(year)s/` |
| `seq_utility_transaction` | Utility Transaction | `utility.transaction` | `TXN/%(year)s/` |
| `seq_utility_adjustment` | Utility Adjustment | `utility.adjustment` | `ADJ/%(year)s/` |
| `seq_utility_reversal` | Utility Reversal | `utility.reversal` | `REV/%(year)s/` |
| `seq_utility_cashier_shift` | Utility Cashier Shift | `utility.cashier.shift` | `SFT/%(year)s/` |

### utility_operations

| المعرف | الاسم | الكود | البادئة |
|--------|-------|-------|---------|
| `seq_utility_service_order` | Utility Service Order | `utility.service.order` | `SO` |
| `seq_utility_installation` | Utility Installation | `utility.installation` | `INST` |
| `seq_utility_inspection` | Utility Inspection | `utility.inspection` | `INSP` |
| `seq_utility_tamper_case` | Utility Tamper Case | `utility.tamper.case` | `TC` |
| `seq_utility_alarm` | Utility Alarm | `utility.alarm` | `ALM` |
| `seq_utility_work_order` | Utility Work Order | `utility.work.order` | `WO` |

---

## 9. المناطق (`utility.region`)

| المعرف | الاسم | الكود | النوع | دورة الفوترة |
|--------|-------|-------|-------|--------------|
| `demo_region_1` | المنطقة الأولى | `REGION_1` | region | نصف شهري |
| `demo_region_2` | المنطقة الثانية | `REGION_2` | region | نصف شهري |
| `demo_region_3` | المنطقة الثالثة | `REGION_3` | region | نصف شهري |
| `demo_region_4` | المنطقة الرابعة | `REGION_4` | region | نصف شهري |
| `demo_region_hodeidah` | الحديدة | `REGION_HUD` | region | نصف شهري |

## 10. الموظفون (`utility.staff`)

| المعرف | الاسم | الكود | الدور |
|--------|-------|-------|-------|
| `demo_staff_inspector` | سالم السقاف (مفتش ميداني) | `EMP_INSP_YE01` | inspector |
| `demo_staff_cashier` | عبد الله الحروي (صراف الإيرادات) | `EMP_CASH_YE01` | cashier |
| `demo_staff_supervisor` | أحمد العولقي (مشرف هندسي) | `EMP_SUPER_YE01` | supervisor |

---

## 11. المنتجات (`product.product`)

| المعرف | الاسم | النوع | القائمة |
|--------|-------|-------|---------|
| `utility_product_kwh` | استهلاك كهرباء (kWh) | service | 350.00 |
| `utility_product_fixed_fee` | رسوم اشتراك العداد | service | 1,500.00 |
| `utility_product_service_charge` | رسوم خدمات وصيانة | service | 1,000.00 |
| `utility_product_discount` | خصم استهلاك مدعوم | service | -350.00 |

## 12. الحسابات واليوميات (`account.account`, `account.journal`)

### الحسابات

| المعرف | الاسم | الرمز | النوع |
|--------|-------|-------|-------|
| `demo_account_fine` | إيرادات الغرامات | 410001 | income |
| `demo_account_discount` | الخصومات والإعفاءات المسموح بها | 420001 | expense |
| `demo_account_deposit` | التأمينات والودائع | 210001 | liability_payable |
| `demo_account_settlement` | تسويات مالية | 410002 | income_other |

### اليوميات

| المعرف | الاسم | الكود | النوع |
|--------|-------|-------|-------|
| `demo_journal_writeoff` | يومية الإعفاءات والتسويات | `WRT` | general |
| `demo_journal_deposit` | يومية التأمينات | `DEP` | general |
| `demo_journal_settlement` | يومية التسويات العامة | `SETL` | general |

---

## 13. قوالب العقود (`utility.contract.template`)

### 13.1 أهالي — شهري (شرائح) `TMPL_PUB_M`
- **القالب**: `demo_tmpl_pub_monthly`
- **رسم الخدمة**: 1,500 | **الدورة**: شهري
- **الشرائح**:
  | الشريحة | من | إلى | السعر |
  |---------|----|-----|-------|
  | الأولى | 0 | 100 | 200 |
  | الثانية | 100 | 200 | 300 |
  | الثالثة | 200 | 500 | 400 |
  | الرابعة | 500+ | مفتوحة | 500 |

### 13.2 أهالي — نصف شهري (شرائح) `TMPL_PUB_BI`
- **القالب**: `demo_tmpl_pub_bimonthly`
- **رسم الخدمة**: 750 | **الدورة**: نصف شهري
- **الشرائح**:
  | الشريحة | من | إلى | السعر |
  |---------|----|-----|-------|
  | الأولى | 0 | 50 | 200 |
  | الثانية | 50 | 100 | 300 |
  | الثالثة | 100 | 250 | 400 |
  | الرابعة | 250+ | مفتوحة | 500 |

### 13.3 كبار مستهلكين — شهري (شرائح) `TMPL_LARGE_M`
- **القالب**: `demo_tmpl_large_monthly`
- **رسم الخدمة**: 4,000 | **الدورة**: شهري
- **الشرائح**:

  | من | إلى | السعر |
  |----|-----|-------|
  | 0 | 500 | 400 |
  | 500 | 1,000 | 500 |
  | 1,000 | 5,000 | 600 |
  | 5,000+ | مفتوحة | 700 |

### 13.4 كبار مستهلكين — نصف شهري (شرائح) `TMPL_LARGE_BI`
- **رسم الخدمة**: 2,000 | **الدورة**: نصف شهري

  | من | إلى | السعر |
  |----|-----|-------|
  | 0 | 250 | 400 |
  | 250 | 500 | 500 |
  | 500 | 2,500 | 600 |
  | 2,500+ | مفتوحة | 700 |

### 13.5 حكومي — شهري (شرائح) `TMPL_GOV_M`
- **رسم الخدمة**: 3,000 | **الدورة**: شهري

  | من | إلى | السعر |
  |----|-----|-------|
  | 0 | 500 | 350 |
  | 500 | 2,000 | 450 |
  | 2,000+ | مفتوحة | 550 |

### 13.6 حكومي — نصف شهري (شرائح) `TMPL_GOV_BI`
- **رسم الخدمة**: 1,500 | **الدورة**: نصف شهري

  | من | إلى | السعر |
  |----|-----|-------|
  | 0 | 250 | 350 |
  | 250 | 1,000 | 450 |
  | 1,000+ | مفتوحة | 550 |

---

---

## 14. دورات الفوترة (`date.range`)

### أنواع الدورات

| المعرف | الاسم | سنة مالية؟ |
|--------|-------|-----------|
| `demo_date_range_type_monthly` | دورة فوترة شهرية - اليمن | لا |
| `demo_date_range_type_biweekly` | دورة فوترة نصف شهرية | لا |
| `demo_fiscal_year_type` | سنة مالية | نعم |

### السنة المالية

| المعرف | الاسم | الفترة | الحالية؟ |
|--------|-------|--------|----------|
| `demo_fiscal_year_2026` | السنة المالية 2026 | 2026-01-01 → 2026-12-31 | نعم |

### دورات شهرية

| المعرف | الاسم | المنطقة | الحالية؟ |
|--------|-------|---------|----------|
| `demo_cycle_monthly_r1` | يوليو 2026 | REGION_1 | نعم |
| `demo_cycle_monthly_r2` | يوليو 2026 | REGION_2 | نعم |
| `demo_cycle_monthly_r3` | يوليو 2026 | REGION_3 | نعم |
| `demo_cycle_monthly_r4` | يوليو 2026 | REGION_4 | نعم |
| `demo_cycle_monthly_hud` | يوليو 2026 | REGION_HUD | نعم |

### دورات نصف شهرية — النصف الأول

| المعرف | المنطقة | الفترة | الحالية؟ |
|--------|---------|--------|----------|
| `demo_cycle_biweekly_r1_a` | REGION_1 | 1-15 يوليو 2026 | نعم |
| `demo_cycle_biweekly_r2_a` | REGION_2 | 1-15 يوليو 2026 | نعم |
| `demo_cycle_biweekly_r3_a` | REGION_3 | 1-15 يوليو 2026 | نعم |
| `demo_cycle_biweekly_r4_a` | REGION_4 | 1-15 يوليو 2026 | نعم |
| `demo_cycle_biweekly_hud_a` | REGION_HUD | 1-15 يوليو 2026 | نعم |

### دورات نصف شهرية — النصف الثاني

| المعرف | المنطقة | الفترة | الحالية؟ |
|--------|---------|--------|----------|
| `demo_cycle_biweekly_r1_b` | REGION_1 | 16-31 يوليو 2026 | لا |
| `demo_cycle_biweekly_r2_b` | REGION_2 | 16-31 يوليو 2026 | لا |
| `demo_cycle_biweekly_r3_b` | REGION_3 | 16-31 يوليو 2026 | لا |
| `demo_cycle_biweekly_r4_b` | REGION_4 | 16-31 يوليو 2026 | لا |
| `demo_cycle_biweekly_hud_b` | REGION_HUD | 16-31 يوليو 2026 | لا |

---



---

## 15. المهام المجدولة (`ir.cron`)

| المعرف | الاسم | الفاصل | الكود |
|--------|-------|--------|-------|
| `cron_generate_bills_daily` | Generate Bills Daily | 1 يوم | `date.range.cron_generate_bills_daily()` |
| `ir_cron_autocreate` | Auto-generate date ranges | 1 يوم | `date.range.type.autogenerate_ranges()` |
| `ir_cron_generate_recurring_invoices` | توليد الفواتير المتكررة للعقود | 1 ساعة | `utility.contract.template.cron_generate_recurring_invoices()` |
| `ir_cron_check_low_credit` | مراقبة وتنبيه الأرصدة المنخفضة | 30 دقيقة | `utility.customer.cron_check_low_credit()` |
| `ir_cron_update_overdue_orders` | تحديث حالة الفواتير المتأخرة | 1 يوم | `sale.order.cron_update_overdue_orders()` |
| `ir_cron_retry_auto_pay` | إعادة محاولة الدفع التلقائي | 30 دقيقة | `utility.customer.cron_retry_auto_pay()` |
| `ir_cron_batch_reading_invoicing` | الفوترة الجماعية للقراءات المعتمدة | 1 يوم | `utility.reading.action_generate_bills_batch()` |
| `ir_cron_calculate_late_penalties` | احتساب غرامات التأخير | 1 يوم | `utility.penalty.cron_calculate_late_penalties()` |
| `ir_cron_send_due_bill_reminders` | إرسال تذكير بالفواتير المستحقة | 1 يوم | `sale.order.cron_send_due_reminders()` |
| `ir_cron_generate_batch_bills` | Utility: Batch Generate Bills | 15 دقيقة | `utility.reading._cron_generate_bills()` |
| `ir_cron_process_staging_readings` | Utility: Process Uploaded Readings | 10 دقائق | `utility.reading.batch._cron_process_readings()` |
| `ir_cron_cleanup_batch_files` | Utility: Cleanup Old Batch Files | 1 يوم | `utility.reading.batch._cron_cleanup_old_batches()` |

---

## 16. بيانات المخزون (`stock.location`, `product.category`)

| المعرف | الاسم | النوع |
|--------|-------|-------|
| `stock_location_utility_customers` | مواقع المشتركين | customer |
| `stock_location_utility_repair` | ورشة الفحص والصيانة | internal |
| `product_category_meters` | العدادات الكهربائية | تصنيف منتج |

---

## 17. بيانات المبيعات المسبقة (Prepaid Demo)

| المعرف | النموذج | ملخص |
|--------|---------|------|
| `demo_customer_1` (prepaid) | `res.partner` | Abdullah Al-Saud |
| `demo_account_1` (prepaid) | `utility.customer` | ACC-2024-0001, رصيد 500 |
| `demo_meter_1` (prepaid) | `utility.meter` | MTR-R-2024-001 |
| `demo_contract_1` (prepaid) | `utility.contract.template` | Residential Standard Prepaid, 0.25/kWh |
| `demo_shift_1` (prepaid) | `utility.cashier.shift` | Demo Morning Shift, مقفلة |
| `demo_token_1` (prepaid) | `utility.token` | توكن 100 ريال = 400 kWh |

---

## 18. بيانات العمليات الميدانية (Operations Demo)

| المعرف | النموذج | الحالة |
|--------|---------|--------|
| `utility_service_order_demo_1` | `utility.service.order` | مسودة (أمر خدمة توصيل جديد) |
| `utility_alarm_demo_1` | `utility.alarm` | جديد (إنذار رصيد منخفض) |
| `utility_tamper_case_demo_1` | `utility.tamper.case` | مبلغ (تلاعب بالعداد) |
| `utility_work_order_demo_1` | `utility.work.order` | مسودة (أمر عمل تركيب) |

---

## 19. إعدادات الشركة (`res.company`)

تم تعيين الحسابات واليوميات والمنتجات الافتراضية على الشركة الرئيسية:

| الحقل | القيمة |
|-------|--------|
| `fine_account_id` | demo_account_fine (410001) |
| `discount_account_id` | demo_account_discount (420001) |
| `deposit_account_id` | demo_account_deposit (210001) |
| `settlement_account_id` | demo_account_settlement (410002) |
| `writeoff_journal_id` | demo_journal_writeoff (WRT) |
| `deposit_journal_id` | demo_journal_deposit (DEP) |
| `settlement_journal_id` | demo_journal_settlement (SETL) |
| `penalty_product_id` | utility_product_service_charge |
| `mu_allim_product_id` | utility_product_fixed_fee |
| `cleaning_product_id` | utility_product_service_charge |
| `local_fee_product_id` | utility_product_fixed_fee |
| `writeoff_account_id` | demo_account_discount (420001) |
| `collection_journal_id` | demo_journal_writeoff (WRT) |

---

## إجمالي السجلات

| القسم | العدد |
|-------|-------|
| فئات المشتركين | 3 |
| أنواع المشتركين | 3 |
| معادلات | 3 |
| أنواع العدادات | 4 |
| حالات العدادات | 5 |
| أنواع التوصيل | 5 |
| أدوار المستخدمين | 6 |
| تسلسلات رقمية | 18 |
| مناطق (region) | 5 |
| موظفون | 3 |
| منتجات | 4 |
| حسابات محاسبية | 4 |
| يوميات | 3 |
| قوالب عقود | 6 |
| أنواع دورات | 3 |
| دورات فوترة | 16 |
| مهام مجدولة | 12 |
| مواقع مخزنية | 2 |
| تصنيفات منتجات | 1 |
| بيانات مسبقة (prepaid) | 6 |
| بيانات عمليات | 4 |
| **المجموع** | **~100+ سجل** |
