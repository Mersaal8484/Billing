from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityServiceOrder(models.Model):
    _inherit = 'utility.service.order'

    service_product_id = fields.Many2one(
        'product.product',
        string='منتج رسم الخدمة',
        domain="[('sale_ok', '=', True)]",
        check_company=True,
    )
    service_fee = fields.Monetary('رسم الخدمة', currency_field='company_currency_id')
    billing_method = fields.Selection([
        ('none', 'بدون رسم'),
        ('invoice', 'فاتورة عميل'),
        ('direct_payment', 'دفع مباشر'),
        ('next_bill', 'إضافة إلى فاتورة الاستهلاك القادمة'),
    ], string='طريقة تحصيل رسم الخدمة', default='none')
    service_charge_ids = fields.One2many('utility.service.charge', 'service_order_id', string='رسوم الخدمة')
    financial_state = fields.Selection([
        ('not_required', 'غير مطلوب'),
        ('pending_invoice', 'بانتظار الفاتورة'),
        ('pending_payment', 'بانتظار السداد'),
        ('partially_paid', 'مدفوع جزئياً'),
        ('cleared', 'مسوى مالياً'),
        ('reversed', 'معكوس'),
        ('cancelled', 'ملغى'),
    ], string='حالة التسوية المالية', compute='_compute_financial_state', store=True)
    financial_clearance_date = fields.Datetime('تاريخ التسوية المالية', readonly=True, copy=False)
    requires_financial_clearance = fields.Boolean(
        'يتطلب تسوية مالية', compute='_compute_requires_financial_clearance', store=True)
    service_invoice_ids = fields.One2many('account.move', 'service_order_id', string='فواتير الخدمة')
    service_charge_count = fields.Integer('عدد رسوم الخدمة', compute='_compute_service_document_counts')
    invoice_count = fields.Integer('عدد فواتير الخدمة', compute='_compute_service_document_counts')
    payment_count = fields.Integer('عدد مدفوعات الخدمة', compute='_compute_service_document_counts')

    @api.depends('billing_method', 'service_fee')
    def _compute_requires_financial_clearance(self):
        for order in self:
            order.requires_financial_clearance = (
                order.billing_method in ('invoice', 'direct_payment', 'next_bill')
                and order.service_fee > 0
            )

    @api.depends(
        'requires_financial_clearance',
        'state',
        'service_charge_ids.state',
        'service_charge_ids.amount_total',
        'service_charge_ids.invoice_id.payment_state',
        'service_charge_ids.invoice_id.state',
        'service_charge_ids.payment_id.state',
    )
    def _compute_financial_state(self):
        for order in self:
            charges = order.service_charge_ids.filtered(lambda charge: charge.state != 'cancelled')
            if order.state == 'cancelled':
                order.financial_state = 'cancelled'
            elif not order.requires_financial_clearance and not charges:
                order.financial_state = 'not_required'
            elif charges and all(charge.state == 'reversed' for charge in charges):
                order.financial_state = 'reversed'
            elif charges and all(order._is_service_charge_cleared(charge) for charge in charges):
                order.financial_state = 'cleared'
            elif charges and any(order._is_service_charge_cleared(charge) for charge in charges):
                order.financial_state = 'partially_paid'
            elif order.billing_method == 'invoice' and not any(charge.invoice_id for charge in charges):
                order.financial_state = 'pending_invoice'
            else:
                order.financial_state = 'pending_payment'

    def _is_service_charge_cleared(self, charge):
        self.ensure_one()
        if charge.billing_method == 'none':
            return True
        if charge.state == 'paid':
            return True
        if charge.billing_method == 'next_bill' and charge.state == 'deferred':
            return True
        if charge.invoice_id and charge.invoice_id.payment_state in ('paid', 'in_payment'):
            return True
        if charge.payment_id and charge.payment_id.state == 'posted':
            return True
        return False

    @api.depends('service_charge_ids', 'service_charge_ids.payment_id', 'service_invoice_ids')
    def _compute_service_document_counts(self):
        for order in self:
            order.service_charge_count = len(order.service_charge_ids)
            order.invoice_count = len(order.service_invoice_ids)
            order.payment_count = len(order.service_charge_ids.mapped('payment_id'))

    @api.onchange('service_product_id')
    def _onchange_service_product_id(self):
        for order in self:
            if order.service_product_id and not order.service_fee:
                order.service_fee = order.service_product_id.lst_price

    def _prepare_service_charge_vals(self):
        self.ensure_one()
        product = self.service_product_id or self.env.ref(
            'utility_core.utility_product_service_charge', raise_if_not_found=False)
        if not product:
            raise UserError(_('يجب تحديد منتج رسم الخدمة قبل إنشاء الرسم.'))
        return {
            'service_order_id': self.id,
            'product_id': product.id,
            'description': _('%s - %s') % (self.order_number, dict(self._fields['service_type'].selection).get(self.service_type)),
            'quantity': 1.0,
            'price_unit': self.service_fee,
            'billing_method': self.billing_method,
            'company_id': self.company_id.id,
        }

    def action_create_service_charge(self):
        self.ensure_one()
        if not self.requires_financial_clearance:
            raise UserError(_('أمر الخدمة الحالي لا يتطلب إنشاء رسم خدمة.'))
        existing = self.service_charge_ids.filtered(lambda charge: charge.state not in ('cancelled', 'reversed'))
        if existing:
            return self.action_view_service_charges()
        charge = self.env['utility.service.charge'].create(self._prepare_service_charge_vals())
        charge.action_confirm()
        return self.action_view_service_charges()

    def action_create_service_invoice(self):
        self.ensure_one()
        if self.billing_method != 'invoice':
            raise UserError(_('اختر طريقة التحصيل "فاتورة عميل" لإنشاء فاتورة.'))
        charge = self.service_charge_ids.filtered(lambda item: item.state not in ('cancelled', 'reversed'))[:1]
        if not charge:
            self.action_create_service_charge()
            charge = self.service_charge_ids.filtered(lambda item: item.state not in ('cancelled', 'reversed'))[:1]
        return charge.action_create_invoice()

    def action_open_direct_payment(self):
        self.ensure_one()
        if self.billing_method != 'direct_payment':
            raise UserError(_('اختر طريقة التحصيل "دفع مباشر" لفتح مستند الدفع.'))
        charge = self.service_charge_ids.filtered(lambda item: item.state not in ('cancelled', 'reversed'))[:1]
        if not charge:
            self.action_create_service_charge()
            charge = self.service_charge_ids.filtered(lambda item: item.state not in ('cancelled', 'reversed'))[:1]
        return charge.action_open_direct_payment()

    def action_add_to_next_bill(self):
        self.ensure_one()
        if self.billing_method != 'next_bill':
            raise UserError(_('اختر طريقة التحصيل "إضافة إلى فاتورة الاستهلاك القادمة" أولاً.'))
        return self.action_create_service_charge()

    def action_check_financial_clearance(self):
        for order in self:
            order.service_charge_ids.action_mark_paid_from_payment()
            if order.financial_state == 'cleared' and not order.financial_clearance_date:
                order.financial_clearance_date = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('التسوية المالية'),
                'message': _('تم تحديث حالة التسوية المالية لأمر الخدمة.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_service_charges(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('رسوم الخدمة'),
            'res_model': 'utility.service.charge',
            'view_mode': 'tree,form',
            'domain': [('service_order_id', '=', self.id)],
            'context': {'default_service_order_id': self.id},
        }

    def action_view_service_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('فواتير الخدمة'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('service_order_id', '=', self.id)],
            'context': {'default_service_order_id': self.id, 'default_move_type': 'out_invoice'},
        }

    def action_view_service_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('مدفوعات الخدمة'),
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'domain': [('service_order_id', '=', self.id)],
            'context': {'default_service_order_id': self.id},
        }

    def action_complete(self):
        blocked = self.filtered(
            lambda order: order.requires_financial_clearance and order.financial_state != 'cleared')
        if blocked:
            names = ', '.join(blocked.mapped('order_number'))
            raise ValidationError(_('لا يمكن إكمال أوامر الخدمة قبل التسوية المالية: %s') % names)
        return super().action_complete()

