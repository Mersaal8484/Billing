from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityReadingSettlement(models.Model):
    _inherit = 'utility.reading.settlement'

    sale_order_id = fields.Many2one(
        'sale.order', 'فاتورة الكهرباء المرتبطة',
        compute='_compute_sale_order_id', store=True,
    )
    billing_adjustment_id = fields.Many2one(
        'utility.billing.adjustment', 'تعديل الفوترة المالي المرتبط',
        readonly=True, copy=False,
    )

    @api.depends('reading_id')
    def _compute_sale_order_id(self):
        for record in self:
            record.sale_order_id = False
            if record.reading_id:
                order = self.env['sale.order'].search([
                    ('reading_id', '=', record.reading_id.id),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                record.sale_order_id = order.id if order else False

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Electricity Bill'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _on_settlement_processed(self):
        """Override hook from utility_operations:
        When technical reading settlement is processed, automatically instantiate
        a utility.billing.adjustment if a posted invoice exists for the related bill.
        """
        super()._on_settlement_processed()
        for rec in self:
            if not rec.sale_order_id:
                continue
            order = rec.sale_order_id
            invoice = self.env['account.move'].search([
                ('utility_sale_order_id', '=', order.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
            ], limit=1)
            if not invoice:
                continue

            existing_adj = self.env['utility.billing.adjustment'].search([
                ('invoice_id', '=', invoice.id),
                ('state', 'in', ('draft', 'submitted', 'approved', 'applied')),
            ], limit=1)
            if existing_adj:
                rec.billing_adjustment_id = existing_adj.id
                continue

            adj = self.env['utility.billing.adjustment'].create({
                'customer_id': rec.account_id.id,
                'billing_period_id': order.date_range_id.id,
                'sale_order_id': order.id,
                'invoice_id': invoice.id,
                'adjustment_type': 'reading_correction',
                'corrected_current_reading': rec.corrected_reading_value,
                'corrected_consumption': rec.corrected_consumption,
                'reason': _('تسوية تقنية للقراءة %s: %s') % (rec.name, rec.reason or ''),
                'rebill': True,
            })
            rec.billing_adjustment_id = adj.id
            rec.message_post(body=_(
                'تم إنشاء طلب تعديل الفوترة المالي المرتبط: %s.'
            ) % adj.name)
