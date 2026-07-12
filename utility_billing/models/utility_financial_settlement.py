from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityFinancialSettlement(models.Model):
    _name = 'utility.financial.settlement'
    _description = 'تسوية مالية'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    active = fields.Boolean('نشط', default=True)
    name = fields.Char('رقم التسوية المالية', default=lambda self: _('جديد'), readonly=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='العملة',
        store=True,
        readonly=True,
    )
    account_id = fields.Many2one('utility.customer', 'حساب الكهرباء', required=True)
    partner_id = fields.Many2one('res.partner', related='account_id.partner_id', store=True, string='العميل')
    region_id = fields.Many2one(related='partner_id.region_id', store=True, string='المنطقة')
    area_id = fields.Many2one(related='partner_id.area_id', store=True, string='المنطقة الفرعية')
    settlement_type = fields.Selection([
        ('credit', 'دائن (خصم للمشترك)'),
        ('debit', 'مدين (غرامة/إضافة على المشترك)'),
    ], string='نوع التسوية المالية', required=True)
    amount = fields.Monetary('مبلغ التسوية', required=True, currency_field='currency_id')
    reason = fields.Text('سبب التسوية المالية', required=True)
    date = fields.Date('تاريخ التسوية', default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('applied', 'تم التطبيق'),
    ], string='الحالة', default='draft')

    move_id = fields.Many2one('account.move', string='القيد المحاسبي', readonly=True)

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f'[{rec.name}] {rec.account_id.partner_id.name or ""}'))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('جديد')) == _('جديد'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.financial.settlement') or _('جديد')
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

        journal = self.env['account.journal'].browse(settlement_journal_id)
        if journal.type != 'sale':
            sale_journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if sale_journal:
                journal = sale_journal
            else:
                raise ValidationError(
                    'اليومية المحددة للتسويات ليست يومية مبيعات. '
                    'يرجى تحديد يومية مبيعات في إعدادات النظام أو إنشاء واحدة.')

        partner = self.account_id.partner_id
        if not partner:
            raise ValidationError('حساب الكهرباء غير مربوط بعميل (Partner).')

        move_type = 'out_refund' if self.settlement_type == 'credit' else 'out_invoice'

        move_vals = {
            'journal_id': journal.id,
            'date': self.date or fields.Date.today(),
            'ref': f"تسوية مالية: {self.name} - {self.reason}",
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_line_ids': [(0, 0, {
                'name': self.reason,
                'quantity': 1.0,
                'price_unit': self.amount,
                'account_id': settlement_account_id,
                'tax_ids': False,
            })]
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()

        self.move_id = move.id
        self.state = 'applied'
        return {
            'type': 'ir.actions.act_window',
            'name': _('القيد المحاسبي'),
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }

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
