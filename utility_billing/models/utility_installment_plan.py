from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityInstallmentPlan(models.Model):
    _name = 'utility.installment.plan'
    _description = 'خطة تقسيط فاتورة كهرباء'
    _order = 'create_date desc, id desc'

    name = fields.Char('رقم الخطة', required=True, default=lambda self: _('New'), copy=False, readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='الفاتورة', required=True, ondelete='restrict', index=True)
    customer_id = fields.Many2one('utility.customer', string='الحساب', related='sale_order_id.customer_id', store=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='المشترك', related='sale_order_id.partner_id', store=True, readonly=True)
    amount_total = fields.Float('إجمالي التقسيط', required=True)
    installment_count = fields.Integer('عدد الأقساط', default=3, required=True)
    start_date = fields.Date('تاريخ أول قسط', default=fields.Date.context_today, required=True)
    line_ids = fields.One2many('utility.installment.plan.line', 'plan_id', string='الأقساط')
    paid_amount = fields.Float('المدفوع', compute='_compute_amounts')
    remaining_amount = fields.Float('المتبقي', compute='_compute_amounts')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('active', 'نشطة'),
        ('paid', 'مدفوعة'),
        ('cancelled', 'ملغاة'),
    ], default='draft', string='الحالة', tracking=True)

    @api.constrains('amount_total', 'installment_count')
    def _check_plan_values(self):
        for plan in self:
            if plan.amount_total <= 0:
                raise ValidationError(_('مبلغ التقسيط يجب أن يكون أكبر من صفر.'))
            if plan.installment_count <= 0:
                raise ValidationError(_('عدد الأقساط يجب أن يكون أكبر من صفر.'))

    @api.depends('sale_order_id.amount_paid', 'amount_total')
    def _compute_amounts(self):
        for plan in self:
            plan.paid_amount = min(plan.sale_order_id.amount_paid or 0.0, plan.amount_total or 0.0)
            plan.remaining_amount = max((plan.amount_total or 0.0) - plan.paid_amount, 0.0)
            if plan.state == 'active' and plan.remaining_amount <= 0:
                plan.state = 'paid'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.installment.plan') or _('New')
            if vals.get('sale_order_id') and not vals.get('amount_total'):
                order = self.env['sale.order'].browse(vals['sale_order_id'])
                vals['amount_total'] = order.balance_due
        return super().create(vals_list)

    def action_generate_lines(self):
        for plan in self:
            if plan.state != 'draft':
                raise ValidationError(_('يمكن توليد الأقساط فقط في حالة المسودة.'))
            plan.line_ids.unlink()
            base = plan.amount_total / plan.installment_count
            lines = []
            running = 0.0
            for seq in range(1, plan.installment_count + 1):
                amount = round(base, 2)
                if seq == plan.installment_count:
                    amount = round(plan.amount_total - running, 2)
                running += amount
                lines.append((0, 0, {
                    'sequence': seq,
                    'due_date': plan.start_date + relativedelta(months=seq - 1),
                    'amount': amount,
                }))
            plan.line_ids = lines

    def action_activate(self):
        for plan in self:
            if not plan.line_ids:
                plan.action_generate_lines()
            plan.state = 'active'

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class UtilityInstallmentPlanLine(models.Model):
    _name = 'utility.installment.plan.line'
    _description = 'قسط فاتورة كهرباء'
    _order = 'plan_id, sequence'

    plan_id = fields.Many2one('utility.installment.plan', string='خطة التقسيط', required=True, ondelete='cascade')
    sequence = fields.Integer('القسط')
    due_date = fields.Date('تاريخ الاستحقاق', required=True)
    amount = fields.Float('المبلغ', required=True)
    paid_amount = fields.Float('المدفوع', compute='_compute_paid_state')
    remaining_amount = fields.Float('المتبقي', compute='_compute_paid_state')
    state = fields.Selection([
        ('pending', 'مستحق'),
        ('partial', 'مدفوع جزئياً'),
        ('paid', 'مدفوع'),
        ('overdue', 'متأخر'),
    ], compute='_compute_paid_state', string='الحالة')

    @api.depends('plan_id.paid_amount', 'amount', 'due_date')
    def _compute_paid_state(self):
        today = fields.Date.context_today(self)
        for line in self:
            previous_due = sum(line.plan_id.line_ids.filtered(lambda l: l.sequence < line.sequence).mapped('amount'))
            available = max((line.plan_id.paid_amount or 0.0) - previous_due, 0.0)
            line.paid_amount = min(available, line.amount or 0.0)
            line.remaining_amount = max((line.amount or 0.0) - line.paid_amount, 0.0)
            if line.remaining_amount <= 0:
                line.state = 'paid'
            elif line.paid_amount > 0:
                line.state = 'partial'
            elif line.due_date and line.due_date < today:
                line.state = 'overdue'
            else:
                line.state = 'pending'