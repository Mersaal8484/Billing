from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityBillReadingComponent(models.Model):
    _name = 'utility.bill.reading.component'
    _description = 'مكون استهلاك فاتورة الكهرباء'
    _order = 'period_start, id'

    sale_order_id = fields.Many2one(
        'sale.order', 'الفاتورة', required=True, index=True,
        ondelete='cascade', check_company=True)
    reading_id = fields.Many2one(
        'utility.reading', 'القراءة', required=True, index=True,
        ondelete='restrict', check_company=True)
    account_id = fields.Many2one(
        'utility.customer', 'حساب المشترك', required=True, index=True,
        ondelete='restrict', check_company=True)
    meter_id = fields.Many2one(
        'utility.meter', 'العداد', required=True, index=True,
        ondelete='restrict', check_company=True)
    reading_purpose = fields.Selection(related='reading_id.reading_purpose', store=True)
    period_start = fields.Datetime('بداية المقطع')
    period_end = fields.Datetime('نهاية المقطع', required=True)
    previous_reading = fields.Float('القراءة السابقة')
    current_reading = fields.Float('القراءة الحالية')
    meter_multiplier = fields.Float('معامل الضرب', required=True, default=1.0)
    consumption = fields.Float('الاستهلاك', required=True)
    company_id = fields.Many2one(
        'res.company', 'الشركة', required=True, index=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('unique_order_reading', 'unique(sale_order_id, reading_id)',
         'لا يمكن إضافة القراءة نفسها مرتين إلى الفاتورة.'),
    ]

    # States in which the parent sale.order is considered confirmed/immutable
    _IMMUTABLE_ORDER_STATES = frozenset({'sale', 'done', 'cancel'})

    @api.constrains('sale_order_id', 'reading_id', 'account_id', 'company_id')
    def _check_component_consistency(self):
        """Keep every snapshot in the same account and company as its bill."""
        for component in self:
            if component.sale_order_id.customer_id != component.account_id:
                raise ValidationError(_('حساب مكون القراءة لا يطابق حساب الفاتورة.'))
            if component.reading_id.account_id != component.account_id:
                raise ValidationError(_('حساب القراءة لا يطابق حساب مكون الفاتورة.'))
            if component.sale_order_id.company_id != component.company_id:
                raise ValidationError(_('شركة مكون القراءة لا تطابق شركة الفاتورة.'))

    def _check_component_immutability(self):
        """Block write/unlink on components belonging to a confirmed order.

        Authorization hierarchy:
          1. If the parent order is still draft/sent → always allowed.
          2. If the parent order is confirmed (sale/done/cancel):
             a. Context flag ``_allow_bill_component_regen`` AND ``env.su``
                (i.e., the call is coming via ``sudo()`` from trusted server
                code — NOT passable from an RPC/JSON call alone) → allowed.
             b. Otherwise → ValidationError.
        """
        for comp in self:
            if comp.sale_order_id.state not in self._IMMUTABLE_ORDER_STATES:
                continue  # Draft / sent bills are editable

            # Admin bypass: requires BOTH the context flag AND a sudo context.
            # env.su is True only when the ORM is in superuser mode (sudo()),
            # which cannot be set by a client RPC call.
            if (self.env.context.get('_allow_bill_component_regen')
                    and self.env.su):
                continue

            raise ValidationError(_(
                'مكونات القراءة في فاتورة مؤكدة أو منتهية أو ملغاة لا يمكن تعديلها أو حذفها.\n'
                'استخدم مستند تصحيح الفوترة (utility.billing.adjustment) لتصحيح الفاتورة.'
            ))

    def write(self, vals):
        self._check_component_immutability()
        return super().write(vals)

    def unlink(self):
        self._check_component_immutability()
        return super().unlink()

