# خطة: إضافة دعم "محول خاص مشترك" إلى `UtilityCustomerWizard`

> **الهدف:** تمكين المستخدم من إنشاء **محول خاص** (Transformer/Cell يدخل ضمن `utility.transformer` ويُسجَّل بـ `is_cell=True` + `is_private=True`) يكون في نفس الوقت **مشتركاً حقيقياً** يُفوتر وتُصدر له قراءات وفواتير. حالياً الـ wizard يدعم إنشاء `res.partner` + `utility.customer` + `utility.meter` فقط، لكنه لا ينشئ محولاً ولا يربط المشترك بمحول خاص.

---

## 1) الوضع الحالي (Baseline)

### 1.1) ما يفعله الـ Wizard اليوم
- `utility_core/wizards/utility_customer_wizard.py:65-123`:
  1. ينشئ `res.partner` (الاسم، الجوال، العنوان، المنطقة، الفئة، القطاع).
  2. ينشئ `utility.customer` ويربطه بـ `contract_template_id`.
  3. ينشئ `utility.meter` عند تفعيل `create_meter=True`.
  4. يفتح بطاقة المشترك.

### 1.2) ما يفتقده
- **لا ينشئ محول/خلية** — العمود `cell_id` على `utility.customer` يبقى فارغاً.
- **لا يوجد خيار "محول خاص"** — لا حقل `is_private_transformer` على الـ wizard، ولا ربط بالمحول.
- **لا ينشئ قراءات ابتدائية للمحول** — حتى لو وُجد محول، لا تُسجَّل قراءة "صفرية" ابتدائية لعداد الربط.
- **الـ meter** (عداد المشترك) ليس له `transformer_id` تلقائياً، بينما عدّاد الربط على المحول (`coupling_meter_id`) مفقود تماماً.

### 1.3) النماذج المتأثرة
| النموذج | الحقول الحالية | الاستخدام في الخطة |
|---|---|---|
| `utility.transformer` | `is_cell`, `is_private`, `private_account_id`, `coupling_meter_id`, `comparison_meter_id`, `cell_account_ids` | إنشاء صف جديد عند الطلب |
| `utility.meter` | `transformer_id`, `customer_id`, `payment_type` | يُربط بالمحول ويصبح نفسه عداد الربط |
| `utility.transformer.reading` | `transformer_id`, `meter_id`, `reading_type`, `state` | قراءة ابتدائية = 0 على العداد |
| `utility.customer` | `cell_id` (domain: `is_cell=True`) | يُربط بالمحول الخاص الجديد |
| `utility.customer_wizard` | لا شيء يخص المحول | إضافة 12 حقل + خطوة جديدة |

---

## 2) الرؤية المستهدفة (Target State)

### 2.1) سيناريوهان للاستخدام
1. **سيناريو A — محول خاص فقط** (المحول هو المشترك، بدون مشتركين آخرين): الـ wizard ينشئ محولاً `is_cell=True, is_private=True` ومشتركاً مرتبطاً به، وعدّادَين: عداد المشترك + عداد الربط.
2. **سيناريو B — مشترك على محول خاص قائم**: الـ wizard يكتشف المحول الموجود (عبر `transformer_code` أو البحث في `utility.transformer`) ويربط المشترك به. لا ينشئ محولاً جديداً.

### 2.2) بنية البيانات بعد الإنشاء
```
utility.transformer                # صف جديد (أو قائم)
   ├── is_cell = True
   ├── is_private = True
   ├── private_account_id → utility.customer (المشترك الجديد)
   ├── coupling_meter_id → utility.meter (نفسه عداد المشترك — انظر 2.3)
   ├── capacity, phase, manufacturer, voltage_primary/secondary
   └── zone_region_id, substation_id, feeder_id

utility.meter (عداد المشترك = عداد الربط)  # يُنشأ دائماً عند create_meter=True
   ├── customer_id = utility.customer
   ├── transformer_id = utility.transformer (المحول الخاص)
   └── payment_type = 'prepaid' | 'postpaid' | 'manual'

utility.customer                    # المشترك
   ├── cell_id = utility.transformer (المحول الخاص)
   ├── is_private_transformer = True (related)
   └── contract_template_id = ...

utility.transformer.reading         # قراءة ابتدائية للمحول
   ├── transformer_id, meter_id = customer_meter
   ├── reading_type = 'coupling'
   ├── reading_value = 0.0
   ├── previous_reading = 0.0
   └── state = 'confirmed'
```

---

### 2.3) قرار التصميم: عداد واحد يخدم المشترك والمحول

> **المبدأ:** في المحول الخاص (مشترك واحد أو مجموعة صغيرة)، لا حاجة لعدّادَيْن منفصلَيْن. عداد المشترك نفسه يُسجَّل كـ `coupling_meter_id` على المحول، فتصبح قراءة العداد هي **نفسها** قراءة المحول.

**الأثر على النماذج:**

| الحقل | القيمة | السبب |
|---|---|---|
| `utility.transformer.coupling_meter_id` | = عداد المشترك | العداد الفريد في المحول الخاص يخدم الغرضين |
| `utility.meter.transformer_id` | = المحول الخاص | ربط عكسي |
| `utility.meter.customer_id` | = المشترك | ربط العداد بالمشترك |

**الأثر على الفوترة (تصحيح هام جداً):**

- **يجب أن تبقى الفوترة معتمدة على `utility.reading` (قراءة المشترك العادية).**
- المشترك الذي يمتلك محولاً خاصاً هو بالنهاية مشترك عادي بالنسبة لدورة الفوترة (`utility.billing.cycle`). لا يجوز قراءة استهلاكه من `utility.transformer.reading` لأن ذلك سيفصل الفوترة إلى مسارين ويعقد النظام.
- إذا كان هناك حاجة تقنية لوجود القراءة في `utility.transformer.reading` (لأغراض تقارير الفاقد للمنطقة)، يجب مزامنتها برمجياً (Sync) من قراءة المشترك، وليس العكس.

**القيد:** في `utility.transformer`، `coupling_meter_id` و `comparison_meter_id` يبقيا حقلين منفصلين، لكن `comparison_meter_id` غير مستخدم في المحول الخاص. يُترك فارغاً.

---

## 3) المراحل

### المرحلة 0 — تجهيز
- إنشاء فرع: `git checkout -b feature/wizard-private-transformer-customer`.
- تشغيل `-u utility_core` على بيئة تطوير.

### المرحلة 1 — إضافة حقول إلى الـ Wizard

في `utility_core/wizards/utility_customer_wizard.py`:

```python
# قسم "المحول الخاص"
use_private_transformer = fields.Boolean(
    string='محول خاص (المحول للمشترك وحده)',
    default=False,
    help='عند التفعيل: ينشئ الـ wizard محولاً خاصاً جديداً في utility.transformer'
         ' ويربطه بالمشترك كخلية خاصة. عدّاد الربط يُنشأ تلقائياً.')

private_transformer_existing_id = fields.Many2one(
    'utility.transformer', string='محول خاص قائم',
    domain="[('is_cell', '=', True), ('is_private', '=', True), ('private_account_id', '=', False)]",
    help='إن وُجد محول خاص غير مرتبط بمشترك، يمكن اختياره بدلاً من إنشاء جديد.')

# حقول تعريف المحول الجديد
transformer_name = fields.Char(string='اسم المحول')
transformer_code = fields.Char(string='كود المحول', required=False)
transformer_capacity = fields.Float(string='السعة (kVA)')
transformer_phase = fields.Selection([
    ('single', 'أحادي'),
    ('three', 'ثلاثي'),
], string='طور المحول')
transformer_manufacturer = fields.Char(string='الشركة المصنعة للمحول')
transformer_serial = fields.Char(string='الرقم التسلسلي للمحول')
voltage_primary = fields.Float(string='الجهد الابتدائي (V)')
voltage_secondary = fields.Float(string='الجهد الثانوي (V)')
transformer_substation_id = fields.Many2one('utility.substation', string='المحطة الفرعية')
transformer_feeder_id = fields.Many2one('utility.feeder', string='المغذي')

# حقول عدّاد الربط (تم إلغاؤها لأن عداد المشترك سيعمل كعداد ربط تلقائياً ولا داعي لإدخال بياناته مرتين)
```

**سلوك الـ onchange الجديد:**

```python
@api.onchange('use_private_transformer')
def _onchange_use_private_transformer(self):
    """إظهار/إخفاء حقول المحول تلقائياً + اقتراح قيم افتراضية."""
    if self.use_private_transformer:
        # اقتراح اسم/كود افتراضي إن لم يدخلهما المستخدم
        if not self.transformer_name:
            self.transformer_name = f"محول خاص - {self.name or 'مشترك جديد'}"
        if not self.transformer_code:
            self.transformer_code = f"PRV-{self.national_id or 'NEW'}"

@api.onchange('transformer_feeder_id')
def _onchange_transformer_feeder_id(self):
    if self.transformer_feeder_id and self.transformer_feeder_id.zone_id:
        self.transformer_zone_id = self.transformer_feeder_id.zone_id
```

### المرحلة 2 — إضافة منطق الإنشاء في `action_create_customer`

```python
def action_create_customer(self):
    self.ensure_one()

    # 1. res.partner (كما هو)
    partner = self._create_partner()

    # 2. utility.customer (كما هو)
    customer = self._create_customer(partner)

    # 3. محول خاص (جديد أو قائم)
    transformer = False
    if self.use_private_transformer:
        transformer = self._get_or_create_private_transformer(customer)

    # 4. عداد المشترك (يُنشأ عند create_meter=True)
    meter = False
    if self.create_meter and self.meter_number:
        meter = self._create_customer_meter(customer, transformer)

    # 5. تعيين عداد المشترك كعداد ربط للمحول الخاص (عداد واحد يخدم الغرضين)
    if transformer and meter:
        transformer.write({'coupling_meter_id': meter.id})

    # لا حاجة لإنشاء قراءة ابتدائية في utility.transformer.reading هنا،
    # سيتم إدخال القراءات بشكل طبيعي عبر utility.reading للمشترك.

    return self._open_customer_form(customer)
```

مع الدوال المساعدة:

```python
def _get_or_create_private_transformer(self, customer):
    """إرجاع محول خاص قائم أو إنشاء جديد."""
    if self.private_transformer_existing_id:
        t = self.private_transformer_existing_id
        if t.coupling_meter_id:
            raise ValidationError(_('المحول الخاص المختار مرتبط بعدّاد ولم يُعيَّن بعداد آخر.'))
        t.write({'private_account_id': customer.id})
        return t

    if not self.transformer_code:
        raise ValidationError(_('يجب إدخال كود المحول الخاص.'))

    if self.env['utility.transformer'].search([('code', '=', self.transformer_code)], limit=1):
        raise ValidationError(_('كود المحول مستخدم بالفعل.'))

    return self.env['utility.transformer'].create({
        'name': self.transformer_name or f"محول خاص - {customer.partner_id.name}",
        'code': self.transformer_code,
        'is_cell': True,
        'is_private': True,
        'private_account_id': customer.id,
        'capacity': self.transformer_capacity,
        'phase': self.transformer_phase or self.phase,
        'manufacturer': self.transformer_manufacturer,
        'serial_number': self.transformer_serial,
        'voltage_primary': self.voltage_primary,
        'voltage_secondary': self.voltage_secondary,
        'substation_id': self.transformer_substation_id.id if self.transformer_substation_id else False,
        'feeder_id': self.transformer_feeder_id.id if self.transformer_feeder_id else False,
        'zone_region_id': self.transformer_zone_id.id if self.transformer_zone_id else False,
    })

def _create_customer_meter(self, customer, transformer=False):
    """إنشاء عداد المشترك، وربطه بالمحول الخاص عند وجوده (يكون نفسه عداد الربط)."""
    status_active = self.env['utility.meter.status'].search([('code', '=', 'ACTIVE')], limit=1)
    return self.env['utility.meter'].create({
        'meter_number': self.meter_number,
        'serial_number': self.serial_number or self.meter_number,
        'manufacturer': self.manufacturer,
        'meter_type_id': self.meter_type_id.id if self.meter_type_id else False,
        'status_id': status_active.id if status_active else False,
        'phase': self.phase,
        'customer_id': customer.id,
        'transformer_id': transformer.id if transformer else False,
        'payment_type': self.payment_type,
        'sts_key_revision': self.sts_key_revision if self.payment_type == 'prepaid' else False,
        'communication_type': self.communication_type if self.payment_type == 'postpaid' else False,
    })

# تم حذف دالة _create_initial_transformer_reading لأن قراءات المحول الخاص 
# ستتم إدارتها عبر قراءات المشترك العادية (utility.reading).```

### المرحلة 3 — ربط المحول بـ `utility.customer.cell_id`

في `_create_customer` يجب إضافة:

```python
if self.use_private_transformer:
    customer_vals['cell_id'] = transformer.id  # يُحدّد بعد _get_or_create
```

**الترتيب الصحيح** في `action_create_customer`:
1. partner
2. customer (بدون `cell_id` بعد)
3. meter
4. transformer (يحتاج customer.id للربط العكسي)
5. customer.write({'cell_id': transformer.id}) ← أو pass transformer.id من البداية

> **الحل الأبسط:** إنشاء transformer **قبل** customer، ثم استخدام `private_account_id` للربط العكسي.

الترتيب المُعدَّل:
```python
# 0. transformer (إن وُجد، قد يكون قائم)
transformer = False
if self.use_private_transformer:
    if not self.private_transformer_existing_id:
        transformer = self._create_transformer_skeleton()  # بدون private_account_id
    else:
        transformer = self.private_transformer_existing_id

# 1. partner
partner = self._create_partner()

# 2. customer
customer = self._create_customer(partner, cell_id=transformer and transformer.id)

# 3. ربط عكسي
if transformer:
    transformer.write({'private_account_id': customer.id})

# 4. إنشاء عداد المشترك (وهو نفسه عداد المحول)
meter = False
if self.create_meter and self.meter_number:
    meter = self._create_customer_meter(customer, transformer)

# 5. ربط عداد المشترك كعداد ربط للمحول (لإلغاء التكرار)
if transformer and meter:
    transformer.write({'coupling_meter_id': meter.id})
    self._create_initial_transformer_reading(coupling_meter)
```

### المرحلة 4 — تحديث الـ View

في `utility_core/views/utility_customer_wizard_views.xml`:

```xml
<group string="المحول الخاص (اختياري)"
       attrs="{'invisible': [('use_private_transformer', '=', False)]}">
    <field name="use_private_transformer"/>
    <field name="private_transformer_existing_id"
           attrs="{'invisible': [('use_private_transformer', '=', False)]}"/>
    <!-- حقول المحول الجديد (تظهر عند عدم اختيار محول قائم) -->
    <field name="transformer_name" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="transformer_code" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="transformer_capacity" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="transformer_phase" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="transformer_manufacturer" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="transformer_serial" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="voltage_primary" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="voltage_secondary" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="transformer_substation_id" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <field name="transformer_feeder_id" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}"/>
    <!-- ملاحظة: عداد الربط = عداد المشترك، لا حاجة لحقل منفصل -->
    <div class="text-muted" attrs="{'invisible': [('private_transformer_existing_id', '!=', False)]}">
        <p>عداد المشترك (الذي سيدخل في الخطوة التالية) سيُسجَّل تلقائياً كعداد ربط للمحول الخاص.</p>
    </div>
</group>
```

> **ملاحظة:** يجب إضافة التبويب **بعد** التبويب الحالي "اختياري: عداد" (ليس داخله)، مع `attrs={'invisible': [('use_private_transformer', '=', False)]}` على مستوى الـ group.

### المرحلة 5 — التحقق من صحة البيانات (Validations)

داخل `action_create_customer`:

```python
# 1. تطابق كود المحول
if self.use_private_transformer and self.private_transformer_existing_id:
    if self.private_transformer_existing_id.private_account_id:
        raise ValidationError(_('المحول الخاص المختار مرتبط بمشترك آخر بالفعل.'))

# 2. تطابق طور المحول مع طور العدّاد
if self.use_private_transformer and self.create_meter:
    if self.transformer_phase and self.phase and self.transformer_phase != self.phase:
        raise ValidationError(_('طور المحول يجب أن يطابق طور العداد.'))

# 3. تطابق الفئة (الجهد) إن كانت متوفرة
# يمكن إضافة تحقق voltage_primary/secondary
```

### المرحلة 6 — فوترة وقراءات المحول (الجزء الثاني من المتطلب)

> المتطلب الكامل يذكر: "يتم فوترته واصدار فواتير و قراءات لمحول ايضا".

#### 6.1) قراءات المحول
- `utility.transformer.reading` يُنشأ تلقائياً عند بدء الاستخدام (قراءة 0 على عداد المشترك، المرحلة 2.5).
- لاحقاً يُسجَّل قراءات شهرية عبر قائمة `utility.transformer.reading` المعتادة.
- **مطلوب:** زر ذكي على `utility.transformer` form لفتح القراءات المرتبطة.

#### 6.2) فوترة المحول
الفاتورة تذهب للمشترك (صاحب المحول الخاص) عبر `_prepare_sale_order_data` (الموجود حالياً في `utility_billing/models/utility_recurring_invoice.py:5-58`).

مصدر القراءة للمحول الخاص: **`utility.transformer.reading`** (وليس `utility.reading`)، لأن العداد نفسه عداد المشترك/المحول ولا يوجد `utility.reading` مرتبط.

#### 6.3) تعديل `cron_generate_recurring_invoices`

```python
def cron_generate_recurring_invoices(self):
    # المسار 1: مشتركين عاديين (قراءة utility.reading، كما هو)
    accounts = self.env['utility.customer'].search([
        ('contract_state', '=', 'active'),
        ('contract_template_id', '!=', False),
        ('cell_id', '=', False),  # استبعاد المحولات الخاصة
    ])
    for account in accounts:
        reading = self.env['utility.reading'].search([
            ('account_id', '=', account.id),
            ('state', '=', 'approved'),
        ], order='reading_date desc', limit=1)
        if not reading:
            continue
        order = self.env['sale.order'].create(
            account.contract_template_id._prepare_sale_order_data(account, reading))
        order._calculate_amounts()
        reading.state = 'billed'
        # ... كما هو

    # المسار 2: محولات خاصة (قراءة utility.transformer.reading، جديد)
    transformers = self.env['utility.transformer'].search([
        ('is_private', '=', True),
        ('private_account_id', '!=', False),
        ('private_account_id.contract_state', '=', 'active'),
    ])
    for t in transformers:
        account = t.private_account_id
        t_reading = self.env['utility.transformer.reading'].search([
            ('transformer_id', '=', t.id),
            ('reading_type', '=', 'coupling'),
            ('state', '=', 'confirmed'),
            ('id', 'not in', self.env['sale.order'].search([
                ('reading_id', '!=', False),
            ]).mapped('reading_id').ids),  # لم تُفوتر بعد
        ], order='reading_date desc', limit=1)
        if not t_reading:
            continue
        reading_proxy = self._transformer_reading_to_proxy(t_reading, account)
        order = self.env['sale.order'].create(
            account.contract_template_id._prepare_sale_order_data(account, reading_proxy))
        order._calculate_amounts()
        # لا تغيّر حالة t_reading — ابقها 'confirmed' (دورة الفوترة لا تأثر على قراءة المحول)
        # أو أضف حقل bill_state على reading إن لزم
```

مع دالة مساعدة:

```python
def _transformer_reading_to_proxy(self, t_reading, account):
    """تحويل utility.transformer.reading إلى كائن يحاكي utility.reading
    ليتم قبوله في _prepare_sale_order_data.
    """
    Reading = self.env['utility.reading']
    return Reading.new({
        'account_id': account.id,
        'previous_reading': t_reading.previous_reading,
        'reading_value': t_reading.reading_value,
        'reading_date': t_reading.reading_date,
        'previous_reading_date': t_reading.previous_reading_date,
        'consumption': t_reading.consumption,
    })
```

> **ملاحظة:** `Reading.new()` ينشئ record في الذاكرة (Transient) ولا يحفظ في DB. هذا يكفي لأن `_prepare_sale_order_data` يقرأ الحقول فقط ولا يحفظ الـ reading.

#### 6.4) زر ذكي على `utility.transformer`
في `utility_core/views/utility_transformer_views.xml`:

```xml
<button name="action_view_coupling_readings" type="object"
        string="قراءات الربط" class="oe_stat_button" icon="fa-tasks">
    <field name="coupling_reading_count" widget="statinfo" string="قراءة"/>
</button>
<button name="action_view_bills" type="object"
        string="الفواتير" class="oe_stat_button" icon="fa-file-text-o">
    <field name="bill_count" widget="statinfo" string="فاتورة"/>
</button>
```

مع الدوال المقابلة في `utility_transformer.py`:
```python
coupling_reading_count = fields.Integer(compute='_compute_coupling_reading_count')
bill_count = fields.Integer(compute='_compute_bill_count')

def _compute_coupling_reading_count(self):
    for r in self:
        r.coupling_reading_count = self.env['utility.transformer.reading'].search_count([
            ('transformer_id', '=', r.id),
            ('reading_type', '=', 'coupling'),
        ])

def _compute_bill_count(self):
    SaleOrder = self.env.get('sale.order')
    for r in self:
        if r.private_account_id and SaleOrder:
            r.bill_count = SaleOrder.search_count([
                ('customer_id', '=', r.private_account_id.id),
            ])
        else:
            r.bill_count = 0

def action_view_coupling_readings(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'name': _('قراءات الربط'),
        'res_model': 'utility.transformer.reading',
        'domain': [('transformer_id', '=', self.id),
                   ('reading_type', '=', 'coupling')],
        'view_mode': 'tree,form',
    }

def action_view_bills(self):
    self.ensure_one()
    if not self.private_account_id:
        return
    return {
        'type': 'ir.actions.act_window',
        'name': _('فواتير المحول'),
        'res_model': 'sale.order',
        'domain': [('customer_id', '=', self.private_account_id.id)],
        'view_mode': 'tree,form',
    }
```

### المرحلة 7 — اختبارات

| # | السيناريو | النتيجة المتوقعة |
|---|---|---|
| 1 | wizard مع `use_private_transformer=True` وكل الحقول | إنشاء partner + customer + meter + transformer + coupling_meter + initial_reading |
| 2 | `transformer_code` مكرر | `ValidationError` |
| 3 | `private_transformer_existing_id` مرتبط بمشترك آخر | `ValidationError` |
| 4 | `transformer_phase != phase` (طور مختلف) | `ValidationError` |
| 5 | `use_private_transformer=False` | السلوك القديم (لا محول، لا عداد ربط) |
| 6 | `private_transformer_existing_id` يُختار (قائم وغير مرتبط) | `transformer.write({'private_account_id': customer.id})` + customer.cell_id = transformer.id |
| 7 | تشغيل `cron_generate_recurring_invoices` على محول خاص بقراءة confirmed | إنشاء sale.order على `private_account_id` |
| 8 | فتح `utility.transformer` form لمحول خاص | ظهور زر "قراءات الربط" + "الفواتير" بعدد صحيح |
| 9 | حساب الفاتورة على المحول (`_calculate_amounts`) | مطابق لقالب العقد (block/flat/local_fee/discount) |
| 10 | `is_private_transformer` على بطاقة المشترك | True (related) |
| 11 | `transformer.coupling_meter_id == meter.id` (نفس العداد) | ✓ |
| 12 | `meter.transformer_id == transformer.id` (ربط عكسي) | ✓ |

### المرحلة 8 — تحديث الوثائق

- `AGENTS.md`: إضافة سطر عن "المحول الخاص المشترك" في قسم "Transformer/cell hierarchy".
- `MERGE_TARIFF_INTO_CONTRACT_TEMPLATE.md`: ربط القسم 8.11.7 (سيناريوهات الاختبار) بالفاتورة الصادرة عن محول خاص.

---

## 4) خريطة الملفات

| الملف | التعديل |
|---|---|
| `utility_core/wizards/utility_customer_wizard.py` | +12 حقل (بدون `coupling_meter_*`)، +4 دوال، تعديل `action_create_customer` |
| `utility_core/views/utility_customer_wizard_views.xml` | group جديد للمحول الخاص |
| `utility_core/models/utility_transformer.py` | +2 compute (counts) +2 دالة (action_view_*) |
| `utility_core/views/utility_transformer_views.xml` | +2 smart button |
| `utility_billing/models/utility_recurring_invoice.py` | +1 مسار (محولات خاصة) في `cron_generate_recurring_invoices` + دالة `_transformer_reading_to_proxy` |
| `utility_core/security/ir.model.access.csv` | لا تغيير (النماذج موجودة) |
| `utility_core/data/utility_sample_data.xml` | اختياري: عينة demo لمحول خاص |

---

## 5) المخاطر والتخفيف

| المخاطرة | الاحتمال | الأثر | التخفيف |
|---|---|---|---|
| عداد الربط يُنشأ بدون رقم تسلسلي فعلي | متوسط | متوسط | جعل `coupling_meter_serial` اختياري لكن تحذير |
| قراءات ابتدائية = 0 قد تتعارض مع قراءة سابقة | منخفض | منخفض | `_sql_constraints` على `unique(meter_id, reading_date)` موجودة في النموذج |
| فاتورة المحول تختلف عن فاتورة المشترك (مكرر) | متوسط | عالي | شرط `customer_id == private_account_id` فقط، تعطيل قراءة العدّاد المشترك للمحول الخاص |
| `cell_id` على `utility.customer` يتطلب `is_cell=True` | منخفض | متوسط | التحقق قبل الربط |
| `domain="[('is_cell', '=', True)]"` على `cell_id` يمنع المحولات العادية | منخفض | منخفض | wizard ينشئ `is_cell=True, is_private=True`، فلا تعارض |

---

## 6) معايير القبول (Definition of Done)

- [ ] حقل `use_private_transformer` يظهر في الـ wizard.
- [ ] تفعيله يُظهر group كامل لحقول المحول (بدون `coupling_meter_*` لأن العداد واحد).
- [ ] `_onchange_use_private_transformer` يقترح اسم/كود افتراضي.
- [ ] `_onchange_transformer_feeder_id` يحدّث `transformer_zone_id` تلقائياً.
- [ ] `action_create_customer` ينشئ: partner + customer + transformer (عند الطلب) + meter + ربط العداد بالمحول كـ coupling_meter + قراءة ابتدائية = 0.
- [ ] عداد المشترك نفسه = عداد الربط (`transformer.coupling_meter_id == meter.id`).
- [ ] `utility.customer.cell_id = transformer.id` و `transformer.private_account_id = customer.id`.
- [ ] التحقق من كود المحول المكرر.
- [ ] التحقق من طور المحول = طور العدّاد.
- [ ] زر "محول خاص قائم" يكتشف المحولات المتاحة ويمنع اختيار المرتبط بعداد.
- [ ] `cron_generate_recurring_invoices` يصدر فاتورة لمحول خاص من قراءة `utility.transformer.reading` (ليس `utility.reading`).
- [ ] زر "قراءات الربط" يظهر على `utility.transformer` ويعمل.
- [ ] زر "الفواتير" يظهر على `utility.transformer` ويعمل.
- [ ] فاتورة المحول تستخدم قالب العقد `private_account_id.contract_template_id`.
- [ ] جميع الفحوصات النحوية (`py_compile`) تنجح.
- [ ] جميع الفحوصات XML تنجح.

---

## 7) تقدير الجهد

| المرحلة | النقاط |
|---|---|
| 0: تجهيز | 0.5 |
| 1: حقول Wizard | 1 |
| 2-3: منطق الإنشاء + الترتيب | 2.5 |
| 4: تحديث الـ View | 0.5 |
| 5: التحققات | 1 |
| 6: فوترة المحول + أزرار ذكية | 4 |
| 7: اختبارات يدوية | 2 |
| 8: توثيق | 0.5 |
| **المجموع** | **12 SP** |

> تعادل تقريباً **1–1.5 أسبوع** لمطوّر واحد.

---

## 8) أسئلة يجب حسمها قبل البدء

1. **عداد الربط = عداد المشترك. هل يُفقد تمييز `reading_type` على `utility.transformer.reading`؟**
   - (أ) لا، القراءة تُسجَّل دائماً بـ `reading_type='coupling'` لأنها على مستوى المحول.
   - (ب) نعم، نضيف `reading_type='subscriber'` ونستخدمه.
   - **المقترح:** (أ) — لأن العداد فعلاً عداد ربط (المحول كله مشترك واحد).
2. **هل يُسمح للمحول الخاص أن يكون له `distribution_percentage < 100`؟**
   - (أ) لا، دائماً 100% (المقترح: نعم، آمن، لأن المشترك يأخذ كل الطاقة).
   - (ب) نعم، قابل للتعديل لاحقاً.
3. **عند وجود محول خاص قائم: هل يُسمح باختيار مشترك آخر له؟**
   - (أ) لا، خطأ إن كان `private_account_id` مضبوطاً (المقترح: نعم، فالـ wizard يتحقق ويمنع التعارض).
   - (ب) نعم، يُعدَّل `private_account_id` ويُفقد الربط بالسابق.
4. **هل الـ `substation_id` و`feeder_id` إلزاميان؟**
   - (أ) اختياريان (المقترح: نعم، اختياريان، فبعض المحولات الخاصة صغيرة ولا تنتمي لشبكة رسمية).
5. **الفاتورة الشهرية: تُنشأ متى؟**
   - (أ) عند تشغيل `cron_generate_recurring_invoices` فقط.
   - (ب) زر يدوي على بطاقة المحول لتوليد فاتورة فورية.
   - **المقترح:** (أ) أولاً، (ب) كتحسين لاحق.
