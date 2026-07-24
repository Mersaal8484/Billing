from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta


class UtilityDashboardAPI(http.Controller):

    @http.route('/utility/dashboard/kpi', type='json', auth='user')
    def get_kpis(self, region_id=False):
        """
        لوحة قيادة مخصصة حصرياً لبيانات الفوترة والتحصيل الآجل (Postpaid Billing)
        بدون إدخال أي من مبيعات أو معاملات الدفع المسبق (Prepaid/POS).
        """
        today = fields.Date.context_today(request.env.user)
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # 1. Base Postpaid Customer Domain
        customer_domain = [('state', '=', 'active')]
        if region_id:
            customer_domain.append(('region_id', '=', region_id))

        Customer = request.env['utility.customer'].sudo()
        customers = Customer.search(customer_domain)
        partner_ids = customers.mapped('partner_id').ids
        customer_ids = customers.ids
        total_postpaid_customers = len(customers)

        # 2. Today's Postpaid Collections (account.payment posted & inbound)
        postpaid_collections_today = 0.0
        account_payment = request.env.get('account.payment')
        if account_payment is not None and partner_ids:
            pay_domain = [
                ('date', '=', today),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound'),
                ('partner_id', 'in', partner_ids)
            ]
            payments_today = account_payment.sudo().search(pay_domain)
            postpaid_collections_today = sum(payments_today.mapped('amount'))

        # 3. Today's Billed Postpaid Sales (sale.order)
        postpaid_billed_today = 0.0
        sale_order = request.env.get('sale.order')
        if sale_order is not None and customer_ids:
            so_domain = [
                ('create_date', '>=', today_start),
                ('create_date', '<=', today_end),
                ('customer_id', 'in', customer_ids),
                ('state', 'in', ['sale', 'done'])
            ]
            orders_today = sale_order.sudo().search(so_domain)
            postpaid_billed_today = sum(orders_today.mapped('amount_total'))

        # 4. Total Outstanding Debt & Overdue Debt (Postpaid sale.order)
        total_debt = 0.0
        overdue_debt = 0.0
        overdue_count = 0

        if sale_order is not None and customer_ids:
            open_so_domain = [
                ('customer_id', 'in', customer_ids),
                ('bill_state', 'in', ['confirmed', 'sent', 'overdue']),
                ('balance_due', '>', 0)
            ]
            open_orders = sale_order.sudo().search(open_so_domain)
            total_debt = sum(open_orders.mapped('balance_due'))

            overdue_orders = open_orders.filtered(lambda r: r.bill_state == 'overdue' or r.is_overdue)
            overdue_debt = sum(overdue_orders.mapped('balance_due'))
            overdue_count = len(overdue_orders)

        # 5. Last 7 Days Postpaid Billed Sales vs Postpaid Collections
        labels = []
        invoices_data = []
        collections_data = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            labels.append(d.strftime('%Y-%m-%d'))
            d_start = datetime.combine(d, datetime.min.time())
            d_end = datetime.combine(d, datetime.max.time())

            # Billed Sales
            day_billed = 0.0
            if sale_order is not None and customer_ids:
                day_so = sale_order.sudo().search([
                    ('create_date', '>=', d_start),
                    ('create_date', '<=', d_end),
                    ('customer_id', 'in', customer_ids),
                    ('state', 'in', ['sale', 'done'])
                ])
                day_billed = sum(day_so.mapped('amount_total'))
            invoices_data.append(day_billed)

            # Collections
            day_pays = 0.0
            if account_payment is not None and partner_ids:
                day_payments = account_payment.sudo().search([
                    ('date', '=', d),
                    ('state', '=', 'posted'),
                    ('payment_type', '=', 'inbound'),
                    ('partner_id', 'in', partner_ids)
                ])
                day_pays = sum(day_payments.mapped('amount'))
            collections_data.append(day_pays)

        # 6. Region-level Postpaid Performance Rows
        region_rows = []
        if region_id:
            region_groups = Customer.read_group(
                domain=customer_domain,
                fields=['region_id'],
                groupby=['region_id'],
                lazy=False,
            )
        else:
            region_groups = Customer.read_group(
                domain=[('state', '=', 'active')],
                fields=['region_id'],
                groupby=['region_id'],
                lazy=False,
            )

        for group in region_groups:
            region_value = group.get('region_id')
            rid = region_value[0] if region_value else False
            region_name = region_value[1] if region_value else 'غير محدد'

            r_customers = Customer.search([('state', '=', 'active'), ('region_id', '=', rid)])
            r_partner_ids = r_customers.mapped('partner_id').ids
            r_customer_ids = r_customers.ids

            # Today's Collections
            r_postpaid = 0.0
            if account_payment is not None and r_partner_ids:
                r_pays = account_payment.sudo().search([
                    ('date', '=', today),
                    ('state', '=', 'posted'),
                    ('payment_type', '=', 'inbound'),
                    ('partner_id', 'in', r_partner_ids),
                ])
                r_postpaid = sum(r_pays.mapped('amount'))

            # Today's Billed
            r_billed = 0.0
            if sale_order is not None and r_customer_ids:
                r_orders = sale_order.sudo().search([
                    ('create_date', '>=', today_start),
                    ('create_date', '<=', today_end),
                    ('customer_id', 'in', r_customer_ids),
                    ('state', 'in', ['sale', 'done'])
                ])
                r_billed = sum(r_orders.mapped('amount_total'))

            # Total & Overdue Debt
            r_debt = 0.0
            r_overdue = 0.0
            if sale_order is not None and r_customer_ids:
                r_open_orders = sale_order.sudo().search([
                    ('customer_id', 'in', r_customer_ids),
                    ('bill_state', 'in', ['confirmed', 'sent', 'overdue']),
                    ('balance_due', '>', 0)
                ])
                r_debt = sum(r_open_orders.mapped('balance_due'))
                r_overdue = sum(r_open_orders.filtered(lambda r: r.bill_state == 'overdue' or r.is_overdue).mapped('balance_due'))

            region_rows.append({
                'region_id': rid,
                'region_name': region_name,
                'active_customers': len(r_customers),
                'today_postpaid': r_postpaid,
                'today_billed': r_billed,
                'total_debt': r_debt,
                'overdue_debt': r_overdue,
                'partner_ids': r_partner_ids,
            })

        region_rows.sort(key=lambda r: r['total_debt'], reverse=True)

        return {
            'today_postpaid': postpaid_collections_today,
            'today_billed': postpaid_billed_today,
            'total_debt': total_debt,
            'overdue_debt': overdue_debt,
            'overdue_count': overdue_count,
            'active_customers': total_postpaid_customers,
            'chart_labels': labels,
            'chart_invoices': invoices_data,
            'chart_collections': collections_data,
            'region_rows': region_rows,
            'region_chart_labels': [row['region_name'] for row in region_rows],
            'region_chart_customers': [row['active_customers'] for row in region_rows],
            'region_chart_debt': [row['total_debt'] for row in region_rows],
        }
