from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ConstructionCashflow(models.Model):
    _name = 'construction.cashflow'
    _description = 'Cash Flow'
    _order = 'date, id'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, index=True)
    name = fields.Char(string='Description', compute='_compute_name', store=True)

    date = fields.Date(string='Date', required=True, index=True)
    period = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], string='Period Type', default='monthly', index=True)

    flow_type = fields.Selection([
        ('income', 'Income/Inflow'),
        ('expense', 'Expense/Outflow'),
    ], string='Flow Type', required=True, default='income', index=True)

    category = fields.Selection([
        ('client_payment', 'Client Payment'),
        ('advance_payment', 'Advance Payment'),
        ('retention', 'Retention Release'),
        ('material', 'Material Purchase'),
        ('labor', 'Labor Cost'),
        ('equipment', 'Equipment Cost'),
        ('subcontract', 'Subcontractor'),
        ('overhead', 'Overhead'),
        ('other', 'Other'),
    ], string='Category', required=True, default='client_payment')

    forecast_amount = fields.Monetary(string='Forecast Amount', default=0.0)
    actual_amount = fields.Monetary(string='Actual Amount', default=0.0,
                                    help='Manual entry when no source document is linked. '
                                         'Auto-filled from linked invoice, payment, or IPC.')
    has_source = fields.Boolean(string='Has Source Document',
                                compute='_compute_has_source')
    variance = fields.Monetary(string='Variance',
                               compute='_compute_variance', store=True)

    planned_date = fields.Date(string='Planned Date')
    actual_date = fields.Date(string='Actual Date')
    is_received = fields.Boolean(string='Received/Paid', default=False)
    reference = fields.Char(string='Reference')
    partner_id = fields.Many2one('res.partner', string='Partner')
    ipc_id = fields.Many2one('construction.ipc', string='Related IPC')
    invoice_id = fields.Many2one('account.move', string='Related Invoice')
    payment_id = fields.Many2one('account.payment', string='Related Payment')
    source_doc_name = fields.Char(string='Source Document', compute='_compute_source_doc_name')

    note = fields.Text(string='Notes')

    @api.depends('forecast_amount', 'actual_amount')
    def _compute_variance(self):
        for rec in self:
            rec.variance = rec.actual_amount - rec.forecast_amount

    @api.depends('category', 'project_id', 'date')
    def _compute_name(self):
        for rec in self:
            cat = dict(rec._fields['category'].selection).get(rec.category, '')
            rec.name = f'{cat} - {rec.date}' if rec.date else cat

    @api.depends('invoice_id', 'payment_id', 'ipc_id')
    def _compute_has_source(self):
        for rec in self:
            rec.has_source = bool(rec.invoice_id or rec.payment_id or rec.ipc_id)

    @api.depends('invoice_id', 'payment_id', 'ipc_id')
    def _compute_source_doc_name(self):
        for rec in self:
            if rec.invoice_id:
                rec.source_doc_name = f'{_("Invoice")}: {rec.invoice_id.name}'
            elif rec.payment_id:
                rec.source_doc_name = f'{_("Payment")}: {rec.payment_id.name}'
            elif rec.ipc_id:
                rec.source_doc_name = f'{_("IPC")}: {rec.ipc_id.name}'
            else:
                rec.source_doc_name = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._auto_fill_actual(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._auto_fill_actual(vals)
        return super().write(vals)

    def _auto_fill_actual(self, vals):
        if vals.get('invoice_id'):
            invoice = self.env['account.move'].browse(vals['invoice_id'])
            vals['actual_amount'] = invoice.amount_total_signed or 0.0
        elif vals.get('payment_id'):
            payment = self.env['account.payment'].browse(vals['payment_id'])
            vals['actual_amount'] = payment.amount or 0.0
        elif vals.get('ipc_id'):
            ipc = self.env['construction.ipc'].browse(vals['ipc_id'])
            vals['actual_amount'] = ipc.net_amount or 0.0

    def action_sync_from_source(self):
        self.ensure_one()
        if self.invoice_id:
            self.actual_amount = self.invoice_id.amount_total_signed
        elif self.payment_id:
            self.actual_amount = self.payment_id.amount
        elif self.ipc_id:
            self.actual_amount = self.ipc_id.net_amount
        else:
            raise UserError(_('No source document linked to sync from.'))

    def action_open_invoice(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Invoice'),
                'res_model': 'account.move', 'view_mode': 'form',
                'res_id': self.invoice_id.id}

    def action_open_payment(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Payment'),
                'res_model': 'account.payment', 'view_mode': 'form',
                'res_id': self.payment_id.id}

    def action_open_ipc(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('IPC'),
                'res_model': 'construction.ipc', 'view_mode': 'form',
                'res_id': self.ipc_id.id}
