# خطة تكامل construction_execution مع أنظمة Odoo — حالة التنفيذ

## ✅ 1. Project (project.project) — مُنفذ

| الحالة | الخطوة | الموديل/الملف |
|---|---|---|
| ✅ | `project_project_id` في `construction.project` | `models/construction_project.py` |
| ✅ | `construction_project_id` في `project.project` | `models/project_project_inherit.py` |
| ✅ | `boq_item_id` في `project.task` | `models/project_project_inherit.py` |
| ✅ | زر "إنشاء حساب تحليلي" | `models/construction_project.py` |
| ✅ | زر "إنشاء مشروع Odoo" مع إنشاء الحساب التحليلي تلقائيًا | `models/construction_project.py` |
| ✅ | زر "إنشاء مهام من بنود BOQ" | `models/construction_project.py` |
| ✅ | إنشاء الحساب التحليلي تلقائيًا عند إنشاء المشروع | `models/construction_project.py:create()` |
| ✅ | إنشاء مشروع Odoo تلقائيًا عند تغيير المرحلة إلى `execution` | `models/construction_project.py:write()` |
| ✅ | عرض `construction_project_id` في واجهة `project.project` | `views/project_project_inherit_views.xml` |
| ✅ | عرض `construction_project_id` و `boq_item_id` في `project.task` | `views/project_project_inherit_views.xml` |

## ✅ 2. المبيعات (sale.order) — مُنفذ

| الحالة | الخطوة | الموديل/الملف |
|---|---|---|
| ✅ | `construction_project_id` في `sale.order` | `models/sale_order_inherit.py` |
| ✅ | `construction_boq_id` في `sale.order` | `models/sale_order_inherit.py` |
| ✅ | `construction_ipc_id` في `sale.order` | `models/sale_order_inherit.py` |
| ✅ | `construction_boq_item_id` في `sale.order.line` | `models/sale_order_inherit.py` |
| ✅ | `construction_ipc_line_id` في `sale.order.line` | `models/sale_order_inherit.py` |
| ✅ | `construction_progress_line_id` في `sale.order.line` | `models/sale_order_inherit.py` |
| ✅ | زر "إنشاء أمر بيع" في BOQ | `models/construction_boq.py` |
| ✅ | زر "إنشاء أمر بيع" في IPC | `models/construction_ipc.py` |
| ✅ | `sale_order_ids` في BOQ | `models/construction_boq.py` |
| ✅ | `sale_order_id` + `sale_order_line_ids` في IPC | `models/construction_ipc.py` |
| ✅ | تحسين `action_create_invoice`: بند لكل IPC line + حساب تحليلي | `models/construction_ipc.py` |
| ✅ | عرض الحقول في `sale.order` + `sale.order.line` | `views/sale_order_inherit_views.xml` |

## ✅ 3. Timesheet / الحسابات التحليلية (account.analytic.line) — مُنفذ

| الحالة | الخطوة | الموديل/الملف |
|---|---|---|
| ✅ | `construction_project_id` في `account.analytic.line` | `models/account_analytic_line_inherit.py` |
| ✅ | `construction_boq_item_id` في `account.analytic.line` | `models/account_analytic_line_inherit.py` |
| ✅ | `cost_type` في `account.analytic.line` | `models/account_analytic_line_inherit.py` |
| ✅ | `timesheet_line_ids` (One2many) في `construction.project` | `models/construction_project.py` |
| ✅ | `total_hours_spent` + `total_timesheet_cost` في `construction.project` | `models/construction_project.py` |
| ✅ | عرض ساعات العمل في صفحة Integration من نموذج المشروع | `views/construction_project_views.xml` |

## ✅ 4. المشتريات (purchase.order) — مُنفذ

| الحالة | الخطوة | الموديل/الملف |
|---|---|---|
| ✅ | `construction_project_id` في `purchase.order` | `models/purchase_order_inherit.py` |
| ✅ | `construction_material_request_id` في `purchase.order` | `models/purchase_order_inherit.py` |
| ✅ | `construction_material_request_line_id` في `purchase.order.line` | `models/purchase_order_inherit.py` |
| ✅ | `construction_boq_item_id` في `purchase.order.line` | `models/purchase_order_inherit.py` |
| ✅ | `construction_cost_entry_id` في `purchase.order.line` | `models/purchase_order_inherit.py` |
| ✅ | تحسين `action_create_purchase_order`: ربط MR line + BOQ item | `models/construction_material_request.py` |
| ✅ | تحسين `_compute_purchase_orders`: استخدام `construction_material_request_id` | `models/construction_material_request.py` |
| ✅ | أتمتة: تأكيد PO ← تحديث MR إلى `ordered` | `models/purchase_order_inherit.py:button_confirm()` |
| ✅ | عرض الحقول في `purchase.order` + `purchase.order.line` | `views/purchase_order_inherit_views.xml` |

## ✅ 5. المخازن (stock.picking / stock.move) — مُنفذ

| الحالة | الخطوة | الموديل/الملف |
|---|---|---|
| ✅ | `construction_project_id` في `stock.picking` | `models/stock_picking_inherit.py` |
| ✅ | `construction_material_issue_id` في `stock.picking` | `models/stock_picking_inherit.py` |
| ✅ | `construction_material_return_id` في `stock.picking` | `models/stock_picking_inherit.py` |
| ✅ | `construction_material_issue_line_id` في `stock.move` | `models/stock_picking_inherit.py` |
| ✅ | `construction_material_return_line_id` في `stock.move` | `models/stock_picking_inherit.py` |
| ✅ | `construction_boq_item_id` في `stock.move` | `models/stock_picking_inherit.py` |
| ✅ | تحسين `action_create_stock_picking`: ربط issue line + BOQ item | `models/construction_material_issue.py` |
| ✅ | إنشاء cost entries تلقائيًا عند صرف المواد | `models/construction_material_issue.py:_create_cost_entries_from_issue()` |
| ✅ | `action_create_stock_return_picking()` في `material.return` | `models/construction_material_return.py` |
| ✅ | `boq_item_id` في return line | `models/construction_material_return.py` |
| ✅ | عرض `picking_id` + `action_create_stock_return_picking` في واجهة المرتجعات | `views/construction_material_views.xml` |
| ✅ | عرض الحقول في `stock.picking` | `views/stock_picking_inherit_views.xml` |

## ❌ 6. CRM (crm.lead) — لم يُنفذ بعد

| الحالة | الخطوة |
|---|---|
| ❌ | إضافة `crm_lead_id` إلى `construction.project` |
| ❌ | زر "تحويل إلى مشروع إنشاءات" في `crm.lead` |
| ❌ | إظهار العقود وBOQs في نموذج الفرصة |

## ✅ 7. تحسينات البنية التحتية المشتركة — مُنفذ

| الحالة | الخطوة |
|---|---|
| ✅ | `analytic_account_id` في `construction.project` (Many2one -> `account.analytic.account`) |
| ✅ | إنشاء analytic account تلقائياً مع كل `construction.project` جديد |
| ✅ | `construction_project_id` (Many2one -> `construction.project`) في كل النماذج الموروثة |
| ✅ | ربط `project.task` بـ `boq_item_id` لتتبع التقدم على مستوى البند |
| ✅ | `sale_order_line_ids` + `purchase_order_line_ids` في `construction.boq.item` |

## ملخص التغييرات

| الملفات الجديدة | الملفات المعدلة |
|---|---|
| `models/project_project_inherit.py` | `models/construction_project.py` |
| `models/sale_order_inherit.py` | `models/construction_boq.py` |
| `models/purchase_order_inherit.py` | `models/construction_boq_item.py` |
| `models/stock_picking_inherit.py` | `models/construction_ipc.py` |
| `models/account_analytic_line_inherit.py` | `models/construction_material_request.py` |
| `views/project_project_inherit_views.xml` | `models/construction_material_issue.py` |
| `views/sale_order_inherit_views.xml` | `models/construction_material_return.py` |
| `views/purchase_order_inherit_views.xml` | `views/construction_project_views.xml` |
| `views/stock_picking_inherit_views.xml` | `views/construction_boq_views.xml` |
| | `views/construction_ipc_views.xml` |
| | `views/construction_material_views.xml` |
| | `__manifest__.py` |
| | `models/__init__.py` |
| | `integration_plan.md` |
