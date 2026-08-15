from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class UtilityFinancialSettlement(models.Model):
    """تسوية مالية لحسابات المشتركين.

    دورة الحياة:
        draft → submitted → approved → applied
        [من draft / submitted / approved] → cancelled

    قواعد النزاهة:
      1. فصل المهام (Segregation of Duties): المعتمد لا يمكن أن يكون هو مقدّم الطلب.
      2. الحماية ضد التعديل (Immutability): بعد التطبيق لا يمكن تعديل الحقول المالية أو حذف السجل.
      3. الربط المحاسبي الصريح: لا يمكن أن تكون الحالة 'applied' دون قيد محاسبي مرحّل.
    """
    _name = 'utility.financial.settlement'
    _description = 'تسوية مالية'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    _IMMUTABLE_FIELDS = frozenset({
        'amount', 'settlement_type', 'account_id', 'company_id', 'reason', 'date'
    })

    active = fields.Boolean('نشط', default=True)
    name = fields.Char('رقم التسوية المالية', default=lambda self: _('جديد'), readonly=True, copy=False)
    company_id = fields.Many2one('res.company', 'الشركة', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    account_id = fields.Many2one('utility.customer', 'حساب الكهرباء', required=True, index=True)
    partner_id = fields.Many2one('res.partner', related='account_id.partner_id', store=True, string='العميل')
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    settlement_type = fields.Selection([
        ('credit', 'دائن (خصم للمشترك)'),
        ('debit', 'مدين (غرامة/إضافة على المشترك)'),
    ], string='نوع التسوية المالية', required=True, default='credit')
    amount = fields.Monetary('مبلغ التسوية', required=True, currency_field='currency_id')
    reason = fields.Text('سبب التسوية المالية', required=True)
    date = fields.Date('تاريخ التسوية', default=fields.Date.context_today, required=True)

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('submitted', 'مُقدَّمة للاعتماد'),
        ('approved', 'معتمدة'),
        ('applied', 'تم التطبيق'),
        ('cancelled', 'ملغاة'),
    ], string='الحالة', default='draft', readonly=True, tracking=True, copy=False)

    # ── سجل الإجراءات وفصل المهام ──────────────────────────────────────────
    submitted_by_id = fields.Many2one('res.users', 'مُقدِّم الطلب', readonly=True, copy=False)
    submitted_date = fields.Datetime('تاريخ التقديم', readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', 'المعتمِد المالي', readonly=True, copy=False)
    approved_date = fields.Datetime('تاريخ الاعتماد', readonly=True, copy=False)
    applied_by_id = fields.Many2one('res.users', 'المنفّذ', readonly=True, copy=False)
    applied_date = fields.Datetime('تاريخ التطبيق', readonly=True, copy=False)
    cancelled_by_id = fields.Many2one('res.users', 'من ألغى', readonly=True, copy=False)
    cancelled_date = fields.Datetime('تاريخ الإلغاء', readonly=True, copy=False)
    cancel_reason = fields.Text('سبب الإلغاء', copy=False)

    move_id = fields.Many2one('account.move', string='القيد المحاسبي', readonly=True, copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('جديد')) == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.financial.settlement') or _('جديد')
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_positive_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('مبلغ التسوية المالية يجب أن يكون أكبر من الصفر.'))

    @api.constrains('state', 'move_id')
    def _check_applied_has_move(self):
        for rec in self:
            if rec.state == 'applied':
                if not rec.move_id or rec.move_id.state != 'posted':
                    raise ValidationError(_('لا يمكن تطبيق التسوية المالية دون قيد محاسبي مرحّل.'))

    def write(self, vals):
        for rec in self:
            if rec.state in ('applied', 'cancelled'):
                # In applied/cancelled state, immutable fields cannot be modified
                if any(field in vals for field in self._IMMUTABLE_FIELDS):
                    raise ValidationError(_(
                        'لا يمكن تعديل البيانات المالية لتسوية بحالة "%s".'
                    ) % dict(self._fields['state'].selection).get(rec.state, rec.state))
            elif rec.state == 'approved':
                if any(field in vals for field in ('amount', 'settlement_type', 'account_id')):
                    raise ValidationError(_('لا يمكن تعديل المبلغ أو الحساب لتسوية معتمدة. يجب إلغاؤها أولاً.'))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_(
                    'لا يمكن حذف تسوية مالية في حالة "%s". يمكنك إلغاؤها بدلاً من ذلك.'
                ) % dict(self._fields['state'].selection).get(rec.state, rec.state))
        return super().unlink()

    def _get_company_config(self, company_field, config_key):
        company = self.env.company
        val = company[company_field]
        if val:
            return val.id if hasattr(val, 'id') else val
        param = self.env['ir.config_parameter'].sudo().get_param(config_key, '0')
        return int(param) if param and param.isdigit() else 0

    # ── إجراءات دورة الحياة ───────────────────────────────────────────────────

    def action_submit(self):
        """تقديم التسوية المالية للاعتماد."""
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('يمكن تقديم التسويات المسودة فقط.'))
            if rec.amount <= 0:
                raise ValidationError(_('مبلغ التسوية يجب أن يكون أكبر من الصفر.'))
            rec.write({
                'state': 'submitted',
                'submitted_by_id': self.env.user.id,
                'submitted_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('تم تقديم التسوية المالية للاعتماد.'))

    def action_approve(self):
        """اعتماد التسوية المالية مع التحقق من فصل المهام."""
        for rec in self:
            if rec.state != 'submitted':
                raise ValidationError(_('يمكن اعتماد التسويات المُقدَّمة فقط.'))
            # Segregation of duties: approver != submitter
            if rec.submitted_by_id == self.env.user and not self.env.su:
                raise AccessError(_(
                    'لا يمكن لمن قدّم طلب التسوية (%s) أن يعتمده مالياً. (مبدأ فصل المهام)'
                ) % self.env.user.name)
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('تم اعتماد التسوية المالية.'))

    def action_apply_settlement(self):
        """تطبيق التسوية المالية وإنشاء القيد المحاسبي."""
        for rec in self:
            if rec.state == 'applied':
                raise ValidationError(_('تم تطبيق هذه التسوية بالفعل!'))
            if rec.state != 'approved':
                raise ValidationError(_('يجب اعتماد التسوية المالية قبل تطبيقها.'))

            settlement_journal_id = rec._get_company_config('settlement_journal_id', 'utility.settlement_journal_id')
            settlement_account_id = rec._get_company_config('settlement_account_id', 'utility.settlement_account_id')

            if not settlement_journal_id or not settlement_account_id:
                raise ValidationError(_('يرجى تحديد يومية التسويات وحساب التسويات في إعدادات النظام أولاً.'))

            journal = self.env['account.journal'].browse(settlement_journal_id)
            if journal.type != 'sale':
                sale_journal = self.env['account.journal'].search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', rec.company_id.id),
                ], limit=1)
                if sale_journal:
                    journal = sale_journal
                else:
                    raise ValidationError(_(
                        'اليومية المحددة للتسويات ليست يومية مبيعات. '
                        'يرجى تحديد يومية مبيعات في إعدادات النظام.'
                    ))

            partner = rec.account_id.partner_id
            if not partner:
                raise ValidationError(_('حساب الكهرباء غير مربوط بعميل (Partner).'))

            move_type = 'out_refund' if rec.settlement_type == 'credit' else 'out_invoice'

            move_vals = {
                'journal_id': journal.id,
                'company_id': rec.company_id.id,
                'date': rec.date or fields.Date.context_today(self),
                'ref': f"تسوية مالية: {rec.name} - {rec.reason}",
                'move_type': move_type,
                'partner_id': partner.id,
                'invoice_line_ids': [(0, 0, {
                    'name': rec.reason,
                    'quantity': 1.0,
                    'price_unit': rec.amount,
                    'account_id': settlement_account_id,
                    'tax_ids': False,
                })],
            }

            move = self.env['account.move'].create(move_vals)
            move.action_post()

            rec.write({
                'state': 'applied',
                'move_id': move.id,
                'applied_by_id': self.env.user.id,
                'applied_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('تم تطبيق التسوية المالية وإنشاء القيد المحاسبي %s.') % move.name)

        return True

    def action_cancel(self):
        """إلغاء التسوية من أي حالة غير applied."""
        for rec in self:
            if rec.state == 'applied':
                raise ValidationError(_(
                    'لا يمكن إلغاء تسوية مالية تم تطبيقها وترحيل قيدها المحاسبي (%s).'
                ) % (rec.move_id.name if rec.move_id else ''))
            rec.write({
                'state': 'cancelled',
                'cancelled_by_id': self.env.user.id,
                'cancelled_date': fields.Datetime.now(),
            })
            rec.message_post(body=_('تم إلغاء التسوية المالية. السبب: %s') % (rec.cancel_reason or _('لم يُحدد')))

    def action_view_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('القيد المحاسبي'),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
