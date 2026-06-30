from odoo import api, fields, models, _


class UtilityDeposit(models.Model):
    _name = 'utility.deposit'
    _description = 'Utility Deposit'
    _rec_name = 'deposit_number'
    _order = 'deposit_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    deposit_number = fields.Char('Deposit Number', required=True, default=lambda self: _('New'))
    customer_id = fields.Many2one('utility.customer', 'Customer')
    partner_id = fields.Many2one('res.partner', related='customer_id.partner_id', store=True)
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    account_id = fields.Many2one('utility.customer', 'Account', related='customer_id', store=True)
    meter_id = fields.Many2one('utility.meter', 'Meter')
    amount = fields.Float('Amount')
    deposit_date = fields.Date('Deposit Date')
    deposit_type = fields.Selection([
        ('connection', 'Connection'),
        ('security', 'Security'),
        ('meter', 'Meter'),
    ], string='Deposit Type', default='security')
    status = fields.Selection([
        ('draft', 'مسودة'),
        ('held', 'محتجزة (مقبوضة)'),
        ('released', 'مستردة'),
        ('forfeited', 'مصادرة'),
    ], string='Status', default='draft')
    release_date = fields.Date('Release Date')
    notes = fields.Text('Notes')
    
    payment_id = fields.Many2one('account.payment', string='سند القبض / الصرف', readonly=True)
    move_id = fields.Many2one('account.move', string='قيد المصادرة', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('deposit_number', _('New')) == _('New'):
                vals['deposit_number'] = self.env['ir.sequence'].next_by_code('utility.deposit') or _('New')
        return super().create(vals_list)

    def action_receive_deposit(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.status != 'draft':
                continue
            settings = self.env['ir.config_parameter'].sudo()
            deposit_journal_id = int(settings.get_param('utility.deposit_journal_id', 0))
            deposit_account_id = int(settings.get_param('utility.deposit_account_id', 0))
            if not deposit_journal_id or not deposit_account_id:
                raise ValidationError('يرجى تحديد يومية التأمينات وحساب التأمينات في الإعدادات أولاً.')
            
            partner = rec.customer_id.partner_id
            if not partner:
                raise ValidationError('لا يوجد عميل مرتبط بحساب الكهرباء.')

            payment = self.env['account.payment'].create({
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': partner.id,
                'amount': rec.amount,
                'date': rec.deposit_date or fields.Date.today(),
                'journal_id': deposit_journal_id,
                'ref': f"وديعة رقم: {rec.deposit_number}",
            })
            payment.action_post()
            rec.write({
                'status': 'held',
                'payment_id': payment.id,
            })

    def action_release_deposit(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.status != 'held':
                continue
            settings = self.env['ir.config_parameter'].sudo()
            deposit_journal_id = int(settings.get_param('utility.deposit_journal_id', 0))
            
            partner = rec.customer_id.partner_id
            
            payment = self.env['account.payment'].create({
                'payment_type': 'outbound',
                'partner_type': 'customer',
                'partner_id': partner.id,
                'amount': rec.amount,
                'date': fields.Date.today(),
                'journal_id': deposit_journal_id,
                'ref': f"استرداد وديعة رقم: {rec.deposit_number}",
            })
            payment.action_post()
            rec.write({
                'status': 'released',
                'release_date': fields.Date.today(),
            })

    def action_forfeit_deposit(self):
        from odoo.exceptions import ValidationError
        for rec in self:
            if rec.status != 'held':
                continue
            settings = self.env['ir.config_parameter'].sudo()
            deposit_journal_id = int(settings.get_param('utility.deposit_journal_id', 0))
            deposit_account_id = int(settings.get_param('utility.deposit_account_id', 0))
            fine_account_id = int(settings.get_param('utility.fine_account_id', 0))
            
            if not deposit_journal_id or not deposit_account_id or not fine_account_id:
                raise ValidationError('إعدادات الحسابات غير مكتملة للمصادرة (حساب الغرامات، التأمينات، واليومية).')
                
            move = self.env['account.move'].create({
                'journal_id': deposit_journal_id,
                'date': fields.Date.today(),
                'ref': f"مصادرة وديعة رقم: {rec.deposit_number}",
                'line_ids': [
                    (0, 0, {
                        'account_id': deposit_account_id,
                        'name': f"مصادرة الوديعة {rec.deposit_number}",
                        'debit': rec.amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': fine_account_id,
                        'name': f"إيراد مصادرة {rec.deposit_number}",
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
