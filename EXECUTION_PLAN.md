# خطة التنفيذ التفصيلية - Utility ERP Development Plan

---

## 🔴 2. دورة قراءة العداد الكاملة (Reading → Review → Approve → Bill)

### الهدف
تدفق كامل لقراءة العداد: تصوير العداد ← دخول المراجعة ← موافقة ← إنشاء الفاتورة تلقائياً.

### التدفق الحالي (خطأ)
```
draft → validated → billed → error
```
لا توجد صور، ولا مراجعة، ولا موافقة.

### التدفق الجديد (صحيح)
```
draft → under_review → approved → billed → error
         ↑ (رفض) ↓
           draft
```

### التنفيذ - 5 مراحل

#### المرحلة 1: تعديل `utility.reading` - إضافة الصور وحالة المراجعة

**الملف:** `utility_billing/models/utility_reading.py` (استبدال كامل)

```python
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReading(models.Model):
    _name = 'utility.reading'
    _description = 'Utility Meter Reading'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reading_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    reading_id = fields.Char('Reading ID', default=lambda self: _('New'), readonly=True)
    
    # --- العداد والحساب ---
    meter_id = fields.Many2one('utility.meter', 'Meter', required=True, index=True)
    account_id = fields.Many2one('utility.account', 'Account', related='meter_id.account_id', store=True, index=True)
    customer_id = fields.Many2one('utility.customer', 'Customer', related='meter_id.customer_id', store=True)
    
    # --- القراءة ---
    reading_date = fields.Datetime('Reading Date', default=fields.Datetime.now, required=True)
    reading_value = fields.Float('Reading Value', required=True)
    consumption = fields.Float('Consumption', compute='_compute_consumption', store=True)
    reading_type = fields.Selection([
        ('manual', 'يدوي'),
        ('estimated', 'تقديري'),
        ('ami', 'AMI'),
    ], string='Reading Type', default='manual')
    is_estimated = fields.Boolean('تقديرية', default=False)
    
    # --- صور العداد ---
    meter_image = fields.Binary('صورة العداد', attachment=True,
        help='الصورة الملتقطة للعداد وقت القراءة')
    meter_image_secondary = fields.Binary('صورة إضافية', attachment=True)
    image_state = fields.Selection([
        ('clear', 'واضحة'),
        ('not_clear', 'غير واضحة'),
        ('not_same', 'لا تطابق العداد'),
        ('none', 'بدون صورة'),
        ('replace', 'عداد مركب حديثاً'),
        ('loss_read', 'قراءة مفقودة'),
    ], string='حالة الصورة', default='none',
        help='حالة فحص الصورة من قبل المراجع')
    
    # --- المراجعة ---
    reviewer_id = fields.Many2one('res.users', 'المراجع',
        readonly=True, tracking=True)
    review_date = fields.Datetime('تاريخ المراجعة', readonly=True)
    review_notes = fields.Text('ملاحظات المراجعة')
    rejection_reason = fields.Text('سبب الرفض')
    
    # --- القراءة السابقة (للمقارنة) ---
    previous_reading = fields.Float('القراءة السابقة')
    previous_reading_date = fields.Datetime('تاريخ القراءة السابقة')
    
    # --- تحليل الاستهلاك (للمساعدة في المراجعة) ---
    consumption_difference = fields.Float('فرق الاستهلاك',
        compute='_compute_consumption_analysis', store=True)
    consumption_diff_percentage = fields.Float('نسبة الفرق %',
        compute='_compute_consumption_analysis', store=True)
    consumption_alert = fields.Selection([
        ('normal', 'طبيعي'),
        ('high', 'مرتفع'),
        ('negative', 'سلبي'),
        ('zero', 'صفر'),
    ], compute='_compute_consumption_analysis', store=True, string='حالة الاستهلاك')
    
    # --- الحالة (التدفق الجديد) ---
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('under_review', 'قيد المراجعة'),
        ('approved', 'معتمدة'),
        ('billed', 'مفوترة'),
        ('error', 'خطأ'),
    ], string='الحالة', default='draft', tracking=True)
    
    remarks = fields.Text('ملاحظات')
    reading_source = fields.Char('مصدر القراءة')

    _sql_constraints = [
        ('unique_meter_reading_date',
         'unique(meter_id, reading_date)',
         'يوجد قراءة لنفس العداد في نفس التاريخ!'),
    ]

    # =======================
    #  الحقول المحسوبة
    # =======================

    @api.depends('reading_value', 'previous_reading')
    def _compute_consumption(self):
        for r in self:
            r.consumption = r.reading_value - r.previous_reading if r.previous_reading else 0.0

    @api.depends('consumption', 'meter_id')
    def _compute_consumption_analysis(self):
        for r in self:
            if r.consumption <= 0:
                r.consumption_alert = 'zero' if r.consumption == 0 else 'negative'
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                continue
            
            # مقارنة مع آخر قراءة معتمدة
            last_approved = self.search([
                ('meter_id', '=', r.meter_id.id),
                ('state', '=', 'approved'),
                ('id', '!=', r.id),
            ], order='reading_date desc', limit=1)
            
            if last_approved and last_approved.consumption > 0:
                diff = r.consumption - last_approved.consumption
                r.consumption_difference = diff
                r.consumption_diff_percentage = (diff / last_approved.consumption) * 100
                r.consumption_alert = 'high' if abs(r.consumption_diff_percentage) > 50 else 'normal'
            else:
                r.consumption_difference = 0
                r.consumption_diff_percentage = 0
                r.consumption_alert = 'normal'

    @api.depends('meter_id', 'reading_date')
    def _compute_previous_reading(self):
        for r in self:
            prev = self.search([
                ('meter_id', '=', r.meter_id.id),
                ('reading_date', '<', r.reading_date),
                ('state', 'in', ['approved', 'billed']),
            ], order='reading_date desc', limit=1)
            r.previous_reading = prev.reading_value if prev else 0.0
            r.previous_reading_date = prev.reading_date if prev else False

    # =======================
    #  دورة الحياة - الإجراءات
    # =======================

    def action_submit_review(self):
        """إرسال القراءة إلى المراجعة"""
        for r in self:
            if r.state != 'draft':
                raise ValidationError('يمكن إرسال القراءات المسودة فقط للمراجعة!')
            if not r.meter_image:
                raise ValidationError('يجب رفع صورة العداد قبل إرسال القراءة للمراجعة!')
            r.write({
                'state': 'under_review',
                'reading_source': r.reading_source or f'manual_{fields.Datetime.now()}',
            })

    def action_approve(self):
        """الموافقة على القراءة"""
        for r in self:
            if r.state != 'under_review':
                raise ValidationError('يمكن الموافقة على القراءات قيد المراجعة فقط!')
            r.write({
                'state': 'approved',
                'is_validated': True,
                'validator_id': self.env.user.id,
                'reviewer_id': self.env.user.id,
                'review_date': fields.Datetime.now(),
            })

    def action_reject(self):
        """رفض القراءة وإعادتها للمسودة"""
        for r in self:
            if r.state not in ('under_review', 'approved'):
                raise ValidationError('يمكن رفض القراءات قيد المراجعة أو المعتمدة فقط!')
            r.write({
                'state': 'draft',
                'rejection_reason': r.rejection_reason or 'مرفوضة من قبل المراجع',
            })

    def action_generate_bill(self):
        """إنشاء فاتورة من القراءة المعتمدة"""
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError('يجب الموافقة على القراءة أولاً قبل إنشاء الفاتورة!')
        if self.billed:
            raise ValidationError('تم إنشاء فاتورة لهذه القراءة مسبقاً!')
        
        tariff = self.account_id.tariff_id
        consumption = self.consumption
        
        bill_vals = {
            'customer_id': self.customer_id.id,
            'account_id': self.account_id.id,
            'meter_id': self.meter_id.id,
            'bill_date': fields.Date.today(),
            'period_start': self.previous_reading_date.date() if self.previous_reading_date else fields.Date.today(),
            'period_end': self.reading_date.date() if self.reading_date else fields.Date.today(),
            'due_date': fields.Date.today() + timedelta(days=30),
            'previous_reading': self.previous_reading,
            'current_reading': self.reading_value,
            'consumption': consumption,
            'tariff_id': tariff.id if tariff else False,
            'state': 'draft',
        }
        bill = self.env['utility.bill'].create(bill_vals)
        
        # حساب بنود الفاتورة حسب التعرفة
        if tariff:
            bill._calculate_amounts()
        
        self.state = 'billed'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.bill',
            'res_id': bill.id,
            'views': [(False, 'form')],
        }

    # =======================
    #  أوامر Batch
    # =======================

    def action_approve_batch(self):
        """موافقة جماعية على قراءات متعددة"""
        readings = self.filtered(lambda r: r.state == 'under_review')
        readings.action_approve()

    def action_generate_bills_batch(self):
        """إنشاء فواتير لقراءات معتمدة批量"""
        readings = self.filtered(lambda r: r.state == 'approved')
        for reading in readings:
            reading.action_generate_bill()

    # =======================
    #  التسلسل
    # =======================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reading_id', _('New')) == _('New'):
                vals['reading_id'] = self.env['ir.sequence'].next_by_code('utility.reading') or _('New')
        return super().create(vals_list)
```

#### المرحلة 2: تعديل الواجهة - إضافة الصور وأزرار المراجعة

**الملف:** `utility_billing/views/utility_reading_views.xml` (استبدال)

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- ===================== LIST VIEW ===================== -->
    <record id="view_utility_reading_tree" model="ir.ui.view">
        <field name="name">utility.reading.tree</field>
        <field name="model">utility.reading</field>
        <field name="arch" type="xml">
            <tree decoration-warning="state == 'under_review'"
                  decoration-success="state == 'approved'"
                  decoration-danger="state == 'error'">
                <field name="reading_id"/>
                <field name="meter_id"/>
                <field name="account_id"/>
                <field name="reading_date"/>
                <field name="reading_value"/>
                <field name="consumption"/>
                <field name="consumption_alert" widget="badge" decoration-danger="consumption_alert in ('high','negative','zero')" decoration-success="consumption_alert == 'normal'"/>
                <field name="reading_type"/>
                <field name="image_state" optional="show"/>
                <field name="state" widget="badge" decoration-warning="state == 'under_review'" decoration-success="state == 'approved'" decoration-primary="state == 'billed'"/>
                <field name="reviewer_id" optional="show"/>
            </tree>
        </field>
    </record>

    <!-- ===================== FORM VIEW ===================== -->
    <record id="view_utility_reading_form" model="ir.ui.view">
        <field name="name">utility.reading.form</field>
        <field name="model">utility.reading</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <!-- أزرار حسب الحالة -->
                    <button name="action_submit_review" type="object"
                            string="إرسال للمراجعة" class="oe_highlight"
                            states="draft"
                            groups="utility_core.group_utility_technician"/>
                    <button name="action_approve" type="object"
                            string="اعتماد القراءة" class="oe_highlight"
                            states="under_review"
                            groups="utility_core.group_utility_supervisor"/>
                    <button name="action_reject" type="object"
                            string="رفض" class="btn-danger"
                            states="under_review,approved"
                            groups="utility_core.group_utility_supervisor"/>
                    <button name="action_generate_bill" type="object"
                            string="إنشاء فاتورة" class="oe_highlight"
                            states="approved"
                            groups="utility_core.group_utility_billing_manager"/>
                    <field name="state" widget="statusbar"
                           statusbar_visible="draft,under_review,approved,billed"/>
                </header>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <!-- صور العداد -->
                        <button name="%(action_open_meter_images)d" type="action"
                                class="oe_stat_button" icon="fa-camera"
                                help="صورة العداد">
                            <div class="o_stat_info">
                                <field name="image_state" widget="badge"/>
                            </div>
                        </button>
                    </div>
                    <group>
                        <group string="معلومات القراءة">
                            <field name="reading_id"/>
                            <field name="meter_id" options="{'no_create': True}"/>
                            <field name="account_id"/>
                            <field name="customer_id"/>
                            <field name="reading_date"/>
                            <field name="reading_type"/>
                        </group>
                        <group string="قراءات العداد">
                            <field name="previous_reading"/>
                            <field name="previous_reading_date"/>
                            <field name="reading_value"/>
                            <field name="consumption" class="text-success"/>
                            <!-- تحليل الاستهلاك -->
                            <field name="consumption_difference" attrs="{'invisible': [('consumption_alert', '=', 'normal')]}"/>
                            <field name="consumption_diff_percentage" attrs="{'invisible': [('consumption_alert', '=', 'normal')]}"/>
                            <field name="consumption_alert" widget="badge"/>
                        </group>
                    </group>
                    <group string="صور العداد">
                        <field name="meter_image" widget="image"
                               class="oe_avatar" options="{'size': [200, 150]}"/>
                        <field name="meter_image_secondary" widget="image"
                               class="oe_avatar" options="{'size': [200, 150]}"/>
                    </group>
                    <group string="المراجعة" groups="utility_core.group_utility_supervisor">
                        <field name="image_state"/>
                        <field name="reviewer_id"/>
                        <field name="review_date"/>
                        <field name="review_notes"/>
                        <field name="rejection_reason" attrs="{'invisible': [('rejection_reason', '=', False)]}"/>
                    </group>
                    <field name="remarks" nolabel="1" placeholder="ملاحظات إضافية..."/>
                </sheet>
                
                <div class="oe_chatter">
                    <field name="message_follower_ids" widget="mail_followers"/>
                    <field name="activity_ids" widget="mail_activity"/>
                    <field name="message_ids" widget="mail_thread"/>
                </div>
            </form>
        </field>
    </record>

    <!-- ===================== SEARCH VIEW ===================== -->
    <record id="view_utility_reading_search" model="ir.ui.view">
        <field name="name">utility.reading.search</field>
        <field name="model">utility.reading</field>
        <field name="arch" type="xml">
            <search>
                <field name="meter_id"/>
                <field name="account_id"/>
                <field name="reading_date"/>
                <!-- فلاتر سريعة -->
                <filter name="draft" string="مسودة" domain="[('state','=','draft')]"/>
                <filter name="under_review" string="قيد المراجعة" domain="[('state','=','under_review')]"
                        help="القراءات التي تنتظر المراجعة والاعتماد"/>
                <filter name="approved" string="معتمدة" domain="[('state','=','approved')]"/>
                <filter name="awaiting_bill" string="تنتظر الفوترة" domain="[('state','=','approved')]"/>
                <filter name="estimated" string="تقديرية" domain="[('is_estimated','=',True)]"/>
                <!-- مجموعات -->
                <group expand="0" string="حالة الصورة">
                    <filter name="img_clear" string="واضحة" domain="[('image_state','=','clear')]"/>
                    <filter name="img_not_clear" string="غير واضحة" domain="[('image_state','=','not_clear')]"/>
                    <filter name="img_no_image" string="بدون صورة" domain="[('image_state','=','none')]"/>
                </group>
                <separator/>
                <group expand="0" string="حالة الاستهلاك">
                    <filter name="cons_high" string="مرتفع" domain="[('consumption_alert','=','high')]"/>
                    <filter name="cons_negative" string="سلبي" domain="[('consumption_alert','=','negative')]"/>
                    <filter name="cons_zero" string="صفر" domain="[('consumption_alert','=','zero')]"/>
                </group>
            </search>
        </field>
    </record>

    <!-- ===================== ACTIONS ===================== -->
    <record id="action_utility_reading" model="ir.actions.act_window">
        <field name="name">قراءات العدادات</field>
        <field name="res_model">utility.reading</field>
        <field name="view_mode">tree,form</field>
        <field name="search_view_id" ref="view_utility_reading_search"/>
        <field name="help">سجل قراءات العدادات. يتم رفع صورة مع كل قراءة، ثم تمر بالمراجعة والاعتماد قبل إنشاء الفاتورة.</field>
    </record>

    <!-- ===================== ACTION:Images ===================== -->
    <record id="action_open_meter_images" model="ir.actions.act_window">
        <field name="name">صورة العداد</field>
        <field name="res_model">utility.reading</field>
        <field name="view_mode">form</field>
        <field name="view_id" ref="view_utility_reading_images"/>
        <field name="target">new</field>
    </record>

    <record id="view_utility_reading_images" model="ir.ui.view">
        <field name="name">utility.reading.images.form</field>
        <field name="model">utility.reading</field>
        <field name="arch" type="xml">
            <form string="صور العداد">
                <group>
                    <field name="meter_image" widget="image" class="oe_avatar"
                           options="{'size': [400, 300]}"/>
                    <field name="meter_image_secondary" widget="image" class="oe_avatar"
                           options="{'size': [400, 300]}"/>
                </group>
                <footer>
                    <button string="إغلاق" class="oe_link" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <!-- ======================= MENU ITEM ======================= -->
    <menuitem id="menu_utility_readings_pending_review"
              name="قراءات تنتظر المراجعة"
              parent="menu_utility_billing_root"
              action="action_utility_readings_pending_review"
              sequence="15"
              groups="utility_core.group_utility_supervisor"/>

    <record id="action_utility_readings_pending_review" model="ir.actions.act_window">
        <field name="name">قراءات تنتظر المراجعة</field>
        <field name="res_model">utility.reading</field>
        <field name="view_mode">tree,form</field>
        <field name="domain">[('state', '=', 'under_review')]</field>
        <field name="context">{'default_state': 'under_review'}</field>
        <field name="help">القراءات التي تم تسجيلها وتنتظر المراجعة والاعتماد.</field>
    </record>
</odoo>
```

#### المرحلة 3: تحديث `utility.bill` - إضافة ربط مع القراءة

**تعديل `utility_billing/models/utility_bill.py`:**

```python
# إضافة الحقول
reading_id = fields.Many2one('utility.reading', 'قراءة العداد', index=True, ondelete='restrict')
meter_image = fields.Binary(related='reading_id.meter_image', string='صورة العداد')
reading_reviewer = fields.Many2one(related='reading_id.reviewer_id', string='مراجع القراءة')

def _calculate_amounts(self):
    """حساب بنود الفاتورة من التعرفة"""
    self.ensure_one()
    tariff = self.tariff_id
    if not tariff:
        return
    consumption = self.consumption
    line_vals = []
    
    # 1. بند الاستهلاك
    if tariff.price_per_kwh and consumption:
        energy_amount = consumption * tariff.price_per_kwh
        self.amount_energy = energy_amount
        line_vals.append((0, 0, {
            'name': f'استهلاك ({consumption} kWh × {tariff.price_per_kwh})',
            'quantity': consumption,
            'unit': 'kWh',
            'unit_price': tariff.price_per_kwh,
            'amount': energy_amount,
            'is_tax': False,
        }))
    
    # 2. رسم ثابت
    if tariff.fixed_charge:
        self.amount_fixed = tariff.fixed_charge
        line_vals.append((0, 0, {
            'name': 'رسم ثابت',
            'quantity': 1,
            'unit': 'شهر',
            'unit_price': tariff.fixed_charge,
            'amount': tariff.fixed_charge,
            'is_tax': False,
        }))
    
    # 3. رسم خدمة
    if tariff.service_charge:
        self.amount_service = tariff.service_charge
        line_vals.append((0, 0, {
            'name': 'رسم خدمة',
            'quantity': 1,
            'unit': 'شهر',
            'unit_price': tariff.service_charge,
            'amount': tariff.service_charge,
            'is_tax': False,
        }))
    
    subtotal = self.amount_energy + (tariff.fixed_charge or 0.0) + (tariff.service_charge or 0.0)
    
    # 4. ضريبة
    if tariff.tax_percentage:
        tax_amount = subtotal * (tariff.tax_percentage / 100.0)
        self.amount_tax = tax_amount
        line_vals.append((0, 0, {
            'name': f'ضريبة ({tariff.tax_percentage}%)',
            'quantity': 1,
            'unit': '%',
            'unit_price': tax_amount,
            'amount': tax_amount,
            'is_tax': True,
        }))
    
    self.line_ids = line_vals
    self.amount_total = subtotal + (self.amount_tax or 0.0)
```

#### المرحلة 4: تحديث `utility.billing.cycle` - استخدام القراءات المعتمدة فقط

**تعديل `utility_billing/models/utility_billing_cycle.py`:**

```python
def action_generate_bills(self):
    """توليد الفواتير من القراءات المعتمدة فقط (وليس validated)"""
    self.ensure_one()
    for meter in self.meter_ids:
        if not meter.account_id:
            continue
        # آخر قراءة معتمدة غير مفوترة
        last_reading = self.env['utility.reading'].search([
            ('meter_id', '=', meter.id),
            ('state', '=', 'approved'),  # ← معتمدة فقط!
        ], order='reading_date desc', limit=1)
        if not last_reading:
            continue
        # آخر فاتورة
        last_bill = self.env['utility.bill'].search([
            ('meter_id', '=', meter.id),
            ('state', 'in', ['confirmed', 'paid']),
        ], order='period_end desc', limit=1)
        prev_reading = last_bill.current_reading if last_bill else 0.0
        consumption = last_reading.reading_value - prev_reading
        if consumption < 0:
            consumption = 0
        bill = self._create_bill(meter.account_id, meter, last_reading, prev_reading, consumption)
        last_reading.state = 'billed'
```

#### المرحلة 5: تحديث صلاحيات الوصول

**تعديل `utility_billing/security/ir.model.access.csv`:**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
admin_reading,utility.reading.admin,model_utility_reading,base.group_system,1,1,1,1
billing_manager_reading,utility.reading.billing_manager,model_utility_reading,utility_core.group_billing_manager,1,1,1,1
technician_reading,utility.reading.technician,model_utility_reading,utility_core.group_utility_technician,1,1,1,0
supervisor_reading,utility.reading.supervisor,model_utility_reading,utility_core.group_utility_supervisor,1,1,0,0
auditor_reading,utility.reading.auditor,model_utility_reading,utility_core.group_auditor,1,0,0,0
```

### الملفات المتأثرة (4 تعديلات + 0 جديد)

| الملف | نوع التغيير |
|-------|------------|
| `utility_billing/models/utility_reading.py` | **استبدال كامل** - إضافة صور، مراجعة، تحليل استهلاك، تدفق تحت_review→approved |
| `utility_billing/views/utility_reading_views.xml` | **استبدال كامل** - إضافة صور، أزرار موافقة/رفض، فلاتر مراجعة |
| `utility_billing/models/utility_bill.py` | **تعديل** - إضافة reading_id, _calculate_amounts() |
| `utility_billing/models/utility_billing_cycle.py` | **تعديل** - استخدام `state='approved'` بدلاً من `state='validated'` |
| `utility_billing/security/ir.model.access.csv` | **تعديل** - إضافة صلاحيات للمشرف والفني |

---

## 🔴 3. العقود المتكررة (Recurring Contracts)

### الهدف
نظام قوالب عقود كهربائية ينشئ فواتير/أوامر بيع تلقائياً حسب دورة الفوترة، مع بنود متغيرة (استهلاك/رسم ثابت/خصم) وربط بقراءات العداد.

### التنفيذ - 5 مراحل

#### المرحلة 1: موديل `utility.contract.template`

**الملف:** `utility_core/models/utility_contract_template.py`

```python
class UtilityContractTemplate(models.Model):
    _name = 'utility.contract.template'
    _description = 'Utility Contract Template'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    
    # --- Billing Configuration ---
    recurring_rule_type = fields.Selection([
        ('monthly', 'شهري'),
        ('bi_monthly', 'نصف شهري'),
        ('quarterly', 'ربع سنوي'),
        ('yearly', 'سنوي'),
    ], default='monthly', required=True)
    recurring_invoicing_type = fields.Selection([
        ('postpaid', 'آجل (Post-paid)'),
        ('prepaid', 'مسبق (Pre-paid)'),
    ], default='postpaid', required=True)
    recurring_interval = fields.Integer(default=1, string='كل كام شهر/دورة')

    # --- Lines ---
    line_ids = fields.One2many('utility.contract.template.line', 'template_id', copy=True, string='بنود العقد')
    meter_line_ids = fields.One2many('utility.contract.template.meter.line', 'template_id', copy=True, string='بنود قراءات العداد')

    # --- Account Config ---
    pricelist_id = fields.Many2one('product.pricelist')
    journal_id = fields.Many2one('account.journal', domain="[('type', 'in', ['sale', 'general'])]")
    tariff_id = fields.Many2one('utility.tariff')
    
    # --- Workflow ---
    sale_autoconfirm = fields.Boolean(default=True, string='تأكيد أمر البيع تلقائياً')
    create_invoice_automatically = fields.Boolean(default=True, string='إنشاء الفاتورة تلقائياً')
    validate_invoice_automatically = fields.Boolean(default=False)

    # --- Auto Pay ---
    is_auto_pay = fields.Boolean(string='دفع تلقائي')
    auto_pay_retries = fields.Integer(default=3)
    auto_pay_retry_hours = fields.Integer(default=1)

    active = fields.Boolean(default=True)
```

#### المرحلة 2: `utility.contract.template.line`

**الملف:** `utility_core/models/utility_contract_template_line.py`

```python
class UtilityContractTemplateLine(models.Model):
    _name = 'utility.contract.template.line'
    _description = 'Contract Template Line'

    template_id = fields.Many2one('utility.contract.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    
    product_id = fields.Many2one('product.product', required=True, domain="[('type', '=', 'service')]")
    name = fields.Text(string='Description', translate=True)
    
    quantity = fields.Float(default=1.0)
    uom_id = fields.Many2one('uom.uom')
    
    price_type = fields.Selection([
        ('fixed', 'سعر ثابت'),
        ('from_product', 'من المنتج'),
        ('formula', 'معادلة'),
        ('meter_reading', 'حسب قراءة العداد'),
    ], default='fixed', required=True)
    
    specific_price = fields.Float(string='السعر')
    formula_code = fields.Text(string='كود المعادلة', help='Python expression using variables: reading, consumption, tariff')
    
    # For meter-based lines
    meter_line_type = fields.Selection([
        ('consumption', 'الاستهلاك'),
        ('fixed_fee', 'رسم ثابت'),
        ('service_charge', 'رسم خدمة'),
        ('discount', 'خصم'),
        ('tax', 'ضريبة'),
    ])
```

#### المرحلة 3: ربط العقد مع `utility.account`

**الملف:** `utility_core/models/utility_account.py` (إضافة حقول)

```python
contract_template_id = fields.Many2one('utility.contract.template', string='نموذج العقد')
date_contract = fields.Date(string='تاريخ العقد')
date_sub_start = fields.Date(string='تاريخ بداية الاشتراك')
date_end = fields.Date(string='تاريخ انتهاء العقد')
recurring_next_date = fields.Date(string='تاريخ الفاتورة القادمة', help='تاريخ إنشاء الفاتورة التالية')

# حالة العقد
contract_state = fields.Selection([
    ('new', 'جديد'),
    ('active', 'نشط'),
    ('suspended', 'موقوف'),
    ('closed', 'مغلق'),
], default='new', string='حالة العقد')

# تواريخ القراءات
last_reading_date = fields.Datetime()
last_invoice_date = fields.Datetime()
last_reading_value = fields.Float('آخر قراءة مسجلة')
last_invoice_reading = fields.Float('آخر قراءة مفوترة')
```

#### المرحلة 4: توليد الفواتير من العقود

**الملف:** `utility_billing/models/utility_recurring_invoice.py`

```python
class UtilityContractTemplate(models.Model):
    _inherit = 'utility.contract.template'

    def _prepare_bill_data(self, account, reading):
        """تحضير بيانات الفاتورة من العقد والقراءة المعتمدة"""
        tariff = account.tariff_id
        consumption = reading.consumption
        lines = []
        
        for line in self.line_ids:
            if line.meter_line_type == 'consumption' and tariff:
                price = tariff.price_per_kwh or 0
                amount = consumption * price
                lines.append((0, 0, {
                    'name': f'استهلاك ({consumption} kWh × {price})',
                    'quantity': consumption,
                    'unit': 'kWh',
                    'unit_price': price,
                    'amount': amount,
                }))
            elif line.price_type == 'fixed':
                lines.append((0, 0, {
                    'name': line.name or line.product_id.name,
                    'quantity': line.quantity,
                    'unit': 'شهر',
                    'unit_price': line.specific_price,
                    'amount': line.quantity * line.specific_price,
                }))
        
        return {
            'account_id': account.id,
            'customer_id': account.customer_id.id,
            'meter_id': account.meter_id.id,
            'reading_id': reading.id,
            'tariff_id': tariff.id if tariff else False,
            'period_start': reading.previous_reading_date.date() if reading.previous_reading_date else fields.Date.today(),
            'period_end': reading.reading_date.date() if reading.reading_date else fields.Date.today(),
            'previous_reading': reading.previous_reading,
            'current_reading': reading.reading_value,
            'consumption': consumption,
            'line_ids': lines,
        }

    def cron_generate_recurring_invoices(self):
        """إنشاء فواتير للحسابات التي لديها عقود نشطة وقراءات معتمدة غير مفوترة"""
        accounts = self.env['utility.account'].search([
            ('contract_state', '=', 'active'),
            ('contract_template_id', '!=', False),
        ])
        for account in accounts:
            # البحث عن آخر قراءة معتمدة غير مفوترة
            reading = self.env['utility.reading'].search([
                ('account_id', '=', account.id),
                ('state', '=', 'approved'),
            ], order='reading_date desc', limit=1)
            if not reading:
                continue
            bill_data = account.contract_template_id._prepare_bill_data(account, reading)
            bill = self.env['utility.bill'].create(bill_data)
            bill._calculate_amounts()
            reading.state = 'billed'
```

#### المرحلة 5: CRON للفوترة التلقائية + الواجهات

- **الملف:** `utility_billing/data/utility_cron_extras.xml` (كرون كل ساعة)
- **الملف:** `utility_core/views/utility_contract_template_views.xml` (قائمة/نموذج/بحث)

### الملفات النهائية (7 ملفات جديدة + 2 تعديلات)

| الملف | نوع |
|-------|-----|
| `utility_core/models/utility_contract_template.py` | جديد |
| `utility_core/models/utility_contract_template_line.py` | جديد |
| `utility_core/models/utility_contract_template_meter_line.py` | جديد |
| `utility_core/models/utility_account.py` | تعديل (إضافة حقول العقد) |
| `utility_core/views/utility_contract_template_views.xml` | جديد |
| `utility_core/views/utility_account_views.xml` | تعديل (إضافة tabs العقد) |
| `utility_core/security/ir.model.access.csv` | تعديل (صلاحيات) |
| `utility_billing/models/utility_recurring_invoice.py` | جديد |
| `utility_billing/data/utility_cron_extras.xml` | جديد |
| `utility_billing/security/ir.model.access.csv` | تعديل |

---

## 🔴 4. فئات المشتركين والخصم المدعوم (Subscriber Categories & Discounts)

### الهدف
نظام فئات هرمي للمشتركين مع دعم الخصم المدعوم (مثل أول 100 kWh بسعر مدعوم)، ومعادلات ديناميكية (Formulas) تحسب الكمية تلقائياً في بنود العقد.

### مستوحى من PEC
```xml
<!-- PEC: خصم الاستهلاك المدعوم -->
<!-- إذا كان الاستهلاك < 100 وحدة → الخصم = كل الوحدات -->
<!-- إذا كان الاستهلاك >= 100 وحدة → الخصم = 100 وحدة (حد أقصى) -->
<!-- السعر = سالب (يظهر في الفاتورة كخصم) -->
```

### التنفيذ - 4 مراحل

#### المرحلة 1: موديل `utility.subscriber.category` (فئات هرمية)

**الملف:** `utility_core/models/utility_subscriber_category.py`

```python
class UtilitySubscriberCategory(models.Model):
    _name = 'utility.subscriber.category'
    _description = 'Subscriber Category'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'sequence, code'

    name = fields.Char('الاسم', required=True, translate=True)
    code = fields.Char('الكود', required=True)
    sequence = fields.Integer('الترتيب', default=10)
    
    # هرمية الفئات (مستويين: category → subcategory)
    parent_id = fields.Many2one('utility.subscriber.category', 'الفئة الرئيسية',
        index=True, ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('utility.subscriber.category', 'parent_id', 'الفئات الفرعية')
    level = fields.Selection([
        ('category', 'فئة رئيسية'),
        ('subcategory', 'فئة فرعية'),
    ], compute='_compute_level', store=True, string='المستوى')
    
    # --- إعدادات الخصم المدعوم ---
    subsidized_enabled = fields.Boolean('تفعيل الخصم المدعوم', default=False,
        help='تفعيل الخصم المدعوم لأول N كيلوواط/ساعة لهذه الفئة')
    subsidized_max_units = fields.Float('الحد الأقصى للوحدات المدعومة', default=100.0,
        help='أول X kWh مدعومة (مثلاً 100)')
    subsidized_percentage = fields.Float('نسبة الدعم (%)', default=100.0,
        help='نسبة الدعم: 100% = مجاناً، 50% = نصف السعر')
    subsidized_price_per_kwh = fields.Float('سعر الوحدة المدعومة', 
        help='سعر ثابت للوحدات المدعومة (يترك فارغاً لحساب النسبة)')
    
    # --- إعدادات الحسابات المحاسبية ---
    subsidy_account_id = fields.Many2one('account.account', 'حساب مصروف الدعم',
        help='حساب مصروف دعم الاستهلاك (مدين)')
    revenue_account_id = fields.Many2one('account.account', 'حساب الإيراد')
    
    # --- إعدادات الفوترة ---
    default_tariff_id = fields.Many2one('utility.tariff', 'التعرفة الافتراضية')
    default_contract_template_id = fields.Many2one('utility.contract.template', 'قالب العقد الافتراضي')
    
    description = fields.Text('الوصف')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('code_unique_per_company', 'unique(code, company_id)',
         'كود الفئة يجب أن يكون فريداً لكل شركة!'),
    ]

    @api.depends('parent_id')
    def _compute_level(self):
        for rec in self:
            rec.level = 'subcategory' if rec.parent_id else 'category'

    def name_get(self):
        res = []
        for rec in self:
            name = f"[{rec.code}] {rec.name}"
            if rec.parent_id:
                name = f"{rec.parent_id.name} / {name}"
            res.append((rec.id, name))
        return res

    def _get_subsidized_amount(self, consumption, tariff):
        """حساب مبلغ الخصم المدعوم حسب الفئة والاستهلاك
        Returns: (quantity, unit_price, name) للبند في الفاتورة
        """
        self.ensure_one()
        if not self.subsidized_enabled or consumption <= 0:
            return (0, 0, '')
        
        # تحديد الوحدات المدعومة: إذا الاستهلاك < الحد → كل الوحدات، وإلا الحد الأقصى
        subsidized_units = min(consumption, self.subsidized_max_units)
        
        # حساب السعر:
        if self.subsidized_price_per_kwh:
            unit_price = -(self.subsidized_price_per_kwh)  # سالب = خصم
        elif tariff and tariff.price_per_kwh:
            discount_price = tariff.price_per_kwh * (self.subsidized_percentage / 100.0)
            unit_price = -(discount_price)  # سالب = خصم
        else:
            unit_price = -130.0  # قيمة افتراضية (مثل PEC)
        
        return (subsidized_units, unit_price,
                f'خصم استهلاك مدعوم - {subsidized_units} وحدة')
```

#### المرحلة 2: معادلات ديناميكية (Formulas) لحساب بنود العقد

**الملف:** `utility_core/models/utility_formula.py`

```python
class UtilityFormula(models.Model):
    _name = 'utility.formula'
    _description = 'Utility Formula for Contract Lines'
    _rec_name = 'name'

    name = fields.Char('اسم المعادلة', required=True, translate=True)
    code = fields.Text('كود المعادلة', required=True,
        help='كود Python يتم تنفيذه لحساب الكمية.\n'
             'المتغيرات المتاحة:\n'
             '- consumption: float - الاستهلاك (kWh)\n'
             '- previous_reading: float - القراءة السابقة\n'
             '- current_reading: float - القراءة الحالية\n'
             '- tariff: object - كائن التعرفة\n'
             '- account: object - كائن الحساب\n'
             '- category: object - كائن فئة المشترك\n'
             '- line: object - كائن بند العقد الحالي\n'
             '- result: float - يجب تعيينها بقيمة الكمية المحسوبة\n'
             '- name: str - يمكن تغييرها لوصف مخصص')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def execute(self, consumption=0, previous_reading=0, current_reading=0,
                tariff=None, account=None, category=None, line=None):
        """تنفيذ المعادلة مع المتغيرات الممررة"""
        self.ensure_one()
        result = 0.0
        name = self.name
        
        # متغيرات السياق
        locals_dict = {
            'consumption': consumption or 0.0,
            'previous_reading': previous_reading or 0.0,
            'current_reading': current_reading or 0.0,
            'tariff': tariff,
            'account': account,
            'category': category,
            'line': line,
            'result': result,
            'name': name,
        }
        
        try:
            safe_eval(self.code, mode='exec', locals_dict=locals_dict)
            result = locals_dict.get('result', 0.0)
            name = locals_dict.get('name', self.name)
        except Exception as e:
            _logger.warning(f"Formula execution error in {self.name}: {e}")
            result = 0.0
        
        return result, name

    # معادلات مدمجة افتراضية (seed data)
    @api.model
    def _load_default_formulas(self):
        """تحميل المعادلات الافتراضية (تستدعى من data.xml)"""
        Formulas = self.env['utility.formula']
        formulas = [
            {
                'name': 'رسوم اشتراك ثابت',
                'code': '''
# إذا كان الاستهلاك صفر → رسوم الاشتراك صفر
if consumption > 0:
    result = 1.0
else:
    result = 0.0
''',
            },
            {
                'name': 'استهلاك كهرباء',
                'code': '''
# كمية الاستهلاك = قراءة العداد (kWh)
result = consumption
''',
            },
            {
                'name': 'خصم استهلاك مدعوم (نظام PEC)',
                'code': '''
# خصم الاستهلاك المدعوم - أول 100 kWh
# إذا كان الاستهلاك < 100 → الخصم = كل الاستهلاك
# وإلا → الخصم = 100
units = consumption or 0.0
if units > 0:
    if units < 100.0:
        result = units
        name = "خصم استهلاك مدعوم - %s وحدة" % units
    else:
        result = 100.0
        name = "خصم استهلاك مدعوم - 100 وحدة"
    # سعر الخصم: سالب = يظهر كخصم في الفاتورة
    # يتم ضبط السعر من خانة السعر في بند العقد (بقيمة سالبة)
else:
    result = 0.0
    name = "خصم استهلاك مدعوم"
''',
            },
            {
                'name': 'خصم استهلاك مدعوم (حسب الفئة)',
                'code': '''
# خصم الاستهلاك المدعوم بناءً على فئة المشترك
# يتم تحديد الحد الأقصى ونسبة الدعم من إعدادات الفئة
if category and category.subsidized_enabled and consumption > 0:
    max_units = category.subsidized_max_units
    pct = category.subsidized_percentage / 100.0
    subsidized = min(consumption, max_units)
    result = subsidized
    name = "خصم مدعوم - %s وحدة (فئة: %s)" % (subsidized, category.name)
else:
    result = 0.0
''',
            },
            {
                'name': 'نسبة من الاستهلاك',
                'code': '''
# خصم بنسبة مئوية من الاستهلاك
# النسبة محددة في سعر البند (مثلاً 50 = 50%)
percentage = abs(line.specific_price or 0.0) if line else 50.0
result = (consumption or 0.0) * (percentage / 100.0)
name = "خصم %s%% من الاستهلاك" % percentage
''',
            },
        ]
        for f_data in formulas:
            existing = Formulas.search([('name', '=', f_data['name'])], limit=1)
            if not existing:
                Formulas.create(f_data)
```

#### المرحلة 3: ربط الفئات مع `utility.customer` + دمج مع بند العقد

**تعديل `utility_core/models/utility_customer.py`:**

```python
# إضافة إلى utility.customer
subscriber_category_id = fields.Many2one('utility.subscriber.category',
    string='فئة المشترك', index=True,
    domain="[('level', '=', 'subcategory')]")
```

**تعديل `utility_core/models/utility_contract_template_line.py` - إضافة formula:**

```python
# إضافة حقول للمعادلة
qty_formula_id = fields.Many2one('utility.formula', 'معادلة الكمية',
    help='معادلة ديناميكية تحسب الكمية تلقائياً (متغيرات: consumption, tariff, account, category)')
is_subsidized = fields.Boolean('خصم مدعوم',
    help='يطبق الخصم حسب فئة المشترك')
```

**تعديل `utility_billing/models/utility_bill.py` - تطبيق الخصم عند حساب الفاتورة:**

```python
def _calculate_amounts(self):
    """حساب بنود الفاتورة مع دعم المعادلات والخصم المدعوم"""
    self.ensure_one()
    tariff = self.tariff_id
    account = self.account_id
    category = account.customer_id.subscriber_category_id if account else False
    consumption = self.consumption
    line_vals = []
    
    # 1. البحث عن قالب العقد وبنوده
    template = account.contract_template_id if account else False
    
    if template:
        for line in template.line_ids:
            qty = line.quantity
            price = line.specific_price or 0.0
            name = line.name or ''
            
            # تنفيذ المعادلة إذا وجدت
            if line.qty_formula_id:
                qty, computed_name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    tariff=tariff,
                    account=account,
                    category=category,
                    line=line,
                )
                if computed_name:
                    name = computed_name
            
            # تطبيق الخصم المدعوم من الفئة (إن لم يكن هناك معادلة خاصة)
            elif line.is_subsidized and category and category.subsidized_enabled and consumption > 0:
                qty, price, name = category._get_subsidized_amount(consumption, tariff)
            
            amount = qty * price
            line_vals.append((0, 0, {
                'name': name,
                'quantity': qty,
                'unit': 'kWh' if line.meter_line_type == 'consumption' else 'شهر',
                'unit_price': price,
                'amount': amount,
                'is_tax': line.meter_line_type == 'tax',
            }))
            
            # تجميع المبالغ
            if line.meter_line_type == 'consumption':
                self.amount_energy += amount
            elif line.meter_line_type == 'fixed_fee':
                self.amount_fixed += amount
            elif line.meter_line_type == 'service_charge':
                self.amount_service += amount
            elif line.meter_line_type == 'tax' or line.meter_line_type == 'tax':
                self.amount_tax += amount
    
    else:
        # حساب يدوي بدون قالب (تعرفة فقط)
        if tariff and tariff.price_per_kwh and consumption > 0:
            energy_amount = consumption * tariff.price_per_kwh
            self.amount_energy = energy_amount
            line_vals.append((0, 0, {
                'name': f'استهلاك ({consumption} kWh × {tariff.price_per_kwh})',
                'quantity': consumption,
                'unit': 'kWh',
                'unit_price': tariff.price_per_kwh,
                'amount': energy_amount,
            }))
        
        if tariff and tariff.fixed_charge:
            self.amount_fixed = tariff.fixed_charge
            line_vals.append((0, 0, {
                'name': 'رسم ثابت', 'quantity': 1,
                'unit': 'شهر', 'unit_price': tariff.fixed_charge,
                'amount': tariff.fixed_charge, 'is_tax': False,
            }))
        
        if tariff and tariff.service_charge:
            self.amount_service = tariff.service_charge
            line_vals.append((0, 0, {
                'name': 'رسم خدمة', 'quantity': 1,
                'unit': 'شهر', 'unit_price': tariff.service_charge,
                'amount': tariff.service_charge, 'is_tax': False,
            }))
    
    subtotal = self.amount_energy + self.amount_fixed + self.amount_service
    
    # ضريبة
    if tariff and tariff.tax_percentage:
        tax_amount = subtotal * (tariff.tax_percentage / 100.0)
        self.amount_tax = tax_amount
        line_vals.append((0, 0, {
            'name': f'ضريبة ({tariff.tax_percentage}%)',
            'quantity': 1, 'unit': '%', 'unit_price': tax_amount,
            'amount': tax_amount, 'is_tax': True,
        }))
    
    self.line_ids = line_vals
    self.amount_total = subtotal + self.amount_tax
```

#### المرحلة 4: بيانات افتراضية (Seed Data)

**الملف:** `utility_core/data/utility_subscriber_data.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <!-- ====== فئات المشتركين ====== -->
    <record id="sub_category_residential" model="utility.subscriber.category">
        <field name="name">سكني</field>
        <field name="code">RES</field>
        <field name="sequence">10</field>
        <field name="subsidized_enabled" eval="True"/>
        <field name="subsidized_max_units">100</field>
        <field name="subsidized_percentage">100</field>
    </record>

    <record id="sub_category_commercial" model="utility.subscriber.category">
        <field name="name">تجاري</field>
        <field name="code">COM</field>
        <field name="sequence">20</field>
        <field name="subsidized_enabled" eval="False"/>
    </record>

    <record id="sub_category_industrial" model="utility.subscriber.category">
        <field name="name">صناعي</field>
        <field name="code">IND</field>
        <field name="sequence">30</field>
        <field name="subsidized_enabled" eval="False"/>
    </record>

    <record id="sub_category_government" model="utility.subscriber.category">
        <field name="name">حكومي</field>
        <field name="code">GOV</field>
        <field name="sequence">40</field>
        <field name="subsidized_enabled" eval="False"/>
    </record>

    <record id="sub_category_agriculture" model="utility.subscriber.category">
        <field name="name">زراعي</field>
        <field name="code">AGR</field>
        <field name="sequence">50</field>
        <field name="subsidized_enabled" eval="True"/>
        <field name="subsidized_max_units">200</field>
        <field name="subsidized_percentage">50</field>
    </record>

    <!-- ====== معادلات افتراضية ====== -->
    <record id="formula_fixed_fee" model="utility.formula">
        <field name="name">رسوم اشتراك ثابت</field>
        <field name="code"><![CDATA[# إذا كان الاستهلاك صفر → رسوم الاشتراك صفر
if consumption > 0:
    result = 1.0
else:
    result = 0.0]]></field>
    </record>

    <record id="formula_consumption" model="utility.formula">
        <field name="name">استهلاك كهرباء</field>
        <field name="code">result = consumption</field>
    </record>

    <record id="formula_discount" model="utility.formula">
        <field name="name">خصم استهلاك مدعوم (نظام PEC)</field>
        <field name="code"><![CDATA[# خصم أول 100 كيلوواط/ساعة مدعوم
units = consumption or 0.0
if units > 0:
    if units < 100.0:
        result = units
        name = "خصم استهلاك مدعوم - %s وحدة" % units
    else:
        result = 100.0
        name = "خصم استهلاك مدعوم - 100 وحدة"
else:
    result = 0.0]]></field>
    </record>
</odoo>
```

### ملفات (3 جديد + 3 تعديلات)

| الملف | نوع |
|-------|-----|
| `utility_core/models/utility_subscriber_category.py` | **جديد** |
| `utility_core/models/utility_formula.py` | **جديد** |
| `utility_core/models/utility_customer.py` | **تعديل** (إضافة subscriber_category_id) |
| `utility_core/models/utility_contract_template_line.py` | **تعديل** (إضافة qty_formula_id, is_subsidized) |
| `utility_billing/models/utility_bill.py` | **تعديل** (_calculate_amounts مع formulas) |
| `utility_core/views/utility_subscriber_category_views.xml` | **جديد** (واجهة) |
| `utility_core/views/utility_customer_views.xml` | **تعديل** (إضافة حقل الفئة) |
| `utility_core/data/utility_subscriber_data.xml` | **جديد** (seed data) |
| `utility_core/security/ir.model.access.csv` | **تعديل** (صلاحيات) |

### هيكل الفاتورة النهائي (مثال)
```
فاتورة كهرباء - أحمد محمد
═══════════════════════
رسوم اشتراك شهري          1,000  يمني
استهلاك (150 kWh × 130)  19,500  يمني
خصم استهلاك مدعوم - 100 وحدة   -13,000  يمني  ← السالب = خصم
───────────────────────
الإجمالي                    7,500  يمني
═══════════════════════
```

### كيف يعمل الخصم المدعوم؟
```
الاستهلاك = 150 kWh
الحد الأقصى المدعوم = 100 kWh (للفئة السكنية)
الوحدات المدعومة = min(150, 100) = 100
سعر الوحدة المدعومة = -(130 × 100%) = -130
الخصم = 100 × (-130) = -13,000 ← يظهر سالباً في الفاتورة
```

---

## 🟡 5. خلايا المحولات وتحليل الفاقد (Transformer Cells & Loss Analysis)

### الهدف
نظام خلايا المحولات لإدارة العدادات المرتبطة بمحول واحد، توزيع الاستهلاك على المشتركين، وتحليل الفاقد (Loss) بين عداد الربط (Coupling Meter) وعدادات المشتركين (Child Meters).

### مفهوم PEC
```
محول (Transformer)
    │
    ├── عداد الربط (Coupling Meter) ← يقيس إجمالي الطاقة الداخلة
    │
    ├── الخلية 1 (Cell)
    │   ├── المشترك أ ← عقد فرعي بنسبة %main
    │   └── المشترك ب ← عقد فرعي بنسبة %sub
    │
    ├── الخلية 2 (Cell)
    │   └── المشترك ج
    │
    └── الفاقد (Loss) = قراءة عداد الربط - ∑ قراءات الخلايا
```

### التنفيذ - 5 مراحل

#### المرحلة 1: موديل `utility.transformer.cell`

**الملف:** `utility_core/models/utility_transformer_cell.py`

```python
class UtilityTransformerCell(models.Model):
    _name = 'utility.transformer.cell'
    _description = 'Transformer Cell'
    _rec_name = 'display_name'
    _order = 'transformer_id, code'

    display_name = fields.Char(compute='_compute_display_name', store=True)
    
    name = fields.Char('اسم الخلية', required=True)
    code = fields.Char('كود الخلية', required=True)
    
    # ربط مع المحول
    transformer_id = fields.Many2one('utility.transformer', 'المحول',
        required=True, index=True)
    region_id = fields.Many2one('utility.region', related='transformer_id.region_id',
        store=True)
    area_id = fields.Many2one('utility.area', related='transformer_id.area_id',
        store=True)
    zone_id = fields.Many2one('utility.zone', related='transformer_id.zone_id',
        store=True)
    
    # عداد الربط (المحول الرئيسي)
    coupling_meter_id = fields.Many2one('utility.meter', 'عداد الربط',
        domain="[('transformer_id', '=', transformer_id)]",
        help='العداد الرئيسي الذي يقيس إجمالي الطاقة الداخلة للمحول')
    
    # عقود الخلايا (المشتركين المرتبطين)
    cell_account_ids = fields.One2many('utility.account', 'cell_id',
        string='عقود الخلايا',
        help='عقود المشتركين المغذاة من هذه الخلية')
    cell_account_count = fields.Integer('عدد العقود',
        compute='_compute_cell_stats', store=True)
    
    # إحصائيات الخلية
    total_consumption = fields.Float('إجمالي الاستهلاك (kWh)',
        compute='_compute_cell_stats', store=True,
        help='مجموع استهلاك جميع عقود الخلية في آخر دورة')
    cell_loss_kwh = fields.Float('فاقد الخلية (kWh)',
        compute='_compute_cell_stats', store=True)
    loss_percentage = fields.Float('نسبة الفاقد %',
        compute='_compute_cell_stats', store=True)
    
    # نسب التوزيع (للمحولات الخاصة)
    distribution_percentage = fields.Float('نسبة التوزيع %',
        default=100.0,
        help='نسبة توزيع الاستهلاك لهذه الخلية من إجمالي المحول')
    
    # إعدادات
    is_private = fields.Boolean('محول خاص',
        help='محول خاص بمشترك واحد أو مجموعة محدودة')
    private_account_id = fields.Many2one('utility.account', 'الحساب الخاص',
        domain="[('cell_id', '=', id)]")
    
    notes = fields.Text('ملاحظات')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('code_unique_per_transformer',
         'unique(code, transformer_id)',
         'كود الخلية يجب أن يكون فريداً لكل محول!'),
    ]

    @api.depends('transformer_id', 'name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name} / {rec.transformer_id.name}"

    @api.depends('cell_account_ids', 'cell_account_ids.meter_id')
    def _compute_cell_stats(self):
        Reading = self.env['utility.reading']
        for rec in self:
            rec.cell_account_count = len(rec.cell_account_ids)
            total = 0.0
            for account in rec.cell_account_ids:
                last_reading = Reading.search([
                    ('account_id', '=', account.id),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                total += last_reading.consumption if last_reading else 0.0
            rec.total_consumption = total

    def action_view_cell_accounts(self):
        """عرض عقود الخلية"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'عقود الخلية {self.display_name}',
            'res_model': 'utility.account',
            'domain': [('cell_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_open_transformer_balance(self):
        """فتح تقرير توازن المحول لهذه الخلية"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'توازن المحول - {self.transformer_id.name}',
            'res_model': 'utility.transformer.balance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_transformer_id': self.transformer_id.id,
                'default_cell_id': self.id,
            },
        }
```

#### المرحلة 2: إضافة `cell_id` إلى `utility.account`

**تعديل `utility_core/models/utility_account.py` - إضافة حقول الخلية:**

```python
cell_id = fields.Many2one('utility.transformer.cell', 'الخلية',
    index=True,
    domain="[('transformer_id', '=', transformer_id)]")
coupling_meter_id = fields.Many2one('utility.meter',
    related='cell_id.coupling_meter_id', store=True,
    string='عداد الربط')
is_private_transformer = fields.Boolean('محول خاص',
    related='cell_id.is_private', store=True)
distribution_percentage = fields.Float('نسبة التوزيع %',
    related='cell_id.distribution_percentage', store=True)
```

#### المرحلة 3: معالج توازن المحول (Transformer Balance Wizard)

**الملف:** `utility_core/wizards/transformer_balance_wizard.py`

```python
class UtilityTransformerBalanceWizard(models.TransientModel):
    _name = 'utility.transformer.balance.wizard'
    _description = 'Transformer Balance Report Wizard'

    transformer_id = fields.Many2one('utility.transformer', 'المحول',
        required=True, domain="[('status', '=', 'active')]")
    cell_id = fields.Many2one('utility.transformer.cell', 'الخلية',
        domain="[('transformer_id', '=', transformer_id)]")
    date_from = fields.Date('من تاريخ', required=True,
        default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date('إلى تاريخ', required=True,
        default=fields.Date.today)
    
    # الحقول المحسوبة (قراءة فقط)
    coupling_meter_ids = fields.One2many('utility.meter',
        compute='_compute_meters',
        string='عدادات الربط')
    child_meter_ids = fields.One2many('utility.meter',
        compute='_compute_meters',
        string='عدادات المشتركين')
    
    total_supplied_kwh = fields.Float('الطاقة الموردة (kWh)',
        compute='_compute_balance', store=True)
    total_consumed_kwh = fields.Float('الطاقة المستهلكة (kWh)',
        compute='_compute_balance', store=True)
    total_loss_kwh = fields.Float('الفاقد (kWh)',
        compute='_compute_balance', store=True)
    loss_percentage = fields.Float('نسبة الفاقد %',
        compute='_compute_balance', store=True)
    
    # تفاصيل الفاقد
    coupling_readings = fields.Text('قراءات عدادات الربط',
        compute='_compute_details')
    child_readings_table = fields.Text('قراءات عدادات المشتركين',
        compute='_compute_details')
    
    # إعدادات التقرير
    show_cells = fields.Boolean('إظهار الخلايا', default=True)
    show_loss_threshold = fields.Float('حد الإنذار للفاقد %', default=10.0,
        help='إذا تجاوز الفاقد هذه النسبة يظهر إنذار أحمر')

    @api.depends('transformer_id')
    def _compute_meters(self):
        for rec in self:
            transformer = rec.transformer_id
            if not transformer:
                rec.coupling_meter_ids = False
                rec.child_meter_ids = False
                continue
            
            # عدادات الربط: العدادات المرتبطة مباشرة بالمحول (type = coupling)
            coupling = self.env['utility.meter'].search([
                ('transformer_id', '=', transformer.id),
                ('is_coupling_meter', '=', True),
            ])
            rec.coupling_meter_ids = coupling
            
            # عدادات المشتركين: كل العدادات الأخرى المرتبطة بالمحول
            children = self.env['utility.meter'].search([
                ('transformer_id', '=', transformer.id),
                ('is_coupling_meter', '=', False),
            ])
            rec.child_meter_ids = children

    @api.depends('date_from', 'date_to', 'transformer_id', 'cell_id')
    def _compute_balance(self):
        Reading = self.env['utility.reading']
        for rec in self:
            coupling_meters = rec.coupling_meter_ids
            child_meters = rec.child_meter_ids
            
            if rec.cell_id:
                # فلترة حسب خلية محددة
                cell = rec.cell_id
                child_meters = self.env['utility.meter'].search([
                    ('id', 'in', child_meters.ids),
                    ('account_id.cell_id', '=', cell.id),
                ])
            
            # قراءات عدادات الربط
            coupling_readings = Reading.search([
                ('meter_id', 'in', coupling_meters.ids),
                ('reading_date', '>=', rec.date_from),
                ('reading_date', '<=', rec.date_to),
                ('state', 'in', ['approved', 'billed']),
            ])
            
            # قراءات عدادات المشتركين
            child_readings = Reading.search([
                ('meter_id', 'in', child_meters.ids),
                ('reading_date', '>=', rec.date_from),
                ('reading_date', '<=', rec.date_to),
                ('state', 'in', ['approved', 'billed']),
            ])
            
            # تجميع حسب العداد (آخر قراءة في الفترة لكل عداد)
            supplied = 0.0
            consumed = 0.0
            
            for meter in coupling_meters:
                last = Reading.search([
                    ('meter_id', '=', meter.id),
                    ('reading_date', '>=', rec.date_from),
                    ('reading_date', '<=', rec.date_to),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                if last and last.consumption > 0:
                    supplied += last.consumption
            
            for meter in child_meters:
                last = Reading.search([
                    ('meter_id', '=', meter.id),
                    ('reading_date', '>=', rec.date_from),
                    ('reading_date', '<=', rec.date_to),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                if last and last.consumption > 0:
                    consumed += last.consumption
            
            rec.total_supplied_kwh = supplied
            rec.total_consumed_kwh = consumed
            rec.total_loss_kwh = supplied - consumed
            if supplied > 0:
                rec.loss_percentage = (rec.total_loss_kwh / supplied) * 100
            else:
                rec.loss_percentage = 0.0

    def action_print_report(self):
        """طباعة تقرير توازن المحول"""
        return self.env.ref('utility_core.action_report_transformer_balance').report_action(self)

    def action_show_details(self):
        """فتح نافذة تفاصيل القراءات"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'تفاصيل توازن المحول {self.transformer_id.name}',
            'res_model': 'utility.transformer.balance.detail',
            'view_mode': 'tree',
            'target': 'new',
        }
```

#### المرحلة 4: تقرير توازن المحول (QWeb PDF)

**الملف:** `utility_core/report/transformer_balance_report_template.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="report_transformer_balance_document">
        <t t-foreach="doc_ids" t-as="doc_id">
            <t t-set="data" t-value="env['utility.transformer.balance.wizard'].browse(doc_id)"/>
            <div class="page" style="font-family: 'Noto Naskh Arabic', sans-serif; direction: rtl; padding: 20px;">
                <!-- العنوان -->
                <div style="text-align: center; margin-bottom: 20px;">
                    <h2>تقرير توازن المحول</h2>
                    <h3 t-esc="data.transformer_id.name"/>
                </div>

                <!-- معلومات المحول -->
                <table style="width: 100%; margin-bottom: 15px;">
                    <tr>
                        <td><strong>المحول:</strong> <span t-esc="data.transformer_id.name"/></td>
                        <td><strong>الكود:</strong> <span t-esc="data.transformer_id.code"/></td>
                    </tr>
                    <tr>
                        <td><strong>المنطقة:</strong> <span t-esc="data.transformer_id.region_id.name or ''"/></td>
                        <td><strong>المنطقة الفرعية:</strong> <span t-esc="data.transformer_id.area_id.name or ''"/></td>
                    </tr>
                    <tr>
                        <td><strong>من تاريخ:</strong> <span t-esc="data.date_from"/></td>
                        <td><strong>إلى تاريخ:</strong> <span t-esc="data.date_to"/></td>
                    </tr>
                    <tr>
                        <td><strong>السعة:</strong> <span t-esc="data.transformer_id.capacity"/> kVA</td>
                        <td><strong>الفاز:</strong>
                            <t t-if="data.transformer_id.phase == 'single'">أحادي</t>
                            <t t-if="data.transformer_id.phase == 'three'">ثلاثي</t>
                        </td>
                    </tr>
                </table>

                <!-- ملخص الفاقد -->
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                    <h3 style="margin-top: 0;">ملخص الفاقد</h3>
                    <table style="width: 100%;">
                        <tr>
                            <td>الطاقة الموردة (عدادات الربط):</td>
                            <td style="text-align: left;"><strong t-esc="data.total_supplied_kwh"/> kWh</td>
                        </tr>
                        <tr>
                            <td>الطاقة المستهلكة (عدادات المشتركين):</td>
                            <td style="text-align: left;"><strong t-esc="data.total_consumed_kwh"/> kWh</td>
                        </tr>
                        <tr style="border-top: 2px solid #000;">
                            <td>الفاقد:</td>
                            <td style="text-align: left;">
                                <strong t-esc="data.total_loss_kwh"/> kWh
                                (<strong t-esc="data.loss_percentage"/>%)
                            </td>
                        </tr>
                    </table>
                    <!-- إنذار عند تجاوز الحد -->
                    <t t-if="data.loss_percentage > data.show_loss_threshold">
                        <div style="background-color: #dc3545; color: white; padding: 10px; margin-top: 10px; border-radius: 5px;">
                            ⚠️ تجاوز الفاقد الحد المسموح به (<t t-esc="data.show_loss_threshold"/>%)
                        </div>
                    </t>
                </div>

                <!-- عدادات الربط -->
                <h3>عدادات الربط (Coupling Meters)</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
                    <thead>
                        <tr style="background-color: #007bff; color: white;">
                            <th>العداد</th>
                            <th>القراءة السابقة</th>
                            <th>القراءة الحالية</th>
                            <th>الاستهلاك (kWh)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr t-foreach="data.coupling_meter_ids" t-as="meter">
                            <t t-set="reading" t-value="env['utility.reading'].search([
                                ('meter_id', '=', meter.id),
                                ('reading_date', '>=', data.date_from),
                                ('reading_date', '<=', data.date_to),
                                ('state', 'in', ['approved', 'billed']),
                            ], order='reading_date desc', limit=1)"/>
                            <td t-esc="meter.meter_number"/>
                            <td t-esc="reading.previous_reading if reading else 0"/>
                            <td t-esc="reading.reading_value if reading else 0"/>
                            <td t-esc="reading.consumption if reading else 0"/>
                        </tr>
                    </tbody>
                </table>

                <!-- عدادات المشتركين -->
                <h3>عدادات المشتركين (Child Meters)</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #28a745; color: white;">
                            <th>العداد</th>
                            <th>المشترك</th>
                            <th>الخلية</th>
                            <th>القراءة السابقة</th>
                            <th>القراءة الحالية</th>
                            <th>الاستهلاك (kWh)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr t-foreach="data.child_meter_ids" t-as="meter">
                            <t t-set="reading" t-value="env['utility.reading'].search([
                                ('meter_id', '=', meter.id),
                                ('reading_date', '>=', data.date_from),
                                ('reading_date', '<=', data.date_to),
                                ('state', 'in', ['approved', 'billed']),
                            ], order='reading_date desc', limit=1)"/>
                            <td t-esc="meter.meter_number"/>
                            <td t-esc="meter.customer_id.partner_id.name if meter.customer_id else ''"/>
                            <td t-esc="meter.account_id.cell_id.name if meter.account_id and meter.account_id.cell_id else ''"/>
                            <td t-esc="reading.previous_reading if reading else 0"/>
                            <td t-esc="reading.reading_value if reading else 0"/>
                            <td t-esc="reading.consumption if reading else 0"/>
                        </tr>
                    </tbody>
                </table>

                <!-- التوقيعات -->
                <div style="margin-top: 30px;">
                    <table style="width: 100%;">
                        <tr>
                            <td style="text-align: center;">
                                __________________<br/>
                                <strong>المشرف</strong>
                            </td>
                            <td style="text-align: center;">
                                __________________<br/>
                                <strong>المدقق</strong>
                            </td>
                        </tr>
                    </table>
                </div>
            </div>
        </t>
    </template>
</odoo>
```

#### المرحلة 5: إضافة `is_coupling_meter` إلى `utility.meter`

**تعديل `utility_core/models/utility_meter.py`:**

```python
# إضافة حقل التمييز بين عداد الربط وعداد المشترك
is_coupling_meter = fields.Boolean('عداد ربط',
    default=False,
    help='عداد الربط (Coupling Meter) يقيس إجمالي الطاقة الداخلة للمحول')
cell_id = fields.Many2one('utility.transformer.cell', 'الخلية',
    help='الخلية المرتبط بها')
```

### هيكل البيانات النهائي
```
utility.transformer
    │
    ├── is_coupling_meter=True ← عداد الربط (يقيس الدخل)
    │
    ├── utility.transformer.cell (الخلايا)
    │   ├── coupling_meter_id ← عداد الربط لهذه الخلية
    │   ├── utility.account (عقود الخلايا)
    │   │   ├── cell_id → link
    │   │   ├── meter_id ← عداد المشترك
    │   │   └── distribution_percentage ← نسبة التوزيع
    │   └── ...
    │
    └── utility.meter (عدادات المشتركين العادية)
        └── is_coupling_meter=False
```

### تحليل الفاقد
```
الفاقد (kWh) = طاقة عداد الربط - ∑ طاقة عدادات المشتركين
نسبة الفاقد (%) = (الفاقد / طاقة الربط) × 100

مثال:
- عداد الربط: 10,000 kWh
- عدادات المشتركين: 8,500 kWh
- الفاقد: 1,500 kWh (15%)
- إنذار إذا تجاوز 10% ← 15% > 10% ← تحذير أحمر
```

### الملفات (4 جديد + 3 تعديلات)

| الملف | نوع |
|-------|-----|
| `utility_core/models/utility_transformer_cell.py` | **جديد** |
| `utility_core/wizards/transformer_balance_wizard.py` | **جديد** |
| `utility_core/wizards/__init__.py` | **جديد** |
| `utility_core/report/transformer_balance_report_template.xml` | **جديد** |
| `utility_core/report/transformer_balance_report.xml` | **جديد** |
| `utility_core/models/utility_account.py` | **تعديل** (إضافة cell_id, coupling_meter_id) |
| `utility_core/models/utility_meter.py` | **تعديل** (إضافة is_coupling_meter, cell_id) |
| `utility_core/views/utility_transformer_cell_views.xml` | **جديد** |
| `utility_core/views/utility_transformer_views.xml` | **تعديل** (إضافة خلايا tab) |
| `utility_core/views/utility_meter_views.xml` | **تعديل** (إضافة is_coupling_meter, cell_id) |
| `utility_core/security/ir.model.access.csv` | **تعديل** |

---

## 🟡 6. الإعدادات (Settings & Configuration)

### الهدف
صفحة إعدادات شاملة تحت قائمة Configuration تسمح بضبط جميع معاملات النظام.

### التنفيذ - 3 مراحل

#### المرحلة 1: موديل `res.config.settings` (توريث)

**الملف:** `utility_core/models/utility_settings.py`

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- Meter Reading ---
    meter_review_required = fields.Boolean(
        string='مطلوب مراجعة صورة العداد',
        config_parameter='utility.meter_review_required',
        default=True)
    meter_image_mandatory = fields.Boolean(
        string='صورة العداد إلزامية',
        config_parameter='utility.meter_image_mandatory',
        default=False)
    meter_reading_validation = fields.Selection([
        ('none', 'بدون تحقق'),
        ('consumption_diff', 'التحقق من فرق الاستهلاك'),
        ('image_review', 'مراجعة الصورة'),
        ('both', 'كلاهما'),
    ], string='نوع التحقق من القراءة',
       config_parameter='utility.meter_reading_validation',
       default='both')

    # --- Billing & Invoicing ---
    enable_auto_invoice_confirm = fields.Boolean(
        string='تأكيد الفواتير تلقائياً',
        config_parameter='utility.enable_auto_invoice_confirm',
        default=False)
    auto_generate_bills = fields.Boolean(
        string='توليد الفواتير تلقائياً',
        config_parameter='utility.auto_generate_bills',
        default=True)
    billing_due_days = fields.Integer(
        string='أيام الاستحقاق',
        config_parameter='utility.billing_due_days',
        default=30)
    late_penalty_percentage = fields.Float(
        string='نسبة غرامة التأخير (%)',
        config_parameter='utility.late_penalty_percentage',
        default=1.5)

    # --- Transformer ---
    max_transformer_loss_tolerance = fields.Float(
        string='نسبة الفاقد المسموح في المحولات (%)',
        config_parameter='utility.max_transformer_loss_tolerance',
        default=10.0)

    # --- Consumption Alerts ---
    high_consumption_threshold = fields.Float(
        string='حد الاستهلاك العالي (kWh)',
        config_parameter='utility.high_consumption_threshold',
        default=10000.0)
    consumption_variation_alert_percentage = fields.Float(
        string='نسبة التغير المنبهة للاستهلاك (%)',
        config_parameter='utility.consumption_variation_alert_percentage',
        default=50.0)

    # --- Prepaid ---
    emergency_credit_amount = fields.Monetary(
        string='قيمة رصيد الطوارئ الافتراضي',
        config_parameter='utility.emergency_credit_amount',
        currency_field='company_currency_id',
        default=50.0)
    emergency_credit_grace_days = fields.Integer(
        string='فترة سماح رصيد الطوارئ (أيام)',
        config_parameter='utility.emergency_credit_grace_days',
        default=7)
    low_credit_threshold = fields.Monetary(
        string='حد الرصيد المنخفض',
        config_parameter='utility.low_credit_threshold',
        currency_field='company_currency_id',
        default=100.0)

    # --- Auto Pay ---
    max_auto_pay_retries = fields.Integer(
        string='الحد الأقصى لإعادة محاولة الدفع',
        config_parameter='utility.max_auto_pay_retries',
        default=3)

    # --- SMS / Notifications ---
    send_sms_on_invoice = fields.Boolean(
        string='إرسال SMS عند إنشاء الفاتورة',
        config_parameter='utility.send_sms_on_invoice',
        default=False)
    send_sms_on_payment = fields.Boolean(
        string='إرسال SMS عند الدفع',
        config_parameter='utility.send_sms_on_payment',
        default=False)
    send_sms_on_low_credit = fields.Boolean(
        string='إرسال SMS عند انخفاض الرصيد',
        config_parameter='utility.send_sms_on_low_credit',
        default=True)

    # --- Accounting ---
    fine_account_id = fields.Many2one(
        'account.account',
        string='حساب إيرادات الغرامات',
        config_parameter='utility.fine_account_id')
    discount_account_id = fields.Many2one(
        'account.account',
        string='حساب الخصومات',
        config_parameter='utility.discount_account_id')
    deposit_account_id = fields.Many2one(
        'account.account',
        string='حساب التأمينات',
        config_parameter='utility.deposit_account_id')
```

#### المرحلة 2: الواجهة

**الملف:** `utility_core/views/utility_settings_views.xml`

```xml
<odoo>
    <record id="view_utility_config_settings" model="ir.ui.view">
        <field name="name">Utility Settings</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="base.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <div id="base_setting_form" position="before">
                <app data-string="Utility ERP" name="utility">
                    <block title="عدادات وإعدادات القراءة" id="utility_meter">
                        <setting help="مطلوب مراجعة صورة العداد قبل اعتماد القراءة">
                            <field name="meter_review_required"/>
                        </setting>
                        <setting help="صورة العداد إلزامية عند تسجيل القراءة">
                            <field name="meter_image_mandatory"/>
                        </setting>
                        <setting help="طريقة التحقق من صحة قراءة العداد">
                            <field name="meter_reading_validation"/>
                        </setting>
                    </block>
                    <block title="الفوترة والمحاسبة" id="utility_billing">
                        <setting help="تأكيد الفواتير تلقائياً بعد إنشائها">
                            <field name="enable_auto_invoice_confirm"/>
                        </setting>
                        <setting help="توليد الفواتير تلقائياً حسب الدورات">
                            <field name="auto_generate_bills"/>
                        </setting>
                        <setting help="عدد أيام الاستحقاق من تاريخ الفاتورة">
                            <field name="billing_due_days"/>
                        </setting>
                        <setting help="نسبة غرامة التأخير عن السداد">
                            <field name="late_penalty_percentage"/>
                        </setting>
                    </block>
                    <block title="الإنذارات والتنبيهات" id="utility_alerts">
                        <setting help="الحد الأدنى للرصيد الذي يطلق إنذار">
                            <field name="low_credit_threshold"/>
                        </setting>
                    </block>
                    <block title="الحسابات المحاسبية" id="utility_accounts">
                        <setting help="حساب إيرادات الغرامات">
                            <field name="fine_account_id"/>
                        </setting>
                        <setting help="حساب الخصومات">
                            <field name="discount_account_id"/>
                        </setting>
                        <setting help="حساب التأمينات">
                            <field name="deposit_account_id"/>
                        </setting>
                    </block>
                    <block title="المدفوعات التلقائية" id="utility_autopay">
                        <setting help="الحد الأقصى لعدد محاولات إعادة الدفع التلقائي">
                            <field name="max_auto_pay_retries"/>
                        </setting>
                    </block>
                    <block title="رصيد الطوارئ" id="utility_emergency">
                        <setting help="قيمة رصيد الطوارئ الافتراضية">
                            <field name="emergency_credit_amount"/>
                        </setting>
                        <setting help="فترة السماح قبل استرداد رصيد الطوارئ">
                            <field name="emergency_credit_grace_days"/>
                        </setting>
                    </block>
                </app>
            </div>
        </field>
    </record>
</odoo>
```

### ملفات (2 جديد)

| الملف | نوع |
|-------|-----|
| `utility_core/models/utility_settings.py` | جديد |
| `utility_core/views/utility_settings_views.xml` | جديد |

---

## 🟡 6. تكامل account.analytic.account

### الهدف
ربط `utility.account` مع `account.analytic.account` لتكامل محاسبي كامل مع Odoo Accounting.

### التنفيذ - 4 مراحل

#### المرحلة 1: توريث `account.analytic.account`

**الملف:** `utility_core/models/account_analytic_account.py`

```python
class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    utility_account_id = fields.Many2one('utility.account', string='حساب الكهرباء', index=True)
    utility_customer_id = fields.Many2one('utility.customer', related='utility_account_id.customer_id', store=True)
    
    meter_id = fields.Char(related='utility_account_id.meter_id.meter_number', string='رقم العداد', store=True)
    meter_type = fields.Selection(related='utility_account_id.meter_id.meter_type_id.code', string='نوع العداد')
    meter_vastype = fields.Selection(related='utility_account_id.meter_id.phase', string='فاز العداد')
    
    meter_current_reading = fields.Float(compute='_compute_meter_readings', string='القراءة الحالية')
    meter_last_invo_reading = fields.Float(compute='_compute_meter_readings', string='آخر قراءة مفوترة')
    
    region_id = fields.Many2one(related='utility_account_id.region_id', store=True)
    area_id = fields.Many2one(related='utility_account_id.area_id', store=True)
    transformer_id = fields.Many2one(related='utility_account_id.meter_id.transformer_id', string='المحول')
    contract_state = fields.Selection(related='utility_account_id.contract_state', string='حالة الاشتراك')
    
    invoice_count = fields.Integer(compute='_compute_smart_buttons')
    reading_count = fields.Integer(compute='_compute_smart_buttons')
    payment_count = fields.Integer(compute='_compute_smart_buttons')

    def _compute_meter_readings(self):
        """آخر قراءة معتمدة من utility.reading"""
        Reading = self.env['utility.reading']
        for rec in self:
            account = rec.utility_account_id
            if account:
                last = Reading.search([
                    ('account_id', '=', account.id),
                    ('state', 'in', ['approved', 'billed']),
                ], order='reading_date desc', limit=1)
                rec.meter_current_reading = last.reading_value if last else 0.0
                last_bill = self.env['utility.bill'].search([
                    ('account_id', '=', account.id),
                    ('state', 'in', ['confirmed', 'paid']),
                ], order='period_end desc', limit=1)
                rec.meter_last_invo_reading = last_bill.current_reading if last_bill else 0.0
```

#### المرحلة 2: إنشاء analytic account تلقائياً عند إنشاء utility account

**تعديل `utility_core/models/utility_account.py`:** إضافة `analytic_account_id` و `action_create_analytic_account()`

#### المرحلة 3: ربط account.move مع utility bill

**الملف:** `utility_billing/models/account_move.py` - إضافة `utility_bill_id`, `meter_number`, `current_meter_reading`, `consumption_units`, `consumption_alert`

#### المرحلة 4: ربط account.payment مع utility collection

**الملف:** `utility_billing/models/account_payment.py` - إضافة `utility_collection_id`, `utility_payment_method`, `electronic_doc_no`, `is_invoice_verified`

### الملفات (4 جديد + 3 تعديلات)

| الملف | نوع |
|-------|-----|
| `utility_core/models/account_analytic_account.py` | جديد |
| `utility_core/models/utility_account.py` | تعديل |
| `utility_core/views/account_analytic_views.xml` | جديد |
| `utility_billing/models/account_move.py` | جديد |
| `utility_billing/models/account_payment.py` | جديد |
| `utility_billing/views/account_move_views.xml` | جديد |
| `utility_billing/views/account_payment_views.xml` | جديد |

---

## 🟡 8. الأتمتة والكرونات (Crons & Automation)

### الهدف
زيادة عدد الكرونات من 1 إلى 8+ لتغطية جميع احتياجات التشغيل الآلي.

### الكرونات المطلوبة

| # | الكرون | الفاصل | الموديل |
|---|--------|--------|---------|
| 1 | توليد الفواتير المتكررة | كل ساعة | `utility.contract.template` |
| 2 | فحص الأرصدة المنخفضة | كل 30 دقيقة | `utility.account` |
| 3 | تحديث الفواتير المتأخرة | يومياً | `utility.bill` |
| 4 | إعادة محاولة الدفع التلقائي | كل 30 دقيقة | `utility.account` |
| 5 | الفوترة الجماعية للقراءات | يومياً | `utility.reading` |
| 6 | إنشاء تقارير التحصيل الشهرية | شهرياً | `utility.cashier.shift` |
| 7 | احتساب غرامات التأخير | يومياً | `utility.penalty` |
| 8 | إرسال تذكير بالفواتير المستحقة | يومياً | `utility.bill` |

### الملفات (1 جديد + تعديلات في 4 موديلات)

| الملف | نوع |
|-------|-----|
| `utility_billing/data/utility_cron_extras.xml` | جديد (8 كرونات) |
| `utility_core/models/utility_account.py` | تعديل |
| `utility_billing/models/utility_bill.py` | تعديل |
| `utility_billing/models/utility_reading.py` | تعديل |
| `utility_billing/models/utility_penalty.py` | تعديل |

---

## 🟡 8. استبدال العدادات (Meter Replacement)

### الهدف
نظام متكامل لتسجيل استبدال العدادات مع معالج wizard، حساب الاستهلاك غير المفوتّر، وإنشاء قراءات الإغلاق والافتتاح.

### الملفات (2 جديد + 3 تعديلات)

| الملف | نوع |
|-------|-----|
| `utility_operations/models/utility_meter_replacement.py` | جديد |
| `utility_operations/wizards/meter_replace_wizard.py` | جديد |
| `utility_operations/views/meter_replace_views.xml` | جديد |
| `utility_operations/__init__.py` | تعديل |
| `utility_operations/wizards/__init__.py` | جديد |
| `utility_operations/security/ir.model.access.csv` | تعديل |

(انظر التفاصيل الكاملة في GAP_ANALYSIS_PLAN.md)

---

## 🟢 10. التسويات (Settlements)

### الهدف
معالجان لتسوية القراءات (تعديل قراءة خاطئة) والتسوية المالية (غرامات/خصومات).

### الملفات (4 جديد)

| الملف | نوع |
|-------|-----|
| `utility_operations/models/utility_reading_settlement.py` | جديد |
| `utility_operations/wizards/reading_settlement_wizard.py` | جديد |
| `utility_billing/models/utility_financial_settlement.py` | جديد |
| `utility_billing/wizards/financial_settlement_wizard.py` | جديد |
| `utility_operations/views/reading_settlement_views.xml` | جديد |
| `utility_billing/views/financial_settlement_views.xml` | جديد |

---

## 🟢 11. تقارير متقدمة

### الهدف
تقرير توازن المحولات (Transformer Balance Report) + كشف حساب المشترك.

### الملفات (4 جديد)

| الملف | نوع |
|-------|-----|
| `utility_core/models/utility_transformer_report.py` | جديد |
| `utility_core/report/transformer_balance_report_template.xml` | جديد |
| `utility_core/report/transformer_balance_report.xml` | جديد |
| `utility_billing/models/utility_customer_statement.py` | جديد |
| `utility_billing/report/customer_statement_report_template.xml` | جديد |
| `utility_billing/report/customer_statement_report.xml` | جديد |

---

## 🟢 12. توليد الفواتير (تحسين الموجود)

تحديث `utility_billing/models/utility_billing_cycle.py` لاستخدام `state='approved'` (بدلاً من `state='validated'`) مع `_create_bill()` المحسّن.

---

## جدول زمني تقديري

| الأسبوع | المكونات | الملفات |
|---------|----------|---------|
| **الأسبوع 1** | **دورة القراءة** (#2) - صور، مراجعة، اعتماد، فوترة | 5 ملفات |
| **الأسبوع 2** | **فئات المشتركين والخصم** (#4) + العقود المتكررة (#3) | 14 ملف |
| **الأسبوع 3** | Settings (#6) + تكامل analytic.account (#7) | 7 ملفات |
| **الأسبوع 4** | 8 كرونات أتمتة (#8) + تحسين توليد الفواتير (#12) | 5 ملفات |
| **الأسبوع 5** | استبدال العدادات (#9) + التسويات (#10) | 8 ملفات |
| **الأسبوع 6** | تقارير متقدمة (#11) | 6 ملفات |
| **الأسبوع 7** | اختبارات + توثيق | 10+ ملفات |
