from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityDeposit(models.Model):
    _name = 'utility.deposit'
    _description = 'تأمين'
    _rec_name = 'deposit_number'
    _order = 'deposit_date desc'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    deposit_number = fields.Char('رقم التأمين', required=True, default=lambda self: _('جديد'))
    customer_id = fields.Many2one('utility.customer', 'العميل')
    partner_id = fields.Many2one('res.partner', related='customer_id.partner_id', store=True)
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    account_id = fields.Many2one('utility.customer', 'الحساب', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'العداد')
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    amount = fields.Monetary('المبلغ', currency_field='currency_id')
    deposit_date = fields.Date('تاريخ التأمين')
    deposit_type = fields.Selection([
        ('connection', 'توصيل'),
        ('security', 'أمان'),
        ('meter', 'عداد'),
    ], string='نوع التأمين', default='security')
    status = fields.Selection([
        ('draft', 'مسودة'),
        ('held', 'محتجزة'),
        ('released', 'مستردة'),
        ('forfeited', 'مصادرة'),
    ], string='الحالة', default='draft')
    release_date = fields.Date('تاريخ الاسترداد')
    notes = fields.Text('ملاحظات')

    payment_id = fields.Many2one('account.payment', string='سند القبض', readonly=True)
    move_id = fields.Many2one('account.move', string='القيد المحاسبي', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('deposit_number', _('جديد')) == _('جديد'):
                vals['deposit_number'] = self.env['ir.sequence'].next_by_code('utility.deposit') or _('جديد')
        return super().create(vals_list)

    # ── FIX-10: منع مبلغ وديعة صفر أو سالب ─────────────────────────────────
    @api.constrains('amount')
    def _check_positive_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(
                    'مبلغ التأمين يجب أن يكون أكبر من الصفر. '
                    'القيمة المدخلة: %s' % rec.amount
                )

    def _get_company_config(self, company_field, config_key):
        company = self.env.company
        val = company[company_field]
        if val:
            return val.id if hasattr(val, 'id') else val
        return int(self.env['ir.config_parameter'].sudo().get_param(config_key, 0))

    def action_receive_deposit(self):
        for rec in self:
            if rec.status != 'draft':
                continue
            if rec.amount <= 0:
                raise ValidationError('لا يمكن تسجيل وديعة بمبلغ صفر أو سالب.')
            deposit_journal_id = rec._get_company_config('deposit_journal_id', 'utility.deposit_journal_id')
            deposit_account_id = rec._get_company_config('deposit_account_id', 'utility.deposit_account_id')
            if not deposit_journal_id or not deposit_account_id:
                raise ValidationError('يرجى تحديد يومية التأمينات وحساب التأمينات في الإعدادات أولاً.')

            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError('لا يوجد عميل مرتبط بحساب الكهرباء.')

            journal = self.env['account.journal'].browse(deposit_journal_id)
            if not journal.inbound_payment_method_line_ids:
                raise ValidationError(
                    'اليومية المحددة (%s) ليس بها طرق دفع واردة. '
                    'يرجى ضبط اليومية في الإعدادات.' % journal.name)

            payment = self.env['account.payment'].create({
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': partner.id,
                'amount': rec.amount,
                'date': rec.deposit_date or fields.Date.today(),
                'journal_id': deposit_journal_id,
                'ref': f'وديعة رقم: {rec.deposit_number}',
            })
            payment.action_post()
            rec.write({
                'status': 'held',
                'payment_id': payment.id,
            })

    def action_release_deposit(self):
        for rec in self:
            if rec.status != 'held':
                continue
            if not rec.payment_id:
                raise ValidationError(
                    'لا يمكن استرداد وديعة [%s] بدون سند قبض مرتبط. '
                    'يُرجى مراجعة سجل التأمين.' % rec.deposit_number
                )
            deposit_journal_id = rec._get_company_config('deposit_journal_id', 'utility.deposit_journal_id')
            deposit_account_id = rec._get_company_config('deposit_account_id', 'utility.deposit_account_id')
            if not deposit_journal_id or not deposit_account_id:
                raise ValidationError('يرجى تحديد يومية التأمينات وحساب التأمينات في الإعدادات أولاً.')

            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError('لا يوجد عميل مرتبط بحساب الكهرباء.')

            journal = self.env['account.journal'].browse(deposit_journal_id)
            bank_account = journal.default_account_id
            if not bank_account:
                raise ValidationError('اليومية المحددة ليس لها حساب افتراضي.')

            move = self.env['account.move'].create({
                'journal_id': deposit_journal_id,
                'date': fields.Date.today(),
                'ref': f'استرداد وديعة رقم: {rec.deposit_number}',
                'line_ids': [
                    (0, 0, {
                        'account_id': deposit_account_id,
                        'name': f'استرداد الوديعة {rec.deposit_number}',
                        'debit': rec.amount,
                        'credit': 0.0,
                        'partner_id': partner.id,
                    }),
                    (0, 0, {
                        'account_id': bank_account.id,
                        'name': f'مقابل استرداد {rec.deposit_number}',
                        'debit': 0.0,
                        'credit': rec.amount,
                    })
                ]
            })
            move.action_post()
            rec.write({
                'status': 'released',
                'release_date': fields.Date.today(),
                'move_id': move.id,
            })

    def action_forfeit_deposit(self):
        for rec in self:
            if rec.status != 'held':
                continue
            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError(
                    'لا يمكن مصادرة وديعة [%s] بدون عميل مرتبط.' % rec.deposit_number
                )
            deposit_journal_id = rec._get_company_config('deposit_journal_id', 'utility.deposit_journal_id')
            deposit_account_id = rec._get_company_config('deposit_account_id', 'utility.deposit_account_id')
            fine_account_id = rec._get_company_config('fine_account_id', 'utility.fine_account_id')

            if not deposit_journal_id or not deposit_account_id or not fine_account_id:
                raise ValidationError('إعدادات الحسابات غير مكتملة للمصادرة (حساب الغرامات، التأمينات، واليومية).')

            move = self.env['account.move'].create({
                'journal_id': deposit_journal_id,
                'date': fields.Date.today(),
                'ref': f'مصادرة وديعة رقم: {rec.deposit_number}',
                'line_ids': [
                    (0, 0, {
                        'account_id': deposit_account_id,
                        'name': f'مصادرة الوديعة {rec.deposit_number}',
                        'debit': rec.amount,
                        'credit': 0.0,
                        'partner_id': partner.id,
                    }),
                    (0, 0, {
                        'account_id': fine_account_id,
                        'name': f'إيراد مصادرة {rec.deposit_number}',
                        'debit': 0.0,
                        'credit': rec.amount,
                    })
                ]
            })
            move.action_post()
            rec.write({
                'status': 'forfeited',
                'move_id': move.id,
            })
