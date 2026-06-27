from odoo import api, fields, models, _


class UtilityContractTemplate(models.Model):
    _inherit = 'utility.contract.template'

    def _prepare_sale_order_data(self, account, reading):
        """تحضير بيانات أمر البيع من العقد والقراءة المعتمدة"""
        tariff = account.tariff_id
        consumption = reading.consumption
        lines = []
        for line in self.line_ids:
            qty = line.quantity
            price = line.specific_price or 0.0
            name = line.name or line.product_id.name
            if line.meter_line_type == 'consumption' and tariff:
                qty = consumption
                price = tariff.price_per_kwh or 0.0
                name = line.name or f'استهلاك ({consumption} kWh × {price})'
            elif line.price_type == 'formula' and line.qty_formula_id:
                category = account.subscriber_category_id
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
            elif line.is_subsidized and account.subscriber_category_id:
                category = account.subscriber_category_id
                if category.subsidized_enabled and consumption > 0:
                    qty, price, name = category._get_subsidized_amount(consumption, tariff)
            if qty or price:
                lines.append((0, 0, {
                    'name': name,
                    'product_uom_qty': qty,
                    'price_unit': price,
                    'is_tax': line.meter_line_type == 'tax',
                }))
        return {
            'partner_id': account.partner_id.id if account.partner_id else self.env.company.partner_id.id,
            'customer_id': account.id,
            'customer_id': account.id,
            'meter_id': account.meter_id.id,
            'reading_id': reading.id,
            'tariff_id': tariff.id if tariff else False,
            'period_start': reading.previous_reading_date.date() if reading.previous_reading_date else fields.Date.today(),
            'period_end': reading.reading_date.date() if reading.reading_date else fields.Date.today(),
            'previous_reading': reading.previous_reading,
            'current_reading': reading.reading_value,
            'consumption': consumption,
            'order_line': lines,
            'bill_state': 'draft',
        }

    def cron_generate_recurring_invoices(self):
        accounts = self.env['utility.customer'].search([
            ('contract_state', '=', 'active'),
            ('contract_template_id', '!=', False),
        ])
        for account in accounts:
            reading = self.env['utility.reading'].search([
                ('account_id', '=', account.id),
                ('state', '=', 'approved'),
            ], order='reading_date desc', limit=1)
            if not reading:
                continue
            order = self.env['sale.order'].create(
                account.contract_template_id._prepare_sale_order_data(account, reading)
            )
            order._calculate_amounts()
            reading.state = 'billed'
            account.write({
                'last_reading_date': reading.reading_date,
                'last_reading_value': reading.reading_value,
                'last_invoice_date': fields.Datetime.now(),
                'last_invoice_reading': reading.reading_value,
            })
