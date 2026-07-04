from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityWriteoff(models.Model):
    _name = 'utility.writeoff'
    _description = 'إعفاء'
    _order = 'date desc'
    _rec_name = 'writeoff_number'
    _rec_display_name = 'writeoff_number'
    
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    writeoff_number = fields.Char('Writeoff Number', required=True, default=lambda self: _('New'))
    customer_id = fields.Many2one('utility.customer', 'Customer')
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    sale_order_id = fields.Many2one('sale.order', 'Sale Order')
    amount = fields.Float('Amount')
    reason = fields.Text('Reason')
    approved_by = fields.Many2one('res.users', 'Approved By')
    date = fields.Datetime('Date', default=fields.Datetime.now)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
    ], string='الحالة', default='draft')

    # ربط القيد المحاسبي الناتج
    move_id = fields.Many2one('account.move', 'إشعار الدائن', readonly=True)

    @api.constrains('amount')
    def _check_positive_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError('مبلغ الإثبات يجب أن يكون أكبر من الصفر.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('writeoff_number', _('New')) == _('New'):
                vals['writeoff_number'] = self.env['ir.sequence'].next_by_code('utility.writeoff') or _('New')
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id
            })

    def _get_company_config(self, company_field, config_key):
        company = self.env.company
        val = company[company_field]
        if val:
            return val.id if hasattr(val, 'id') else val
        return int(self.env['ir.config_parameter'].sudo().get_param(config_key, 0))

    def action_apply(self):
        for rec in self:
            if rec.state != 'approved':
                raise ValidationError( 
                    'يجب اعتماد الإثبات أولاً قبل التطبيق. الحالة الحالية: %s' % rec.state
                )
            if not rec.sale_order_id:
                raise ValidationError('يجب تحديد الفاتورة المرتبطة قبل تطبيق الإثبات.')

            order = rec.sale_order_id
            partner = order.partner_id
            posted_invoices = order.invoice_ids.filtered(lambda i: i.state == 'posted' and i.amount_residual > 0)

            writeoff_journal_id = rec._get_company_config('writeoff_journal_id', 'utility.writeoff_journal_id')
            writeoff_account_id = rec._get_company_config('writeoff_account_id', 'utility.writeoff_account_id')

            if not writeoff_journal_id or not writeoff_account_id:
                raise ValidationError(
                    'يرجى تحديد يومية الإثبات وحساب الإثبات في إعدادات النظام. مسار: إعدادات ← محاسبة الكهرباء ← الإثبات.'
                )

            # إنشاء إشعار دائن (Credit Note) لتغطية مبلغ الإثبات
            move = self.env['account.move'].create({
                'move_type': 'out_refund',
                'partner_id': partner.id,
                'invoice_date': fields.Date.today(),
                'journal_id': writeoff_journal_id,
                'ref': f'إثبات رقم {rec.writeoff_number} - {order.name}',
                'utility_sale_order_id': order.id,
                'invoice_line_ids': [(0, 0, {
                    'name': rec.reason or f'إثبات رصيد {order.name}',
                    'price_unit': rec.amount,
                    'quantity': 1.0,
                    'account_id': writeoff_account_id,
                })],
            })
            move.action_post()

            # مقاصة إشعار الدائن مع فواتير الأمر المتبقية
            if posted_invoices:
                refund_lines = move.line_ids.filtered(
                    lambda l: not l.reconciled and l.account_id.account_type == 'asset_receivable'
                )
                invoice_lines = posted_invoices.mapped('line_ids').filtered(
                    lambda l: not l.reconciled and l.account_id.account_type == 'asset_receivable'
                )
                (refund_lines | invoice_lines).reconcile()

            rec.write({
                'state': 'applied',
                'move_id': move.id,
            })

    def action_draft(self):
        for rec in self:
            rec.write({
                'state': 'draft',
                'approved_by': False
            })
