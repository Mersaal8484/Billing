import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityTransaction(models.Model):
    _name = 'utility.transaction'
    _description = 'سجل معاملات الدفع المسبق'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company, index=True)
    reference = fields.Char('المرجع', required=True, index=True, default=lambda self: _('جديد'))
    date = fields.Datetime('التاريخ', default=fields.Datetime.now, index=True)

    transaction_type = fields.Selection([
        ('vending', 'بيع'),
        ('fee', 'رسوم'),
        ('tax', 'ضريبة'),
        ('debt_recovery', 'استقطاع ديون'),
        ('reversal', 'عكس'),
        ('refund', 'استرداد'),
        ('adjustment', 'تسوية'),
        ('compensation', 'تعويض'),
    ], 'نوع المعاملة', required=True, index=True)

    amount = fields.Monetary('المبلغ', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)

    partner_id = fields.Many2one('res.partner', 'العميل', index=True)
    account_id = fields.Many2one('utility.customer', 'حساب المشترك', index=True)
    meter_id = fields.Many2one('utility.meter', 'العداد', index=True)

    vending_request_id = fields.Many2one('utility.vending.request', 'طلب البيع', index=True)
    pos_order_id = fields.Many2one('pos.order', 'أمر POS', index=True)
    reversal_id = fields.Many2one('utility.vending.reversal', 'العكس', index=True)
    adjustment_id = fields.Many2one('utility.prepaid.adjustment', 'التسوية', index=True)

    account_move_id = fields.Many2one('account.move', 'القيد المحاسبي', index=True)
    payment_id = fields.Many2one('account.payment', 'الدفعة', index=True)

    operator_id = fields.Many2one('res.users', 'المشغل', default=lambda self: self.env.user, index=True)
    notes = fields.Text('ملاحظات')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('جديد')) == _('جديد'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('utility.transaction') or _('جديد')
        return super().create(vals_list)


class UtilityPrepaidAccountingService(models.AbstractModel):
    _name = 'utility.prepaid.accounting.service'
    _description = 'خدمة محاسبة الدفع المسبق'

    def create_vending_entry(self, vending_request):
        vending_request.ensure_one()
        company = vending_request.company_id
        if not company.prepaid_liability_account_id:
            _logger.warning('No prepaid liability account configured for company %s', company.name)
            return self.env['account.move']

        move_vals = {
            'move_type': 'entry',
            'journal_id': company.prepaid_journal_id.id if company.prepaid_journal_id else
                          self.env['account.journal'].search([
                              ('company_id', '=', company.id),
                              ('type', '=', 'general'),
                          ], limit=1).id,
            'date': fields.Date.context_today(vending_request),
            'ref': _('قيد بيع مسبق - %s') % vending_request.reference,
            'line_ids': [],
        }

        debit_lines = []
        credit_lines = []

        total_amount = vending_request.gross_amount or 0.0
        if total_amount > 0:
            debit_lines.append({
                'account_id': company.prepaid_receivable_account_id.id
                              if company.prepaid_receivable_account_id
                              else company.prepaid_liability_account_id.id,
                'debit': total_amount,
                'credit': 0,
                'partner_id': vending_request.partner_id.id,
                'name': _('قبض بيع مسبق - %s') % vending_request.reference,
            })

        if vending_request.energy_amount > 0:
            if company.prepaid_revenue_policy == 'deferred':
                credit_lines.append({
                    'account_id': company.prepaid_liability_account_id.id,
                    'debit': 0,
                    'credit': vending_request.energy_amount,
                    'partner_id': vending_request.partner_id.id,
                    'name': _('إيراد مؤجل - %s') % vending_request.reference,
                })
            else:
                credit_lines.append({
                    'account_id': company.electricity_revenue_account_id.id,
                    'debit': 0,
                    'credit': vending_request.energy_amount,
                    'partner_id': vending_request.partner_id.id,
                    'name': _('إيراد كهرباء - %s') % vending_request.reference,
                })

        if vending_request.service_charge_amount > 0:
            credit_lines.append({
                'account_id': company.service_charge_revenue_account_id.id,
                'debit': 0,
                'credit': vending_request.service_charge_amount,
                'name': _('رسوم خدمة - %s') % vending_request.reference,
            })

        if vending_request.tax_amount > 0:
            credit_lines.append({
                'account_id': company.prepaid_tax_account_id.id,
                'debit': 0,
                'credit': vending_request.tax_amount,
                'name': _('ضريبة - %s') % vending_request.reference,
            })

        if vending_request.debt_recovery_amount > 0:
            credit_lines.append({
                'account_id': company.debt_recovery_account_id.id,
                'debit': 0,
                'credit': vending_request.debt_recovery_amount,
                'name': _('استقطاع ديون - %s') % vending_request.reference,
            })

        line_data = [(0, 0, line) for line in debit_lines + credit_lines]
        if line_data:
            move_vals['line_ids'] = line_data
            move = self.env['account.move'].create(move_vals)
            move.action_post()
            vending_request.account_move_id = move.id
            return move
        return self.env['account.move']

    def create_reversal_entry(self, reversal):
        reversal.ensure_one()
        company = reversal.company_id
        if not reversal.original_vending_request_id.account_move_id:
            return self.env['account.move']

        original_move = reversal.original_vending_request_id.account_move_id
        reverse_move = original_move._reverse_moves(
            default_values_list=[{
                'date': fields.Date.context_today(reversal),
                'ref': _('عكس قيد بيع مسبق - %s') % reversal.reference,
            }],
            cancel=False,
        )
        reversal.account_move_id = reverse_move.id
        return reverse_move

    def create_adjustment_entry(self, adjustment):
        adjustment.ensure_one()
        company = adjustment.company_id
        if not adjustment.amount:
            return self.env['account.move']

        journal = company.prepaid_journal_id or self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', 'general'),
        ], limit=1)

        move_vals = {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': fields.Date.context_today(adjustment),
            'ref': _('قيد تسوية - %s') % adjustment.reference,
        }

        lines = []
        if adjustment.adjustment_type in ('credit', 'compensation'):
            lines.append({
                'account_id': company.prepaid_adjustment_account_id.id,
                'debit': adjustment.amount,
                'credit': 0,
                'partner_id': adjustment.partner_id.id,
                'name': _('تسوية دائنة - %s') % adjustment.reference,
            })
            lines.append({
                'account_id': company.electricity_revenue_account_id.id,
                'debit': 0,
                'credit': adjustment.amount,
                'partner_id': adjustment.partner_id.id,
                'name': _('تسوية دائنة - %s') % adjustment.reference,
            })
        else:
            lines.append({
                'account_id': company.electricity_revenue_account_id.id,
                'debit': adjustment.amount,
                'credit': 0,
                'partner_id': adjustment.partner_id.id,
                'name': _('تسوية مدينة - %s') % adjustment.reference,
            })
            lines.append({
                'account_id': company.prepaid_adjustment_account_id.id,
                'debit': 0,
                'credit': adjustment.amount,
                'partner_id': adjustment.partner_id.id,
                'name': _('تسوية مدينة - %s') % adjustment.reference,
            })

        move_vals['line_ids'] = [(0, 0, l) for l in lines]
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        adjustment.account_move_id = move.id
        return move
