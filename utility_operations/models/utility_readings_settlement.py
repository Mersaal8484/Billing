from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class UtilityReadingSettlement(models.Model):
    _name = 'utility.reading.settlement'
    _description = 'سجل تسويات القراءات'
    _order = 'adjustment_date desc'

    name = fields.Char('رقم التسوية', default=lambda self: _('New'), readonly=True)
    reading_id = fields.Many2one('utility.reading', 'القراءة المستهدفة', required=True)
    meter_id = fields.Many2one('utility.meter', related='reading_id.meter_id', store=True)
    account_id = fields.Many2one('utility.customer', related='reading_id.account_id', store=True)
    sale_order_id = fields.Many2one('sale.order', 'فاتورة الكهرباء المرتبطة',
                                     compute='_compute_sale_order_id', store=True)

    old_value = fields.Float('القراءة القديمة', readonly=True)
    new_value = fields.Float('القراءة الجديدة المعدلة', required=True)
    old_consumption = fields.Float('الاستهلاك القديم', readonly=True)
    new_consumption = fields.Float('الاستهلاك الجديد', compute='_compute_new_consumption')

    adjusted_by = fields.Many2one('res.users', 'تمت التسوية بواسطة',
                                   default=lambda self: self.env.user, readonly=True)
    adjustment_date = fields.Date('تاريخ التسوية', default=fields.Date.today, readonly=True)
    reason = fields.Text('سبب التعديل والتسوية', required=True)

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('done', 'تمت التسوية'),
    ], string='الحالة', default='draft', readonly=True)

    # FIX-8: ربط المستند التصحيحي الناتج
    correction_move_id = fields.Many2one(
        'account.move', 'مستند التصحيح', readonly=True,
        help='إشعار الدائن أو فاتورة فرق الناتجة عن التسوية'
    )

    @api.depends('reading_id')
    def _compute_sale_order_id(self):
        for r in self:
            if r.reading_id:
                order = self.env['sale.order'].search([
                    ('reading_id', '=', r.reading_id.id),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                r.sale_order_id = order.id if order else False

    @api.depends('new_value', 'reading_id.previous_reading')
    def _compute_new_consumption(self):
        for r in self:
            if r.reading_id:
                r.new_consumption = r.new_value - (r.reading_id.previous_reading or 0.0)

    @api.onchange('reading_id')
    def _onchange_reading_id(self):
        if self.reading_id:
            self.old_value = self.reading_id.reading_value
            self.old_consumption = self.reading_id.consumption

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.reading.settlement') or _('New')
        return super().create(vals_list)

    def action_apply_settlement(self):
        self.ensure_one()
        if self.state == 'done':
            raise ValidationError('هذه التسوية مكتملة بالفعل!')
        if self.reading_id.state != 'billed':
            raise ValidationError(
                'يمكن تعديل القراءات المفوترة فقط عبر التسوية! الحالة الحالية: %s'
                % self.reading_id.state)

        old_value = self.reading_id.reading_value
        old_consumption = self.reading_id.consumption
        self.old_value = old_value
        self.old_consumption = old_consumption

        # تحديث قيمة القراءة عبر السياق الآمن
        self.reading_id.with_context(_bypass_reading_protection=True).write({
            'reading_value': self.new_value,
        })

        new_consumption = self.new_value - (self.reading_id.previous_reading or 0.0)
        delta_consumption = new_consumption - old_consumption

        # ── FIX-8: إنشاء مستند تصحيحي بدلاً من تعديل فاتورة مرحّلة ─────────
        correction_move = None
        if self.sale_order_id:
            order = self.sale_order_id
            posted_invoices = order.invoice_ids.filtered(lambda i: i.state == 'posted')

            if posted_invoices and delta_consumption != 0:
                # احسب تأثير الفرق بناءً على سعر الوحدة من آخر فاتورة مرحّلة
                last_invoice = posted_invoices[0]
                # ابحث عن بند الاستهلاك في الفاتورة
                energy_line = last_invoice.invoice_line_ids.filtered(
                    lambda l: l.product_id and l.price_unit > 0 and l.quantity > 0
                )
                unit_price = energy_line[0].price_unit if energy_line else 0.0

                if unit_price > 0:
                    diff_amount = abs(delta_consumption * unit_price)
                    partner = order.partner_id

                    if delta_consumption < 0:
                        # الاستهلاك الجديد أقل → أنشئ إشعار دائن (credit note) لصالح العميل
                        move_type = 'out_refund'
                        ref_label = _('إشعار دائن - تسوية قراءة: %s') % self.name
                    else:
                        # الاستهلاك الجديد أكبر → فاتورة إضافية على العميل
                        move_type = 'out_invoice'
                        ref_label = _('فاتورة فرق - تسوية قراءة: %s') % self.name

                    correction_move = self.env['account.move'].create({
                        'move_type': move_type,
                        'partner_id': partner.id,
                        'invoice_date': fields.Date.today(),
                        'ref': ref_label,
                        'utility_sale_order_id': order.id,
                        'invoice_line_ids': [(0, 0, {
                            'name': _(
                                'تسوية استهلاك: من %.2f إلى %.2f كيلووات / سبب: %s'
                            ) % (old_consumption, new_consumption, self.reason),
                            'price_unit': diff_amount,
                            'quantity': 1.0,
                            'product_id': energy_line[0].product_id.id if energy_line else False,
                            'account_id': energy_line[0].account_id.id if energy_line else False,
                        })]
                    })
                    correction_move.action_post()
                    _logger.info(
                        'Settlement %s: created %s %s for order %s (delta=%.2f)',
                        self.name, move_type, correction_move.name, order.name, delta_consumption
                    )
            elif not posted_invoices and order.state in ('draft', 'sent'):
                # الفاتورة لم تُرحَّل بعد — يمكن إعادة الحساب مباشرة
                try:
                    order._calculate_amounts()
                except Exception as e:
                    _logger.warning('Settlement %s: could not recalculate order %s: %s', self.name, order.name, e)

        # تسجيل الحدث في السجل
        msg = _(
            'تسوية قراءة: %.2f ← %.2f (الفرق: %+.2f)\n'
            'الاستهلاك: %.2f ← %.2f kWh\n'
            'السبب: %s\n'
            'الفاتورة المرتبطة: %s\n'
            'المستند التصحيحي: %s'
        ) % (
            old_value, self.new_value, self.new_value - old_value,
            old_consumption, new_consumption,
            self.reason,
            self.sale_order_id.name if self.sale_order_id else '—',
            correction_move.name if correction_move else 'لا يوجد (فرق = 0 أو فاتورة غير مرحّلة)',
        )
        self.reading_id.message_post(body=msg)

        self.write({
            'state': 'done',
            'correction_move_id': correction_move.id if correction_move else False,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'تسوية القراءة',
                'message': 'تم تطبيق تسوية القراءة بنجاح.%s' % (
                    _(' تم إنشاء مستند تصحيحي: %s') % correction_move.name
                    if correction_move else ''
                ),
                'type': 'success',
                'sticky': False,
            }
        }
