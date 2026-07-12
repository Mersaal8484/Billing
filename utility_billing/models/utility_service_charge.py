from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityServiceCharge(models.Model):
    _name = 'utility.service.charge'
    _description = 'رسم خدمة'
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('المرجع', required=True, copy=False, default=lambda self: _('جديد'), index=True)
    date = fields.Date('التاريخ', default=fields.Date.context_today, required=True)
    service_order_id = fields.Many2one(
        'utility.service.order',
        string='أمر الخدمة',
        required=True,
        index=True,
        ondelete='restrict',
        check_company=True,
    )
    account_id = fields.Many2one(
        'utility.customer',
        string='حساب المشترك',
        related='service_order_id.account_id',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='العميل',
        related='account_id.partner_id',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='منتج الرسم',
        required=True,
        domain="[('sale_ok', '=', True)]",
        check_company=True,
    )
    description = fields.Char('الوصف', required=True)
    quantity = fields.Float('الكمية', default=1.0, required=True)
    price_unit = fields.Monetary('سعر الوحدة', required=True, currency_field='currency_id')
    tax_ids = fields.Many2many('account.tax', string='الضرائب', domain="[('type_tax_use', '=', 'sale')]")
    amount_untaxed = fields.Monetary('المبلغ قبل الضريبة', compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary('الضريبة', compute='_compute_amounts', store=True)
    amount_total = fields.Monetary('الإجمالي', compute='_compute_amounts', store=True)
    billing_method = fields.Selection([
        ('none', 'بدون رسم'),
        ('invoice', 'فاتورة عميل'),
        ('direct_payment', 'دفع مباشر'),
        ('next_bill', 'إضافة إلى فاتورة الاستهلاك القادمة'),
    ], string='طريقة التحصيل', default='invoice', required=True)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكد'),
        ('invoiced', 'مفوتر'),
        ('payment_requested', 'طلب دفع'),
        ('paid', 'مسدد'),
        ('deferred', 'مؤجل للفاتورة القادمة'),
        ('reversed', 'معكوس'),
        ('cancelled', 'ملغى'),
    ], string='الحالة', default='draft', index=True)
    invoice_id = fields.Many2one('account.move', string='الفاتورة', readonly=True, copy=False, check_company=True)
    payment_id = fields.Many2one('account.payment', string='الدفع المباشر', copy=False, check_company=True)
    pos_order_id = fields.Many2one('pos.order', string='طلب نقطة البيع', copy=False, check_company=True)
    billing_charge_id = fields.Many2one('sale.order.line', string='بند فاتورة الاستهلاك', copy=False)
    company_id = fields.Many2one(
        'res.company',
        string='الشركة',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='العملة',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        ('positive_quantity', 'CHECK(quantity > 0)', 'يجب أن تكون كمية رسم الخدمة أكبر من صفر.'),
        ('non_negative_price', 'CHECK(price_unit >= 0)', 'لا يمكن أن يكون سعر رسم الخدمة سالباً.'),
    ]

    @api.depends('quantity', 'price_unit', 'tax_ids', 'partner_id', 'product_id', 'currency_id')
    def _compute_amounts(self):
        for charge in self:
            base = charge.quantity * charge.price_unit
            if charge.tax_ids:
                taxes = charge.tax_ids.compute_all(
                    charge.price_unit,
                    currency=charge.currency_id,
                    quantity=charge.quantity,
                    product=charge.product_id,
                    partner=charge.partner_id,
                )
                charge.amount_untaxed = taxes['total_excluded']
                charge.amount_tax = taxes['total_included'] - taxes['total_excluded']
                charge.amount_total = taxes['total_included']
            else:
                charge.amount_untaxed = base
                charge.amount_tax = 0.0
                charge.amount_total = base

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for charge in self:
            if not charge.product_id:
                continue
            charge.description = charge.product_id.display_name
            charge.price_unit = charge.product_id.lst_price
            charge.tax_ids = charge.product_id.taxes_id.filtered(
                lambda tax: tax.company_id == charge.company_id or not tax.company_id
            )

    @api.constrains('billing_method', 'amount_total')
    def _check_billable_amount(self):
        for charge in self:
            if charge.billing_method != 'none' and charge.amount_total <= 0:
                raise ValidationError(_('يجب أن يكون مبلغ رسم الخدمة أكبر من صفر عند اختيار طريقة تحصيل.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('جديد')) == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.service.charge') or _('جديد')
        return super().create(vals_list)

    def action_confirm(self):
        for charge in self:
            if charge.state != 'draft':
                continue
            if charge.billing_method == 'none':
                charge.state = 'paid'
            elif charge.billing_method == 'next_bill':
                charge.state = 'deferred'
            else:
                charge.state = 'confirmed'

    def action_create_invoice(self):
        self.ensure_one()
        if self.billing_method != 'invoice':
            raise UserError(_('إنشاء الفاتورة متاح فقط لطريقة تحصيل "فاتورة عميل".'))
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('فاتورة رسم الخدمة'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_id.id,
                'target': 'current',
            }
        if not self.partner_id:
            raise UserError(_('لا يمكن إنشاء فاتورة بدون عميل مرتبط بحساب المشترك.'))
        if self.state == 'draft':
            self.action_confirm()

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'company_id': self.company_id.id,
            'service_order_id': self.service_order_id.id,
            'service_charge_id': self.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'name': self.description or self.product_id.display_name,
                'quantity': self.quantity,
                'price_unit': self.price_unit,
                'tax_ids': [(6, 0, self.tax_ids.ids)],
            })],
        })
        self.write({'invoice_id': invoice.id, 'state': 'invoiced'})
        return {
            'type': 'ir.actions.act_window',
            'name': _('فاتورة رسم الخدمة'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    def action_open_direct_payment(self):
        self.ensure_one()
        if self.billing_method != 'direct_payment':
            raise UserError(_('الدفع المباشر متاح فقط لطريقة تحصيل "دفع مباشر".'))
        if not self.partner_id:
            raise UserError(_('لا يمكن فتح دفع مباشر بدون عميل مرتبط بحساب المشترك.'))
        if self.state == 'draft':
            self.action_confirm()
        self.state = 'payment_requested'
        return {
            'type': 'ir.actions.act_window',
            'name': _('دفع رسم الخدمة'),
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_partner_id': self.partner_id.id,
                'default_amount': self.amount_total,
                'default_service_order_id': self.service_order_id.id,
                'default_service_charge_id': self.id,
                'default_ref': self.name,
            },
        }

    def action_mark_paid_from_payment(self):
        for charge in self:
            if charge.payment_id and charge.payment_id.state == 'posted':
                charge.state = 'paid'
            elif charge.invoice_id and charge.invoice_id.payment_state in ('paid', 'in_payment'):
                charge.state = 'paid'

    def action_cancel(self):
        for charge in self:
            if charge.invoice_id and charge.invoice_id.state == 'posted':
                raise UserError(_('لا يمكن إلغاء رسم خدمة له فاتورة مرحلة. أنشئ إشعاراً دائناً أولاً.'))
            charge.state = 'cancelled'


