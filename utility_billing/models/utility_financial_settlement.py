from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityFinancialSettlement(models.Model):
    _name = 'utility.financial.settlement'
    _description = 'تسوية مالية'
    _order = 'date desc'

    name = fields.Char('رقم التسوية المالية', default=lambda self: _('New'), readonly=True)
    account_id = fields.Many2one('utility.customer', 'حساب الكهرباء', required=True)
    customer_id = fields.Many2one('utility.customer', related='account_id', store=True)
    partner_id = fields.Many2one('res.partner', related='customer_id.partner_id', store=True)
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    settlement_type = fields.Selection([
        ('credit', 'دائن (خصم للمشترك)'),
        ('debit', 'مدين (غرامة/إضافة على المشترك)'),
    ], string='نوع التسوية المالية', required=True)
    amount = fields.Float('مبلغ التسوية', required=True)
    reason = fields.Text('سبب التسوية المالية', required=True)
    date = fields.Date('تاريخ التسوية', default=fields.Date.today, readonly=True)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('applied', 'تم التطبيق'),
    ], string='الحالة', default='draft', readonly=True)

    move_id = fields.Many2one('account.move', string='القيد المحاسبي', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.financial.settlement') or _('New')
        return super().create(vals_list)

    def _get_company_config(self, company_field, config_key):
        company = self.env.company
        val = company[company_field]
        if val:
            return val.id if hasattr(val, 'id') else val
        return int(self.env['ir.config_parameter'].sudo().get_param(config_key, 0))

    def action_apply_settlement(self):
        self.ensure_one()
        if self.state == 'applied':
            raise ValidationError('تم تطبيق هذه التسوية بالفعل!')
            
        settlement_journal_id = self._get_company_config('settlement_journal_id', 'utility.settlement_journal_id')
        settlement_account_id = self._get_company_config('settlement_account_id', 'utility.settlement_account_id')
        
        if not settlement_journal_id or not settlement_account_id:
            raise ValidationError('يرجى تحديد يومية التسويات وحساب التسويات في إعدادات النظام أولاً.')
            
        partner = self.account_id.partner_id
        if not partner:
            raise ValidationError('حساب الكهرباء غير مربوط بعميل (Partner).')
            
        partner_account_id = partner.property_account_receivable_id.id
        if not partner_account_id:
            raise ValidationError('العميل ليس لديه حساب مستحقات (Receivable Account) معرف.')
            
        move_vals = {
            'journal_id': settlement_journal_id,
            'date': self.date or fields.Date.today(),
            'ref': f"تسوية مالية: {self.name} - {self.reason}",
            'line_ids': []
        }
        
        if self.settlement_type == 'credit':
            move_vals['line_ids'].append((0, 0, {
                'account_id': settlement_account_id,
                'name': self.reason,
                'debit': self.amount,
                'credit': 0.0,
            }))
            move_vals['line_ids'].append((0, 0, {
                'account_id': partner_account_id,
                'partner_id': partner.id,
                'name': self.reason,
                'debit': 0.0,
                'credit': self.amount,
            }))
        else:
            move_vals['line_ids'].append((0, 0, {
                'account_id': partner_account_id,
                'partner_id': partner.id,
                'name': self.reason,
                'debit': self.amount,
                'credit': 0.0,
            }))
            move_vals['line_ids'].append((0, 0, {
                'account_id': settlement_account_id,
                'name': self.reason,
                'debit': 0.0,
                'credit': self.amount,
            }))
            
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        
        self.move_id = move.id
        self.state = 'applied'
        return True
