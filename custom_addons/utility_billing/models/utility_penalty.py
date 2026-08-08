from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityPenaltyType(models.Model):
    _name = 'utility.penalty.type'
    _description = 'نوع الغرامة'
    _order = 'name'

    name = fields.Char('اسم الغرامة', required=True, translate=True)
    code = fields.Char('الرمز', required=True)
    description = fields.Text('الوصف')
    active = fields.Boolean('نشط', default=True)


class UtilityPenalty(models.Model):
    _name = 'utility.penalty'
    _description = 'غرامة'
    _rec_name = 'name'
    _order = 'calculated_date desc'

    name = fields.Char(string="الاسم", compute="_compute_name", store=True)

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    sale_order_id = fields.Many2one('sale.order', 'أمر البيع', index=True)
    customer_id = fields.Many2one('utility.customer', 'العميل')
    partner_id = fields.Many2one('res.partner', related='customer_id.partner_id', store=True)
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    currency_id = fields.Many2one(
        'res.currency',
        related='sale_order_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )

    @api.depends('penalty_type_id', 'sale_order_id')
    def _compute_name(self):
        for rec in self:
            if rec.penalty_type_id and rec.sale_order_id:
                rec.name = f"غرامة {rec.penalty_type_id.name} - {rec.sale_order_id.name}"
            else:
                rec.name = "غرامة جديدة"

    penalty_type_id = fields.Many2one('utility.penalty.type', string='نوع الغرامة', required=True)
    amount = fields.Monetary('المبلغ', currency_field='currency_id')
    calculated_date = fields.Date('تاريخ الحساب')
    reason = fields.Text('السبب')
    waived = fields.Boolean('تم الإعفاء', default=False)
    waived_by = fields.Many2one('res.users', 'أعفى بواسطة')
    state = fields.Selection([
        ('calculated', 'محتسبة'),
        ('applied', 'مُطبّقة'),
        ('waived', 'مُعفاة'),
    ], string='الحالة', default='calculated')

    move_id = fields.Many2one('account.move', string='فاتورة الغرامة', readonly=True)

    def _get_company_config(self, company_field, config_key, default=0):
        company = self.env.company
        val = company[company_field]
        if val:
            return val.id if hasattr(val, 'id') else val
        return int(self.env['ir.config_parameter'].sudo().get_param(config_key, default))

    def action_apply_penalty(self):
        for rec in self:
            if rec.state != 'calculated':
                continue

            penalty_product_id = rec._get_company_config('penalty_product_id', 'utility.penalty_product_id')

            if not penalty_product_id:
                raise ValidationError('يرجى تحديد منتج الغرامات في إعدادات النظام أولاً.')

            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError('لا يوجد عميل مرتبط بحساب الكهرباء.')

            penalty_account_id = rec._get_company_config('fine_account_id', 'utility.fine_account_id')
            product = self.env['product.product'].browse(penalty_product_id)
            account_id = (
                penalty_account_id
                or product.property_account_income_id.id
                or product.categ_id.property_account_income_categ_id.id
            )
            if not account_id:
                raise ValidationError(
                    'لم يتم تحديد حساب محاسبي للغرامات. يرجى ضبطه في الإعدادات '
                    '(حساب إيرادات الغرامات) أو على المنتج.')

            move = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': fields.Date.today(),
                'ref': f"غرامة: {rec.name}",
                'utility_sale_order_id': rec.sale_order_id.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': penalty_product_id,
                    'name': rec.reason or rec.name,
                    'price_unit': rec.amount,
                    'quantity': 1.0,
                    'account_id': account_id,
                })]
            })
            move.action_post()

            rec.write({
                'state': 'applied',
                'move_id': move.id,
            })

    def action_waive_penalty(self):
        for rec in self:
            if rec.state == 'calculated':
                rec.write({
                    'state': 'waived',
                    'waived': True,
                    'waived_by': self.env.user.id
                })

    @api.model
    def cron_calculate_late_penalties(self):
        """
        كرون حساب غرامات التأخير للفواتير المتأخرة.

        FIX-7: حد أقصى للغرامات المتراكمة = utility.max_penalty_percentage % من مبلغ الفاتورة الأصلي (افتراضي: 30%)
        """
        ICP = self.env['ir.config_parameter'].sudo()
        batch_size = int(ICP.get_param('utility.penalty_batch_size', 500))
        penalty_percentage = float(ICP.get_param('utility.late_penalty_percentage', 1.5))
        max_penalty_pct = float(ICP.get_param('utility.max_penalty_percentage', 30.0))

        penalty_type = self.env['utility.penalty.type'].search([('code', '=', 'late_payment')], limit=1)
        if not penalty_type:
            penalty_type = self.env['utility.penalty.type'].create({
                'name': 'غرامة السداد',
                'code': 'late_payment',
            })

        overdue_orders = self.env['sale.order'].sudo().search([
            ('bill_state', '=', 'overdue'),
            ('balance_due', '>', 0),
        ], limit=batch_size)

        if not overdue_orders:
            return

        order_ids = overdue_orders.ids
        today = fields.Date.today()

        already_penalized = {
            p['sale_order_id'][0]
            for p in self.search_read([
                ('sale_order_id', 'in', order_ids),
                ('calculated_date', '=', today),
                ('penalty_type_id', '=', penalty_type.id),
            ], fields=['sale_order_id'])
        }

        existing_penalty_data = self.read_group([
            ('sale_order_id', 'in', order_ids),
            ('penalty_type_id', '=', penalty_type.id),
            ('state', 'in', ['calculated', 'applied']),
        ], ['sale_order_id'], ['amount:sum'])
        accumulated_map = {
            item['sale_order_id'][0]: item['amount_sum']
            for item in existing_penalty_data
        }

        order_map = {o.id: o for o in overdue_orders}
        penalties_to_create = []

        for order_id in order_ids:
            if order_id in already_penalized:
                continue

            order = order_map[order_id]
            total_accumulated = accumulated_map.get(order_id, 0.0)
            original_amount = order.amount_total
            max_allowed = original_amount * (max_penalty_pct / 100.0)

            if total_accumulated >= max_allowed:
                continue

            amount = order.balance_due * (penalty_percentage / 100.0)
            amount = min(amount, max_allowed - total_accumulated)

            if amount > 0:
                penalties_to_create.append({
                    'sale_order_id': order_id,
                    'customer_id': order.customer_id.id,
                    'penalty_type_id': penalty_type.id,
                    'amount': amount,
                    'calculated_date': today,
                    'reason': 'غرامة سداد الفاتورة رقم %s' % order.name,
                    'state': 'calculated',
                })

        if penalties_to_create:
            self.sudo().create(penalties_to_create)
