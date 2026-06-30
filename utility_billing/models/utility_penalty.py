from odoo import api, fields, models, _


class UtilityPenaltyType(models.Model):
    _name = 'utility.penalty.type'
    _description = 'نوع الغرامة'
    _order = 'name'

    name = fields.Char('اسم الغرامة', required=True, translate=True)
    code = fields.Char('الرمز', required=True)
    description = fields.Text('الوصف')
    active = fields.Boolean(default=True)


class UtilityPenalty(models.Model):
    _name = 'utility.penalty'
    _description = 'Utility Penalty'
    _order = 'calculated_date desc'

    name = fields.Char(string="الاسم", compute="_compute_name", store=True)

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    sale_order_id = fields.Many2one('sale.order', 'Sale Order')
    customer_id = fields.Many2one('utility.customer', 'Customer')
    partner_id = fields.Many2one('res.partner', related='customer_id.partner_id', store=True)
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    
    @api.depends('penalty_type_id', 'sale_order_id')
    def _compute_name(self):
        for rec in self:
            if rec.penalty_type_id and rec.sale_order_id:
                rec.name = f"غرامة {rec.penalty_type_id.name} - {rec.sale_order_id.name}"
            else:
                rec.name = "غرامة جديدة"
    penalty_type_id = fields.Many2one('utility.penalty.type', string='Penalty Type', required=True)
    amount = fields.Float('Amount')
    calculated_date = fields.Date('Calculated Date')
    reason = fields.Text('Reason')
    waived = fields.Boolean('Waived', default=False)
    waived_by = fields.Many2one('res.users', 'Waived By')
    state = fields.Selection([
        ('calculated', 'Calculated'),
        ('applied', 'Applied'),
        ('waived', 'Waived'),
    ], string='State', default='calculated')
    
    move_id = fields.Many2one('account.move', string='فاتورة الغرامة', readonly=True)

    def action_apply_penalty(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.state != 'calculated':
                continue
                
            settings = self.env['ir.config_parameter'].sudo()
            penalty_product_id = int(settings.get_param('utility.penalty_product_id', 0))
            
            if not penalty_product_id:
                raise ValidationError('يرجى تحديد منتج الغرامات في إعدادات النظام أولاً.')
                
            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError('لا يوجد عميل مرتبط بحساب الكهرباء.')
                
            move = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': fields.Date.today(),
                'ref': f"غرامة: {rec.name}",
                'invoice_line_ids': [(0, 0, {
                    'product_id': penalty_product_id,
                    'name': rec.reason or rec.name,
                    'price_unit': rec.amount,
                    'quantity': 1.0,
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
        penalty_type = self.env['utility.penalty.type'].search([('code', '=', 'late_payment')], limit=1)
        if not penalty_type:
            penalty_type = self.env['utility.penalty.type'].create({
                'name': 'غرامة تأخير السداد',
                'code': 'late_payment'
            })
            
        overdue_orders = self.env['sale.order'].search([
            ('bill_state', '=', 'overdue'),
            ('balance_due', '>', 0),
        ])
        penalty_percentage = float(self.env['ir.config_parameter'].sudo().get_param('utility.late_penalty_percentage', 1.5))
        for order in overdue_orders:
            already_calculated = self.search([
                ('sale_order_id', '=', order.id),
                ('calculated_date', '=', fields.Date.today()),
                ('penalty_type_id', '=', penalty_type.id)
            ], limit=1)
            if not already_calculated:
                amount = order.balance_due * (penalty_percentage / 100.0)
                if amount > 0:
                    self.create({
                        'sale_order_id': order.id,
                        'customer_id': order.customer_id.id,
                        'account_id': order.customer_id.id,
                        'penalty_type_id': penalty_type.id,
                        'amount': amount,
                        'calculated_date': fields.Date.today(),
                        'reason': f'غرامة تأخير سداد الفاتورة رقم {order.name}',
                        'state': 'calculated',
                    })
                    order.amount_penalty += amount
