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
