from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityCustomerStatementWizard(models.TransientModel):
    _name = 'utility.customer.statement.wizard'
    _description = 'كشف حساب مشترك كهرباء'

    customer_id = fields.Many2one('utility.customer', string='الحساب', required=True)
    date_from = fields.Date(string='من تاريخ')
    date_to = fields.Date(string='إلى تاريخ', default=fields.Date.context_today)
    include_draft = fields.Boolean(string='تضمين المسودات')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'utility.customer' and self.env.context.get('active_id'):
            res.setdefault('customer_id', self.env.context['active_id'])
        return res

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_('تاريخ البداية يجب أن يكون قبل أو يساوي تاريخ النهاية.'))

    def _order_domain(self, before=False):
        self.ensure_one()
        domain = [('customer_id', '=', self.customer_id.id), ('state', '!=', 'cancel')]
        if not self.include_draft:
            domain.append(('state', 'not in', ('draft', 'sent')))
        if before and self.date_from:
            domain.append(('date_order', '<', self.date_from))
        else:
            if self.date_from:
                domain.append(('date_order', '>=', self.date_from))
            if self.date_to:
                domain.append(('date_order', '<=', '%s 23:59:59' % self.date_to))
        return domain

    def _payment_domain(self, before=False):
        self.ensure_one()
        domain = [('utility_sale_order_id.customer_id', '=', self.customer_id.id)]
        if not self.include_draft:
            domain.append(('state', '=', 'posted'))
        else:
            domain.append(('state', '!=', 'cancelled'))
        if before and self.date_from:
            domain.append(('date', '<', self.date_from))
        else:
            if self.date_from:
                domain.append(('date', '>=', self.date_from))
            if self.date_to:
                domain.append(('date', '<=', self.date_to))
        return domain

    def _get_opening_balance(self):
        self.ensure_one()
        if not self.date_from:
            return 0.0
        orders = self.env['sale.order'].search(self._order_domain(before=True))
        payments = self.env['account.payment'].search(self._payment_domain(before=True))
        return sum(orders.mapped('amount_total')) - sum(payments.mapped('amount'))

    def _get_statement_lines(self, opening_balance=None):
        self.ensure_one()
        entries = []
        orders = self.env['sale.order'].search(self._order_domain(), order='date_order, id')
        for order in orders:
            entries.append({
                'date': order.date_order.date() if order.date_order else False,
                'sequence': order.id,
                'kind': 'invoice',
                'ref': order.name,
                'description': _('فاتورة كهرباء'),
                'debit': order.amount_total,
                'credit': 0.0,
            })

        payments = self.env['account.payment'].search(self._payment_domain(), order='date, id')
        for payment in payments:
            entries.append({
                'date': payment.date,
                'sequence': payment.id,
                'kind': 'payment',
                'ref': payment.name or payment.ref,
                'description': _('سداد فاتورة %s') % (payment.utility_sale_order_id.name or ''),
                'debit': 0.0,
                'credit': payment.amount,
            })

        entries.sort(key=lambda line: (line['date'] or fields.Date.today(), line['kind'], line['sequence']))
        balance = self._get_opening_balance() if opening_balance is None else opening_balance
        for line in entries:
            balance += line['debit'] - line['credit']
            line['balance'] = balance
        return entries

    def _get_statement_totals(self):
        self.ensure_one()
        opening = self._get_opening_balance()
        lines = self._get_statement_lines(opening)
        debit = sum(line['debit'] for line in lines)
        credit = sum(line['credit'] for line in lines)
        return {
            'opening': opening,
            'debit': debit,
            'credit': credit,
            'closing': opening + debit - credit,
        }

    def _prepare_report_values(self):
        self.ensure_one()
        opening = self._get_opening_balance()
        lines = self._get_statement_lines(opening)
        debit = sum(line['debit'] for line in lines)
        credit = sum(line['credit'] for line in lines)
        return {
            'lines': lines,
            'totals': {
                'opening': opening,
                'debit': debit,
                'credit': credit,
                'closing': opening + debit - credit,
            },
        }

    def action_print_statement(self):
        self.ensure_one()
        return self.env.ref('utility_billing.action_report_customer_statement').report_action(self)