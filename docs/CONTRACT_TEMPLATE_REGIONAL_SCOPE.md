# تحديد النطاق الجغرافي لقالب العقد (Contract Template Regional Scope)

يوضح هذا المستند التصميم البرمجي والمعماري المطور لتطبيق ميزة **تحديد النطاق الجغرافي لقالب العقد** (`utility.contract.template`) في نظام المؤسسة العامة للكهرباء (Utility ERP)، بحيث يدعم الفصل الكامل بين **المناطق الرئيسية** (`region_ids`) و**المناطق الفرعية** (`area_ids`).

---

## 1. الفكرة المعمارية المطورة (Architectural Concept)

لتحقيق أقصى درجات المرونة وسهولة الاستخدام للجهة المشغلة، سنفصل بين اختيار المناطق الرئيسية والمناطق الفرعية في قالب العقد كالتالي:

1. **في نموذج قالب العقد (`utility.contract.template`)**:
   * يتم تحديد حقل يحدد نطاق التغطية الجغرافية (`scope`).
   * حقل **المناطق الرئيسية المسموح بها** (`region_ids`) - لاختيار وتفويض مناطق كاملة.
   * حقل **المناطق الفرعية المسموح بها** (`area_ids`) - لاختيار وتفويض فروع محددة ومخصصة فقط.
2. **في عقد المشترك / حساب المشترك (`utility.customer`)**:
   * تتم فلترة قوالب العقود المتاحة للمشترك تلقائياً بناءً على موقعه التشغيلي (منطقته الرئيسية أو الفرعية).
   * يتم التحقق برمجياً من توافق موقع المشترك مع قوالب العقود المحددة.

---

## 2. هيكلة البيانات البرمجية (Data Model & Fields)

### أ. نموذج قالب العقد (`utility.contract.template`)

تُضاف الحقول التالية لتحديد وتخصيص النطاق الجغرافي:

| اسم الحقل | النوع | الوصف | الخصائص |
| :--- | :--- | :--- | :--- |
| `scope` | Selection | نطاق التغطية الجغرافية | `global` (عام) أو `restricted` (مخصص)، افتراضي: `global` |
| `region_ids` | Many2many | المناطق الرئيسية المسموح بها | علاقة مع `utility.region` مع فلترة النوع ليكون (`region`) فقط |
| `area_ids` | Many2many | المناطق الفرعية المسموح بها | علاقة مع `utility.region` مع فلترة النوع ليكون (`area`) فقط |

### ب. نموذج حساب المشترك (`utility.customer`)

يتم التحقق من تطابق أي من الموقعين (المنطقة الرئيسية أو الفرعية) للمشترك مع قوالب العقود المحددة.

---

## 3. مقترح التنفيذ البرمجي (Proposed Implementation)

### 1. بايثون (Python Backend)

#### نموذج قالب العقد (`utility_contract_template.py`)
```python
class UtilityContractTemplate(models.Model):
    _inherit = 'utility.contract.template'

    scope = fields.Selection([
        ('global', 'عام على جميع المناطق'),
        ('restricted', 'مخصص لمناطق محددة')
    ], string='نطاق التغطية الجغرافية', default='global', required=True)

    region_ids = fields.Many2many(
        'utility.region',
        'utility_contract_template_region_rel',
        'template_id',
        'region_id',
        string='المناطق الرئيسية المسموح بها',
        domain="[('type', '=', 'region')]",
        help="المناطق الرئيسية المسموح بها لهذا القالب"
    )

    area_ids = fields.Many2many(
        'utility.region',
        'utility_contract_template_area_rel',
        'template_id',
        'region_id',
        string='المناطق الفرعية المسموح بها',
        domain="[('type', '=', 'area')]",
        help="المناطق الفرعية/الفروع المسموح بها لهذا القالب"
    )

    @api.constrains('scope', 'region_ids', 'area_ids')
    def _check_scope_regions(self):
        for rec in self:
            if rec.scope == 'restricted' and not rec.region_ids and not rec.area_ids:
                raise ValidationError(_("يجب اختيار منطقة رئيسية أو منطقة فرعية واحدة على الأقل عند تحديد نطاق التغطية كمخصص!"))
```

#### نموذج حساب المشترك (`utility_customer.py`)
```python
class UtilityCustomer(models.Model):
    _inherit = 'utility.customer'

    # فلترة جغرافية ذكية لقوالب العقود
    contract_template_id = fields.Many2one(
        'utility.contract.template',
        string='نموذج العقد',
        domain="["
               "('subscriber_category_ids', '=', category_id), "
               "('subscriber_ids', '=', subscriber_id), "
               "'|', ('scope', '=', 'global'), "
               "'|', ('region_ids', '=', region_id), "
               "('area_ids', '=', area_id)"
               "]"
    )

    @api.constrains('contract_template_id', 'region_id', 'area_id')
    def _check_contract_region_compatibility(self):
        for rec in self:
            template = rec.contract_template_id
            if template and template.scope == 'restricted':
                allowed_region_ids = template.region_ids.ids
                allowed_area_ids = template.area_ids.ids
                
                customer_region_id = rec.region_id.id
                customer_area_id = rec.area_id.id
                
                is_region_allowed = customer_region_id in allowed_region_ids if customer_region_id else False
                is_area_allowed = customer_area_id in allowed_area_ids if customer_area_id else False
                
                # منع الحفظ إذا كان المشترك يتبع منطقة ومنطقة فرعية غير مغطاة في القالب المخصص
                if not (is_region_allowed or is_area_allowed):
                    raise ValidationError(
                        _("قالب العقد المختار '%s' مخصص لمناطق محددة ولا يدعم المنطقة أو المنطقة الفرعية لهذا المشترك.")
                        % template.name
                    )
```

#### ويزارد تسجيل المشتركين (`utility_customer_wizard.py`)
```python
class UtilityCustomerWizard(models.TransientModel):
    _inherit = 'utility.customer.wizard'

    contract_template_id = fields.Many2one(
        'utility.contract.template', 
        string='قالب العقد الافتراضي', 
        required=True,
        domain="["
               "('subscriber_category_ids', '=', category_id), "
               "('subscriber_ids', '=', subscriber_id), "
               "'|', ('scope', '=', 'global'), "
               "'|', ('region_ids', '=', utility_region_id), "
               "('area_ids', '=', utility_area_id)"
               "]"
    )

    @api.constrains('contract_template_id', 'utility_region_id', 'utility_area_id')
    def _check_wizard_contract_region_compatibility(self):
        for rec in self:
            template = rec.contract_template_id
            if template and template.scope == 'restricted':
                allowed_region_ids = template.region_ids.ids
                allowed_area_ids = template.area_ids.ids
                
                region_id = rec.utility_region_id.id
                area_id = rec.utility_area_id.id
                
                is_region_allowed = region_id in allowed_region_ids if region_id else False
                is_area_allowed = area_id in allowed_area_ids if area_id else False
                
                if not (is_region_allowed or is_area_allowed):
                    raise ValidationError(
                        _("قالب العقد الافتراضي المختار '%s' لا يدعم المنطقة أو المنطقة الفرعية المحددة في المعالج.")
                        % template.name
                    )
```

---

### 2. الواجهات (UI - XML Views)

#### شاشة قالب العقد (`utility_contract_template_views.xml`)
يتم عرض حقول النطاق الجغرافي ديناميكياً مع الفصل التام بين المناطق والمناطق الفرعية:
```xml
<field name="scope" widget="radio" options="{'horizontal': true}"/>
<field name="region_ids" widget="many2many_tags" placeholder="اختر المناطق الرئيسية المسموح بها..." 
       attrs="{'invisible': [('scope', '!=', 'restricted')], 'required': [('scope', '=', 'restricted')]}"/>
<field name="area_ids" widget="many2many_tags" placeholder="اختر المناطق الفرعية المسموح بها..." 
       attrs="{'invisible': [('scope', '!=', 'restricted')], 'required': [('scope', '=', 'restricted')]}"/>
```

---

## 4. التحقق والضمان البرمجي (QA & Testing)

1. **التحقق من الواجهات (UI Verification)**:
   * يظهر قالبا العقد العامان للجميع. القوالب المخصصة تظهر فقط لمن هم داخل المناطق والبلدان المحددة.
2. **التحقق البرمجي (Model Constrains)**:
   * تضمن قواعد التحقق سلامة البيانات والتحقق المتقاطع لمنع ثغرات إدخال البيانات غير المتوافقة.
