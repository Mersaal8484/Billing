from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class UtilityWriteoff(models.Model):
    _name = 'utility.writeoff'
    _description = 'إعفاء'
    _order = 'date desc'
    _rec_name = 'writeoff_number'
    _rec_display_name = 'writeoff_number'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    writeoff_number = fields.Char('رقم الإعفاء', required=True, default=lambda self: _('جديد'))
    customer_id = fields.Many2one('utility.customer', 'العميل')
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    sale_order_id = fields.Many2one('sale.order', 'أمر البيع')
    currency_id = fields.Many2one(
        'res.currency',
        related='sale_order_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    amount = fields.Monetary('المبلغ', currency_field='currency_id')
    reason = fields.Text('السبب')
    approved_by = fields.Many2one('res.users', 'اعتمد بواسطة')
    date = fields.Datetime('التاريخ', default=fields.Datetime.now)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('applied', 'مُطبّق'),
    ], string='الحالة', default='draft')

    # ربط القيد المحاسبي الناتج
    move_id = fields.Many2one(
        'account.move',
        'إشعار الدائن',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )

    @api.constrains('amount')
    def _check_positive_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError('مبلغ الإثبات يجب أن يكون أكبر من الصفر.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('writeoff_number', _('جديد')) == _('جديد'):
                vals['writeoff_number'] = self.env['ir.sequence'].next_by_code('utility.writeoff') or _('جديد')
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if rec.move_id or rec.state != 'draft':
                raise ValidationError(
                    _('لا يمكن اعتماد الإعفاء إلا من حالة المسودة ومن دون إشعار دائن.')
                )
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
            # Serialize concurrent applications so exactly one credit note can
            # be created and linked to this write-off.
            self.env.flush_all()
            self.env.cr.execute(
                'SELECT id FROM utility_writeoff WHERE id = %s FOR UPDATE',
                [rec.id],
            )
            rec.invalidate_recordset(['state', 'move_id'])

            if rec.move_id:
                raise UserError(
                    _('تم تطبيق هذا الإعفاء مسبقاً وإشعار الدائن المرتبط به هو %s.')
                    % rec.move_id.display_name
                )
            if rec.state != 'approved':
                raise ValidationError(
                    _('يجب اعتماد الإعفاء أولاً قبل التطبيق. الحالة الحالية: %s') % rec.state
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
            if rec.move_id or rec.state == 'applied':
                raise UserError(
                    _('لا يمكن إعادة فتح إعفاء تم تطبيقه أو نتج عنه أثر مالي.')
                )
            if rec.state != 'approved':
                raise ValidationError(
                    _('لا يمكن إعادة الإعفاء إلى المسودة إلا من حالة الاعتماد.')
                )
            rec.write({
                'state': 'draft',
                'approved_by': False
            })
