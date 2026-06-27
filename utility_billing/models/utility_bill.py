from datetime import date, timedelta
from odoo import api, fields, models, _


class UtilityBill(models.Model):
    _name = 'utility.bill'
    _description = 'Utility Bill'
    _inherit = ['mail.thread']
    _order = 'bill_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    bill_number = fields.Char('Bill Number', required=True, index=True, default=lambda self: _('New'))
    customer_id = fields.Many2one('utility.customer', 'Customer/Contract', required=True, index=True)
    account_id = fields.Many2one('utility.customer', 'Account', index=True)
    meter_id = fields.Many2one('utility.meter', 'Meter')
    billing_cycle_id = fields.Many2one('utility.billing.cycle', 'Billing Cycle')
    bill_date = fields.Date('Bill Date', default=fields.Date.today)
    period_start = fields.Date('Period Start')
    period_end = fields.Date('Period End')
    due_date = fields.Date('Due Date')
    previous_reading = fields.Float('Previous Reading')
    current_reading = fields.Float('Current Reading')
    consumption = fields.Float('Consumption')
    tariff_id = fields.Many2one('utility.tariff', 'Tariff')
    line_ids = fields.One2many('utility.bill.line', 'bill_id', string='Bill Lines')
    amount_energy = fields.Float('Energy Amount')
    amount_fixed = fields.Float('Fixed Charge')
    amount_service = fields.Float('Service Charge')
    amount_tax = fields.Float('Tax Amount')
    amount_penalty = fields.Float('Penalty Amount')
    amount_total = fields.Float('Total Amount')
    amount_paid = fields.Float('Amount Paid')
    balance_due = fields.Float('Balance Due', compute='_compute_balance_due', store=True)
    is_overdue = fields.Boolean('Is Overdue', compute='_compute_is_overdue', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft')
    invoice_id = fields.Many2one('account.move', 'Invoice')
    notes = fields.Text('Notes')

    # الربط مع القراءة
    reading_id = fields.Many2one('utility.reading', 'قراءة العداد', index=True, ondelete='restrict')
    meter_image = fields.Binary(related='reading_id.meter_image', string='صورة العداد')
    reading_reviewer = fields.Many2one(related='reading_id.reviewer_id', string='مراجع القراءة')

    _sql_constraints = [
        ('unique_bill_number_company', 'unique(bill_number, company_id)',
         'Bill number must be unique per company!'),
    ]

    @api.depends('amount_total', 'amount_paid')
    def _compute_balance_due(self):
        for r in self:
            r.balance_due = r.amount_total - r.amount_paid

    @api.depends('state', 'due_date', 'amount_paid', 'amount_total')
    def _compute_is_overdue(self):
        today = date.today()
        for r in self:
            if r.state not in ('paid', 'cancelled') and r.due_date and r.due_date < today:
                if r.amount_paid < r.amount_total:
                    r.is_overdue = True
                else:
                    r.is_overdue = False
            else:
                r.is_overdue = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('bill_number', _('New')) == _('New'):
                vals['bill_number'] = self.env['ir.sequence'].next_by_code('utility.bill') or _('New')
        return super().create(vals_list)

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
        
        # تهيئة المبالغ
        self.amount_energy = 0.0
        self.amount_fixed = 0.0
        self.amount_service = 0.0
        self.amount_tax = 0.0
        
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
                elif line.meter_line_type == 'tax':
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
        
        self.line_ids = [(5, 0, 0)] + line_vals  # مسح البنود السابقة وإضافة الجديدة
        self.amount_total = subtotal + self.amount_tax

    @api.model
    def cron_update_overdue_bills(self):
        today = date.today()
        bills = self.search([
            ('state', 'not in', ('paid', 'cancelled', 'overdue')),
            ('due_date', '<', today),
        ])
        for bill in bills:
            if bill.balance_due > 0:
                bill.state = 'overdue'

    @api.model
    def cron_send_due_bill_reminders(self):
        pass

