from odoo import api, fields, models, _


class UtilityContractTemplate(models.Model):
    _inherit = 'utility.contract.template'

    def _prepare_bill_data(self, account, reading):
        """تحضير بيانات الفاتورة من العقد والقراءة المعتمدة"""
        tariff = account.tariff_id
        consumption = reading.consumption
        lines = []
        
        for line in self.line_ids:
            qty = line.quantity
            price = line.specific_price or 0.0
            name = line.name or line.product_id.name
            
            # 1. منطق الفوترة من التعرفة للاستهلاك
            if line.meter_line_type == 'consumption' and tariff:
                qty = consumption
                price = tariff.price_per_kwh or 0.0
                name = line.name or f'استهلاك ({consumption} kWh × {price})'
            # 2. منطق المعادلات الديناميكية
            elif line.price_type == 'formula' and line.qty_formula_id:
                category = account.customer_id.subscriber_category_id
                qty, computed_name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=reading.previous_reading,
                    current_reading=reading.reading_value,
                    tariff=tariff,
                    account=account,
                    category=category,
                    line=line,
                )
                if computed_name:
                    name = computed_name
            # 3. منطق الخصم المدعوم
            elif line.is_subsidized and account.customer_id.subscriber_category_id:
                category = account.customer_id.subscriber_category_id
                if category.subsidized_enabled and consumption > 0:
                    qty, price, name = category._get_subsidized_amount(consumption, tariff)
            
            # إضافة البند فقط إذا كانت الكمية أو السعر غير صفريين
            if qty or price:
                lines.append((0, 0, {
                    'name': name,
                    'quantity': qty,
                    'unit': 'kWh' if line.meter_line_type == 'consumption' else 'شهر',
                    'unit_price': price,
                    'amount': qty * price,
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
            'state': 'draft',
        }

    def cron_generate_recurring_invoices(self):
        """إنشاء فواتير للحسابات التي لديها عقود نشطة وقراءات معتمدة غير مفوترة"""
        accounts = self.env['utility.customer'].search([
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
            
            # تحديث حالة القراءة لتكون مفوترة
            reading.state = 'billed'
            
            # تحديث تواريخ الحساب القراءة
            account.write({
                'last_reading_date': reading.reading_date,
                'last_reading_value': reading.reading_value,
                'last_invoice_date': fields.Datetime.now(),
                'last_invoice_reading': reading.reading_value,
            })
