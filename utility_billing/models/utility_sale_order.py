from datetime import date, timedelta
from odoo import api, fields, models, _


class UtilitySaleOrder(models.Model):
    _inherit = 'sale.order'
    _description = 'Utility Bill (Sale Order)'

    customer_id = fields.Many2one('utility.customer', 'الحساب', index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد')
    reading_id = fields.Many2one('utility.reading', 'قراءة العداد', index=True, ondelete='restrict')
    date_range_id = fields.Many2one('date.range', 'فترة الفوترة', index=True)

    meter_image = fields.Binary(related='reading_id.meter_image', string='صورة العداد')
    reading_reviewer = fields.Many2one(related='reading_id.reviewer_id', string='مراجع القراءة')

    period_start = fields.Date('بداية الفترة')
    period_end = fields.Date('نهاية الفترة')
    previous_reading = fields.Float('القراءة السابقة')
    current_reading = fields.Float('القراءة الحالية')
    consumption = fields.Float('الاستهلاك')
    tariff_id = fields.Many2one('utility.tariff', 'التعرفة')

    amount_energy = fields.Float('قيمة الطاقة')
    amount_fixed = fields.Float('الرسم الثابت')
    amount_service = fields.Float('رسم الخدمة')
    amount_penalty = fields.Float('الغرامات')

    amount_paid = fields.Float('المدفوع', compute='_compute_payment', store=True)
    balance_due = fields.Float('المتبقي', compute='_compute_payment', store=True)
    is_overdue = fields.Boolean('متأخر', compute='_compute_payment', store=True)

    bill_state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('sent', 'مرسلة'),
        ('paid', 'مدفوعة'),
        ('overdue', 'متأخرة'),
        ('cancelled', 'ملغاة'),
    ], string='حالة الفاتورة', default='draft', tracking=True)

    @api.depends('amount_total', 'amount_paid')
    def _compute_payment(self):
        for r in self:
            paid = sum(r.invoice_ids.filtered(lambda i: i.state == 'paid').mapped('amount_total'))
            if not paid:
                paid = 0.0
            r.amount_paid = paid
            r.balance_due = r.amount_total - paid
            r.is_overdue = r.bill_state not in ('paid', 'cancelled') and r.balance_due > 0 and r.date_order and r.date_order.date() < date.today()

    def _calculate_amounts(self):
        self.ensure_one()
        tariff = self.tariff_id
        account = self.customer_id
        category = account.subscriber_category_id if account else False
        consumption = self.consumption
        lines = []
        template = account.contract_template_id if account else False
        self.amount_energy = 0.0
        self.amount_fixed = 0.0
        self.amount_service = 0.0
        if template:
            for line in template.line_ids:
                qty = line.quantity
                price = line.specific_price or 0.0
                name = line.name or ''
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
                elif line.is_subsidized and category and category.subsidized_enabled and consumption > 0:
                    qty, price, name = category._get_subsidized_amount(consumption, tariff)
                amount = qty * price
                lines.append((0, 0, {
                    'name': name,
                    'product_uom_qty': qty,
                    'price_unit': price,
                    'is_tax': line.meter_line_type == 'tax',
                }))
                if line.meter_line_type == 'consumption':
                    self.amount_energy += amount
                elif line.meter_line_type == 'fixed_fee':
                    self.amount_fixed += amount
                elif line.meter_line_type == 'service_charge':
                    self.amount_service += amount
        else:
            if tariff and tariff.price_per_kwh and consumption > 0:
                energy_amount = consumption * tariff.price_per_kwh
                self.amount_energy = energy_amount
                lines.append((0, 0, {
                    'name': f'استهلاك ({consumption} kWh × {tariff.price_per_kwh})',
                    'product_uom_qty': consumption,
                    'price_unit': tariff.price_per_kwh,
                }))
            if tariff and tariff.fixed_charge:
                self.amount_fixed = tariff.fixed_charge
                lines.append((0, 0, {
                    'name': 'رسم ثابت',
                    'product_uom_qty': 1,
                    'price_unit': tariff.fixed_charge,
                }))
            if tariff and tariff.service_charge:
                self.amount_service = tariff.service_charge
                lines.append((0, 0, {
                    'name': 'رسم خدمة',
                    'product_uom_qty': 1,
                    'price_unit': tariff.service_charge,
                }))
        if tariff and tariff.tax_percentage:
            tax_amount = (self.amount_energy + self.amount_fixed + self.amount_service) * (tariff.tax_percentage / 100.0)
            lines.append((0, 0, {
                'name': f'ضريبة ({tariff.tax_percentage}%)',
                'product_uom_qty': 1,
                'price_unit': tax_amount,
                'is_tax': True,
            }))
        self.order_line = [(5, 0, 0)] + lines

    @api.model
    def cron_update_overdue_orders(self):
        today = date.today()
        orders = self.search([
            ('bill_state', 'not in', ('paid', 'cancelled', 'overdue')),
            ('date_order', '<', today),
            ('balance_due', '>', 0),
        ])
        orders.write({'bill_state': 'overdue'})

    @api.model
    def cron_send_due_reminders(self):
        pass


class UtilitySaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _description = 'Utility Bill Line'

    is_tax = fields.Boolean('ضريبة', default=False)
