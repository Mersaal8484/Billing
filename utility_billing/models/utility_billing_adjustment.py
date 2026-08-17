from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class UtilityBillingAdjustment(models.Model):
    _name = 'utility.billing.adjustment'
    _description = 'تعديل فوترة الكهرباء'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'requested_date desc, id desc'

    name = fields.Char(string='رقم التعديل', required=True, copy=False, readonly=True,
                       default=lambda self: _('جديد'))
    customer_id = fields.Many2one(
        'utility.customer', string='حساب المشترك', required=True, index=True,
        check_company=True, tracking=True)
    billing_period_id = fields.Many2one(
        'date.range', string='فترة الفوترة', required=True, index=True,
        check_company=True, tracking=True)
    sale_order_id = fields.Many2one(
        'sale.order', string='الفاتورة الأصلية', required=True, index=True,
        ondelete='restrict', check_company=True, tracking=True)
    invoice_id = fields.Many2one(
        'account.move', string='الفاتورة المحاسبية الأصلية', required=True,
        index=True, ondelete='restrict', check_company=True, tracking=True)

    adjustment_type = fields.Selection([
        ('reading_correction', 'تصحيح قراءة'),
        ('consumption_correction', 'تصحيح استهلاك'),
        ('tariff_correction', 'تصحيح تعرفة'),
        ('charge_correction', 'تصحيح رسم'),
        ('billing_component_correction', 'تصحيح مكون فوترة'),
        ('manual_adjustment', 'تعديل يدوي'),
        ('other', 'أخرى'),
    ], string='نوع التعديل', required=True, default='manual_adjustment', tracking=True)
    component_line_type = fields.Selection([
        ('consumption', 'استهلاك'),
        ('fixed_fee', 'رسم ثابت'),
        ('service_charge', 'رسم خدمة'),
        ('mu_allim', 'رسم المعلم'),
        ('cleaning', 'رسم النظافة'),
        ('municipality', 'رسم محلي'),
        ('private_transformer_fee', 'رسم المحول الخاص'),
        ('discount', 'خصم'),
        ('penalty', 'غرامة'),
    ], string='مكوّن الفوترة', tracking=True,
        help='يحدد بند الفاتورة الذي يجب أن يعالجه الإشعار الجزئي.')
    reason = fields.Char(string='سبب التعديل', required=True, tracking=True)
    description = fields.Text(string='الوصف والتبرير')
    rebill = fields.Boolean(string='إعادة فوترة كاملة', default=False, tracking=True)
    corrected_consumption = fields.Float(string='الاستهلاك المصحح')
    corrected_current_reading = fields.Float(string='القراءة الحالية المصححة')

    currency_id = fields.Many2one(
        'res.currency', string='العملة', related='sale_order_id.currency_id',
        store=True, readonly=True)
    original_amount = fields.Monetary(
        string='المبلغ الأصلي', currency_field='currency_id',
        compute='_compute_amounts', store=True, readonly=True)
    corrected_amount = fields.Monetary(
        string='المبلغ المصحح', currency_field='currency_id', tracking=True)
    difference_amount = fields.Monetary(
        string='فرق التعديل', currency_field='currency_id',
        compute='_compute_amounts', store=True, readonly=True)

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('submitted', 'بانتظار الاعتماد'),
        ('approved', 'معتمد'),
        ('applied', 'تم التطبيق'),
        ('cancelled', 'ملغى'),
    ], string='الحالة', default='draft', required=True, index=True,
        tracking=True, copy=False)
    requested_by_id = fields.Many2one(
        'res.users', string='طالب التعديل', default=lambda self: self.env.user,
        required=True, readonly=True, copy=False)
    requested_date = fields.Datetime(
        string='تاريخ الطلب', default=fields.Datetime.now, required=True,
        readonly=True, copy=False)
    approved_by_id = fields.Many2one(
        'res.users', string='معتمد التعديل', readonly=True, copy=False)
    approved_date = fields.Datetime(
        string='تاريخ الاعتماد', readonly=True, copy=False)
    credit_note_id = fields.Many2one(
        'account.move', string='إشعار الدائن', readonly=True, copy=False,
        index=True, ondelete='restrict')
    debit_invoice_id = fields.Many2one(
        'account.move', string='فاتورة التعديل الإضافية (مدين)', readonly=True, copy=False,
        index=True, ondelete='restrict',
        help='فاتورة إضافية تنشأ عند تصحيح يُنتج فرقًا ماليًا موجبًا (استهلاك أعلى من الأصلي).')
    replacement_sale_order_id = fields.Many2one(
        'sale.order', string='الفاتورة البديلة', readonly=True, copy=False,
        index=True, ondelete='restrict')
    replacement_invoice_id = fields.Many2one(
        'account.move', string='الفاتورة المحاسبية البديلة', readonly=True,
        copy=False, index=True, ondelete='restrict')
    company_id = fields.Many2one(
        'res.company', string='الشركة', required=True,
        default=lambda self: self.env.company, index=True, check_company=True)

    @api.depends('invoice_id.amount_total', 'corrected_amount', 'corrected_consumption', 'corrected_current_reading')
    def _compute_amounts(self):
        for record in self:
            original = record.invoice_id.amount_total if record.invoice_id else 0.0
            record.original_amount = original
            # إذا لم يتم تعيين corrected_amount في تصحيح القراءة/الاستهلاك، نحسبه آلياً من محرك التسعير
            if record.adjustment_type in ('reading_correction', 'consumption_correction') and record.sale_order_id and record.corrected_amount == 0.0:
                if record.adjustment_type == 'reading_correction' and record.corrected_current_reading and not record.corrected_consumption:
                    prev = record.sale_order_id.previous_reading or 0.0
                    mult = getattr(record.sale_order_id, 'meter_multiplier', 1.0) or 1.0
                    record.corrected_consumption = max(0.0, (record.corrected_current_reading - prev) * mult)
                if hasattr(record.sale_order_id, '_simulate_bill_total_for_consumption') and (record.corrected_consumption or record.corrected_current_reading):
                    version_id = record.sale_order_id.contract_template_version_id.id if record.sale_order_id.contract_template_version_id else False
                    curr_read = record.corrected_current_reading if record.adjustment_type == 'reading_correction' else record.sale_order_id.current_reading
                    record.corrected_amount = record.sale_order_id._simulate_bill_total_for_consumption(
                        record.corrected_consumption or 0.0,
                        current_reading=curr_read,
                        version_id=version_id,
                    )
            record.difference_amount = record.corrected_amount - original

    @api.onchange('corrected_current_reading', 'sale_order_id', 'adjustment_type')
    def _onchange_corrected_current_reading(self):
        if self.adjustment_type == 'reading_correction' and self.sale_order_id and self.corrected_current_reading is not False:
            if hasattr(self.sale_order_id, '_calculate_corrected_consumption_for_reading'):
                self.corrected_consumption = self.sale_order_id._calculate_corrected_consumption_for_reading(self.corrected_current_reading)
            else:
                prev = self.sale_order_id.previous_reading or 0.0
                mult = getattr(self.sale_order_id, 'meter_multiplier', 1.0) or 1.0
                self.corrected_consumption = max(0.0, (self.corrected_current_reading - prev) * mult)
            self._reprice_correction()

    @api.onchange('corrected_consumption', 'sale_order_id', 'adjustment_type')
    def _onchange_corrected_consumption(self):
        if self.adjustment_type in ('reading_correction', 'consumption_correction') and self.sale_order_id:
            self._reprice_correction()

    def _reprice_correction(self):
        """حساب المبلغ التجاري المصحح آلياً من محرك التسعير التاريخي (Authoritative Server Repricing)."""
        for record in self:
            if record.adjustment_type in ('reading_correction', 'consumption_correction') and record.sale_order_id:
                if record.adjustment_type == 'reading_correction' and record.corrected_current_reading is not False:
                    if hasattr(record.sale_order_id, '_calculate_corrected_consumption_for_reading'):
                        record.corrected_consumption = record.sale_order_id._calculate_corrected_consumption_for_reading(record.corrected_current_reading)
                    else:
                        prev = record.sale_order_id.previous_reading or 0.0
                        mult = getattr(record.sale_order_id, 'meter_multiplier', 1.0) or 1.0
                        record.corrected_consumption = max(0.0, (record.corrected_current_reading - prev) * mult)

                consumption = record.corrected_consumption or 0.0
                curr_read = record.corrected_current_reading if record.adjustment_type == 'reading_correction' else record.sale_order_id.current_reading
                version_id = record.sale_order_id.contract_template_version_id.id if record.sale_order_id.contract_template_version_id else False
                if hasattr(record.sale_order_id, '_simulate_bill_total_for_consumption'):
                    record.corrected_amount = record.sale_order_id._simulate_bill_total_for_consumption(
                        consumption,
                        current_reading=curr_read,
                        version_id=version_id,
                    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', _('جديد')) == _('جديد'):
                vals['name'] = sequence.next_by_code('utility.billing.adjustment') or _('تعديل جديد')
            if vals.get('sale_order_id'):
                order = self.env['sale.order'].browse(vals['sale_order_id']).exists()
                if order:
                    vals.setdefault('customer_id', order.customer_id.id)
                    vals.setdefault('billing_period_id', order.date_range_id.id)
                    vals.setdefault('company_id', order.company_id.id)
                    # Auto-compute corrected_consumption for reading_correction
                    if vals.get('adjustment_type') == 'reading_correction' and vals.get('corrected_current_reading') is not None:
                        if hasattr(order, '_calculate_corrected_consumption_for_reading'):
                            vals['corrected_consumption'] = order._calculate_corrected_consumption_for_reading(vals['corrected_current_reading'])
                        else:
                            prev = order.previous_reading or 0.0
                            mult = getattr(order, 'meter_multiplier', 1.0) or 1.0
                            vals['corrected_consumption'] = max(0.0, (vals['corrected_current_reading'] - prev) * mult)
                    # Server-authoritative calculation for reading/consumption corrections (cannot be overridden by user input)
                    if vals.get('adjustment_type') in ('reading_correction', 'consumption_correction') and hasattr(order, '_simulate_bill_total_for_consumption'):
                        cons = vals.get('corrected_consumption', 0.0)
                        curr_read = vals.get('corrected_current_reading', order.current_reading)
                        v_id = order.contract_template_version_id.id if order.contract_template_version_id else False
                        vals['corrected_amount'] = order._simulate_bill_total_for_consumption(cons, current_reading=curr_read, version_id=v_id)
        records = super().create(vals_list)
        records._validate_original_links()
        return records

    def _validate_original_links(self):
        for record in self:
            if record.sale_order_id.customer_id != record.customer_id:
                raise ValidationError(_('حساب التعديل لا يطابق حساب الفاتورة الأصلية.'))
            if record.sale_order_id.date_range_id != record.billing_period_id:
                raise ValidationError(_('فترة التعديل لا تطابق فترة الفاتورة الأصلية.'))
            if record.invoice_id not in (record.sale_order_id.invoice_ids | record.sale_order_id.utility_move_ids):
                raise ValidationError(_('الفاتورة المحاسبية لا ترتبط بأمر البيع الأصلي.'))
            if record.invoice_id.state != 'posted':
                raise ValidationError(_('لا يمكن تعديل فاتورة محاسبية غير مرحلة.'))
            if record.company_id != record.sale_order_id.company_id:
                raise ValidationError(_('شركة التعديل لا تطابق شركة الفاتورة الأصلية.'))

    @api.constrains(
        'state', 'credit_note_id', 'debit_invoice_id', 'replacement_sale_order_id',
        'replacement_invoice_id', 'rebill')
    def _check_applied_integrity(self):
        for record in self:
            if record.state != 'applied':
                continue
            # A zero-difference adjustment requires no accounting document
            rounding = record.currency_id.rounding if record.currency_id else 0.01
            has_financial_diff = abs(record.difference_amount) > rounding
            if has_financial_diff:
                has_credit = record.credit_note_id and record.credit_note_id.state == 'posted'
                has_debit = record.debit_invoice_id and record.debit_invoice_id.state == 'posted'
                if not (has_credit or has_debit):
                    raise ValidationError(_(
                        'لا يمكن أن يكون التعديل مطبقًا دون مستند محاسبي مرحّل '
                        '(إشعار دائن أو فاتورة تعديل إضافية).'
                    ))
            if record.rebill and (
                    not record.replacement_sale_order_id
                    or not record.replacement_invoice_id
                    or record.replacement_invoice_id.state != 'posted'):
                raise ValidationError(_(
                    'إعادة الفوترة المطبقة تتطلب أمر بيع وفاتورة بديلة مرحلة.'
                ))

    def _lock_for_application(self):
        self.ensure_one()
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT id FROM utility_billing_adjustment WHERE id = %s FOR UPDATE',
            [self.id],
        )
        self.env.cr.execute(
            'SELECT id FROM account_move WHERE id = %s FOR UPDATE',
            [self.invoice_id.id],
        )
        self.invalidate_cache()
        self.invoice_id.invalidate_cache()

    def _check_manager(self):
        if not (self.env.user.has_group('utility_core.group_utility_billing_manager')
                or self.env.user.has_group('utility_core.group_utility_admin')):
            raise AccessError(_('لا تملك صلاحية اعتماد أو تطبيق تعديلات الفوترة.'))

    def write(self, vals):
        if not (self.env.context.get('_allow_adjustment_transition') and self.env.su):
            for record in self:
                if record.state == 'applied':
                    raise ValidationError(_('تعديل الفوترة المطبق غير قابل للتعديل.'))
                if record.state in ('submitted', 'approved') and set(vals) - {'message_follower_ids'}:
                    raise ValidationError(_('لا يمكن تعديل بيانات التعديل بعد إرساله للاعتماد.'))
        res = super().write(vals)
        # Recalculate authoritative amounts on draft records if input values changed
        if any(f in vals for f in ('corrected_current_reading', 'corrected_consumption', 'adjustment_type')):
            for record in self:
                if record.state == 'draft' and record.adjustment_type in ('reading_correction', 'consumption_correction'):
                    record._reprice_correction()
        return res

    def action_submit(self):
        for record in self:
            self.env.user.check_record_scope(record)
            if record.state != 'draft':
                raise ValidationError(_('يمكن إرسال التعديلات المسودة فقط.'))
            if record.adjustment_type in ('reading_correction', 'consumption_correction'):
                record._reprice_correction()
            record._validate_original_links()
            if not (record.reason or '').strip():
                raise ValidationError(_('يجب إدخال سبب واضح للتعديل.'))
            record.sudo().with_context(_allow_adjustment_transition=True).write({
                'state': 'submitted', 'requested_date': fields.Datetime.now(),
            })
            record.message_post(body=_('تم إرسال تعديل الفوترة للاعتماد.'))
        return True

    def action_approve(self):
        self._check_manager()
        for record in self:
            self.env.user.check_record_scope(record)
            if record.state != 'submitted':
                raise ValidationError(_('يمكن اعتماد التعديلات المرسلة فقط.'))
            if (record.requested_by_id == self.env.user
                    and not self.env.user.has_group('utility_core.group_utility_admin')):
                raise AccessError(_('لا يمكن لمدير الفوترة اعتماد التعديل الذي أنشأه بنفسه.'))
            record.with_context(_allow_adjustment_transition=True).write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            record.message_post(body=_('تم اعتماد تعديل الفوترة.'))
        return True

    def action_cancel(self):
        for record in self:
            if record.state == 'applied':
                raise ValidationError(_('لا يمكن إلغاء تعديل تم تطبيقه.'))
            record.with_context(_allow_adjustment_transition=True).write({'state': 'cancelled'})
            record.message_post(body=_('تم إلغاء تعديل الفوترة.'))
        return True

    def action_open_original_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('الفاتورة الأصلية'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_open_credit_note(self):
        self.ensure_one()
        if not self.credit_note_id:
            raise UserError(_('لم يتم إنشاء إشعار دائن لهذا التعديل بعد.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('إشعار الدائن'),
            'res_model': 'account.move',
            'res_id': self.credit_note_id.id,
            'view_mode': 'form',
        }

    def action_open_replacement(self):
        self.ensure_one()
        if not self.replacement_invoice_id:
            raise UserError(_('لا توجد فاتورة بديلة لهذا التعديل بعد.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('الفاتورة البديلة'),
            'res_model': 'account.move',
            'res_id': self.replacement_invoice_id.id,
            'view_mode': 'form',
        }

    def _create_full_credit_note(self):
        self.ensure_one()
        invoice = self.invoice_id
        credit_notes = invoice._reverse_moves([{
            'invoice_date': fields.Date.context_today(self),
            'ref': _('%s - إشعار دائن كامل') % self.name,
        }], cancel=False)
        credit_note = credit_notes[:1]
        credit_note.write({
            'utility_adjustment_id': self.id,
        })
        credit_note.action_post()
        return credit_note

    def _create_partial_credit_note(self):
        self.ensure_one()
        amount = abs(self.difference_amount)
        if not amount:
            raise ValidationError(_('لا يوجد فرق مالي لإنشاء إشعار دائن.'))
        invoice = self.invoice_id
        invoice_lines = invoice.invoice_line_ids.filtered(
            lambda item: item.account_id
            and item.display_type not in ('line_section', 'line_note'))
        if self.adjustment_type == 'billing_component_correction':
            if not self.component_line_type:
                raise ValidationError(_('يجب تحديد مكوّن الفوترة للتصحيح المكوّني.'))
            invoice_lines = invoice_lines.filtered(
                lambda line: self.component_line_type in line.sale_line_ids.mapped('meter_line_type'))
            if not invoice_lines:
                raise ValidationError(_('لم يتم العثور على مكوّن الفوترة المحدد في الفاتورة الأصلية.'))
        source_line = invoice_lines[:1]
        if not source_line:
            raise ValidationError(_('لا يوجد حساب إيراد صالح في الفاتورة الأصلية لإنشاء إشعار الدائن.'))
        source_total = sum(invoice_lines.mapped('price_total'))
        ratio = amount / source_total if source_total else 0.0
        credit_line_commands = []
        for line in invoice_lines:
            credit_line_commands.append((0, 0, {
                'product_id': line.product_id.id,
                'name': _('تصحيح: %s') % (line.name or self.reason),
                'account_id': line.account_id.id,
                'quantity': abs(line.quantity or 0.0) * ratio,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'analytic_distribution': line.analytic_distribution,
            }))
        if not credit_line_commands:
            raise ValidationError(_('لا توجد بنود محاسبية قابلة للنسخ في الفاتورة الأصلية.'))
        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'journal_id': invoice.journal_id.id,
            'company_id': invoice.company_id.id,
            'partner_id': invoice.partner_id.id,
            'currency_id': invoice.currency_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': _('%s - إشعار دائن جزئي') % self.name,
            'invoice_origin': invoice.name,
            'utility_customer_id': self.customer_id.id,
            'utility_sale_order_id': self.sale_order_id.id,
            'utility_adjustment_id': self.id,
            'reversed_entry_id': invoice.id,
            'invoice_line_ids': credit_line_commands,
        })
        residual = amount - credit_note.amount_total
        if abs(residual) > invoice.currency_id.rounding:
            credit_note.write({'invoice_line_ids': [(0, 0, {
                'name': _('تسوية فرق التقريب لتعديل الفوترة: %s') % self.reason,
                'account_id': source_line.account_id.id,
                'quantity': 1.0,
                'price_unit': residual,
                'tax_ids': [(6, 0, [])],
            })]})
        credit_note.action_post()
        return credit_note

    def _create_debit_invoice(self):
        """Create an additional out_invoice for a positive financial correction difference.

        Used when corrected_amount > original invoice amount (upward correction).
        Example: meter under-read → additional consumption → additional invoice.
        The resulting invoice posts to the same revenue account as the original.
        """
        self.ensure_one()
        amount = abs(self.difference_amount)
        if not amount:
            raise ValidationError(_('لا يوجد فرق مالي موجب لإنشاء فاتورة تعديل إضافية.'))
        invoice = self.invoice_id
        invoice_lines = invoice.invoice_line_ids.filtered(
            lambda l: l.account_id
            and l.display_type not in ('line_section', 'line_note'))
        if self.adjustment_type == 'billing_component_correction' and self.component_line_type:
            invoice_lines = invoice_lines.filtered(
                lambda line: self.component_line_type in line.sale_line_ids.mapped('meter_line_type'))
        source_line = invoice_lines[:1]
        if not source_line:
            raise ValidationError(_(
                'لا يوجد حساب إيراد صالح في الفاتورة الأصلية لإنشاء فاتورة التعديل الإضافية.'
            ))
        debit_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': invoice.journal_id.id,
            'company_id': invoice.company_id.id,
            'partner_id': invoice.partner_id.id,
            'currency_id': invoice.currency_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': _('%s - فاتورة تعديل إضافية (مدين)') % self.name,
            'invoice_origin': invoice.name,
            'utility_customer_id': self.customer_id.id,
            'utility_sale_order_id': self.sale_order_id.id,
            'utility_adjustment_id': self.id,
            'invoice_line_ids': [(0, 0, {
                'name': _('تعديل إضافي: %s') % self.reason,
                'account_id': source_line.account_id.id,
                'quantity': 1.0,
                'price_unit': amount,
                'tax_ids': [(6, 0, [])],
            })],
        })
        debit_invoice.action_post()
        return debit_invoice

    def _create_replacement_bill(self):
        self.ensure_one()
        order = self.sale_order_id
        if self.adjustment_type in ('reading_correction', 'consumption_correction') and self.corrected_consumption < 0:
            raise ValidationError(_('الاستهلاك المصحح لا يمكن أن يكون سالباً.'))
        consumption = order.consumption
        if self.adjustment_type in ('consumption_correction', 'reading_correction'):
            consumption = self.corrected_consumption
        current_reading = order.current_reading
        if self.adjustment_type == 'reading_correction':
            current_reading = self.corrected_current_reading

        forced_version_id = order.contract_template_version_id.id if order.contract_template_version_id else False
        replacement_ctx = dict(self.env.context, allow_billing_adjustment=True)
        if forced_version_id:
            replacement_ctx['_force_contract_version_id'] = forced_version_id

        replacement = self.env['sale.order'].with_context(
            replacement_ctx
        ).create({
            'partner_id': order.partner_id.id,
            'customer_id': order.customer_id.id,
            'meter_id': order.meter_id.id,
            'contract_template_version_id': forced_version_id,
            'date_range_id': order.date_range_id.id,
            'date_order': fields.Datetime.now(),
            'period_start': order.period_start,
            'period_end': order.period_end,
            'previous_reading': order.previous_reading,
            'current_reading': current_reading,
            'consumption': consumption,
            'replacement_of_id': order.id,
            'billing_adjustment_id': self.id,
            'billing_correction_status': 'replaced',
        })
        replacement.with_context(replacement_ctx)._calculate_amounts()
        replacement.with_context(replacement_ctx).action_confirm()
        invoices = replacement._create_invoices()
        invoices.write({
            'utility_adjustment_id': self.id,
            'utility_replacement_of_id': self.invoice_id.id,
        })
        invoices.action_post()
        return replacement, invoices[:1]

    def action_apply_correction(self):
        """Apply an approved billing adjustment.

        Routing:
          difference < 0  → Credit Note (downward correction)
          difference > 0  → Additional Debit Invoice (upward correction)
          difference == 0 → No accounting document (administrative/metadata only)
        """
        self._check_manager()
        for record in self:
            record._lock_for_application()
            if record.state == 'applied':
                raise ValidationError(_('تم تطبيق هذا التعديل مسبقاً ولا يمكن إعادة تطبيقه.'))
            if record.state != 'approved':
                raise ValidationError(_('يجب اعتماد التعديل قبل تطبيق التصحيح.'))
            record._validate_original_links()
            conflicting = self.search([
                ('id', '!=', record.id),
                ('invoice_id', '=', record.invoice_id.id),
                ('state', '=', 'applied'),
            ], limit=1)
            if conflicting:
                raise ValidationError(_(
                    'لا يمكن تطبيق تعديل آخر على الفاتورة %s بعد تطبيق التعديل %s.'
                ) % (record.invoice_id.display_name, conflicting.name))

            rounding = record.currency_id.rounding if record.currency_id else 0.01

            with self.env.cr.savepoint():
                vals = {'state': 'applied'}

                if abs(record.difference_amount) <= rounding:
                    # ── Zero difference: no accounting document required ──────────
                    record.sale_order_id.write({'billing_correction_status': 'partially_corrected'})
                    record.with_context(_allow_adjustment_transition=True).write(vals)
                    record.message_post(body=_(
                        'تم تطبيق التعديل. الفرق المالي = صفر؛ لم يُنشأ أي مستند محاسبي.'
                    ))

                elif record.difference_amount < 0:
                    # ── Downward correction: Credit Note ─────────────────────────
                    credit_note = (
                        record._create_full_credit_note()
                        if record.rebill
                        else record._create_partial_credit_note()
                    )
                    vals['credit_note_id'] = credit_note.id
                    if record.rebill:
                        replacement, replacement_invoice = record._create_replacement_bill()
                        vals.update({
                            'replacement_sale_order_id': replacement.id,
                            'replacement_invoice_id': replacement_invoice.id,
                        })
                        record.sale_order_id.write({'billing_correction_status': 'replaced'})
                    else:
                        record.sale_order_id.write({'billing_correction_status': 'partially_corrected'})
                    record.with_context(_allow_adjustment_transition=True).write(vals)
                    record.message_post(body=_(
                        'تم تطبيق التصحيح (تخفيض): إشعار دائن %s بمبلغ %s.'
                    ) % (credit_note.name, abs(record.difference_amount)))
                    record.invoice_id.message_post(
                        body=_('تم ربط تعديل الفوترة %s بهذه الفاتورة.') % record.name)

                else:
                    # ── Upward correction: Additional Debit Invoice ───────────────
                    debit_invoice = record._create_debit_invoice()
                    vals['debit_invoice_id'] = debit_invoice.id
                    record.sale_order_id.write({'billing_correction_status': 'partially_corrected'})
                    record.with_context(_allow_adjustment_transition=True).write(vals)
                    record.message_post(body=_(
                        'تم تطبيق التصحيح (زيادة): فاتورة تعديل إضافية %s بمبلغ %s.'
                    ) % (debit_invoice.name, record.difference_amount))
                    record.invoice_id.message_post(
                        body=_('تم ربط تعديل الفوترة %s بهذه الفاتورة.') % record.name)

        return True
