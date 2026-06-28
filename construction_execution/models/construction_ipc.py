from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import date_utils


class ConstructionIpc(models.Model):
    _name = 'construction.ipc'
    _description = 'Interim Payment Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True
    _rec_name = 'name'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, tracking=True, index=True)
    name = fields.Char(string='IPC Reference', required=True, index=True)
    date = fields.Date(string='IPC Date', required=True, default=fields.Date.today,
                       tracking=True)
    period_from = fields.Date(string='Period From', required=True, tracking=True)
    period_to = fields.Date(string='Period To', required=True, tracking=True)
    ipc_number = fields.Integer(string='IPC Number', required=True,
                                help='Sequential IPC number for the project')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
        ('certified', 'Certified'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    submitted_by = fields.Many2one('res.users', string='Submitted By', tracking=True)
    reviewed_by = fields.Many2one('res.users', string='Reviewed By', tracking=True)
    certified_by = fields.Many2one('res.users', string='Certified By', tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True)

    line_ids = fields.One2many('construction.ipc.line', 'ipc_id',
                               string='IPC Lines', copy=True)
    line_count = fields.Integer(string='Line Count',
                                compute='_compute_line_count', store=True)

    prev_work_done = fields.Monetary(string='Previous Work Done', default=0.0,
                                     help='Total value certified in previous IPCs')
    current_work_done = fields.Monetary(string='Current Work Done',
                                        compute='_compute_amounts', store=True)
    total_work_done = fields.Monetary(string='Total Work Done',
                                      compute='_compute_amounts', store=True)

    retention_percent = fields.Float(string='Retention %', default=5.0,
                                     digits=(5, 2))
    retention_amount = fields.Monetary(string='Retention Amount',
                                       compute='_compute_amounts', store=True)
    retention_release = fields.Monetary(string='Retention Release', default=0.0)

    advance_paid = fields.Monetary(string='Advance Paid', default=0.0)
    advance_recovery = fields.Monetary(string='Advance Recovery', default=0.0)
    advance_balance = fields.Monetary(string='Advance Balance',
                                      compute='_compute_amounts', store=True)

    previous_paid = fields.Monetary(string='Previously Paid', default=0.0)
    tax_percent = fields.Float(string='Tax %', default=0.0, digits=(5, 2))
    tax_amount = fields.Monetary(string='Tax Amount',
                                 compute='_compute_amounts', store=True)
    gross_amount = fields.Monetary(string='Gross Amount',
                                   compute='_compute_amounts', store=True)
    net_amount = fields.Monetary(string='Net Amount',
                                 compute='_compute_amounts', store=True)
    total_approved_amount = fields.Monetary(string='Total Approved',
                                            compute='_compute_amounts', store=True)

    invoice_id = fields.Many2one('account.move', string='Customer Invoice')
    payment_id = fields.Many2one('account.payment', string='Payment')
    paid_date = fields.Date(string='Payment Date')
    payment_reference = fields.Char(string='Payment Reference')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order',
        index=True, help='Sale order linked to this IPC')
    sale_order_line_ids = fields.One2many('sale.order.line',
        'construction_ipc_line_id', string='Sale Order Lines',
        help='Sale order lines generated from this IPC')

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('ipc_number_project_unique', 'UNIQUE(ipc_number, project_id)',
         'IPC number must be unique per project!'),
    ]

    @api.depends('line_ids', 'line_ids.amount', 'retention_percent',
                 'retention_release', 'advance_paid', 'advance_recovery',
                 'tax_percent', 'previous_paid', 'prev_work_done')
    def _compute_amounts(self):
        for rec in self:
            rec.current_work_done = sum(rec.line_ids.mapped('amount'))
            rec.total_work_done = rec.prev_work_done + rec.current_work_done
            rec.retention_amount = rec.current_work_done * rec.retention_percent / 100
            rec.advance_balance = rec.advance_paid - rec.advance_recovery
            rec.gross_amount = rec.current_work_done - rec.retention_amount + rec.retention_release - rec.advance_recovery
            rec.tax_amount = rec.gross_amount * rec.tax_percent / 100
            rec.net_amount = rec.gross_amount - rec.tax_amount
            rec.total_approved_amount = rec.prev_work_done + rec.net_amount

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_submit(self):
        if not self.line_ids:
            raise UserError(_('Cannot submit an IPC with no lines!'))
        self.write({
            'state': 'submitted',
            'submitted_by': self.env.user.id,
        })

    def action_review(self):
        self.write({
            'state': 'reviewed',
            'reviewed_by': self.env.user.id,
        })

    def action_certify(self):
        self.write({
            'state': 'certified',
            'certified_by': self.env.user.id,
        })

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
        })

    def action_paid(self):
        self.write({
            'state': 'paid',
            'paid_date': fields.Date.today(),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def _get_income_account(self):
        account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        return account.id if account else False

    def action_create_sale_order(self):
        self.ensure_one()
        if self.sale_order_id:
            raise UserError(_('A sale order already exists for this IPC!'))
        lines = self.line_ids.filtered(lambda l: l.amount)
        if not lines:
            raise UserError(_('No IPC lines with amounts!'))
        generic_product = self.env['product.product'].search([
            ('detailed_type', '=', 'service'),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        if not generic_product:
            generic_product = self.env['product.product'].create({
                'name': 'Construction Works / أعمال مقاولات',
                'detailed_type': 'service',
                'company_id': self.company_id.id,
                'list_price': 1.0,
            })
        so_vals = {
            'partner_id': self.project_id.partner_id.id or self.env.user.partner_id.id,
            'construction_project_id': self.project_id.id,
            'construction_ipc_id': self.id,
            'date_order': fields.Datetime.now(),
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id or self.company_id.currency_id.id,
            'client_order_ref': self.name,
            'order_line': [],
        }
        for line in lines:
            so_vals['order_line'].append((0, 0, {
                'product_id': generic_product.id,
                'name': line.name or line.boq_item_id.display_name,
                'product_uom_qty': line.current_quantity or 1.0,
                'product_uom': line.boq_item_id.unit.id if line.boq_item_id else generic_product.uom_id.id,
                'price_unit': line.rate,
                'construction_boq_item_id': line.boq_item_id.id,
                'construction_ipc_line_id': line.id,
            }))
        so = self.env['sale.order'].create(so_vals)
        self.sale_order_id = so.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': so.id,
        }

    def action_create_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            raise UserError(_('An invoice already exists for this IPC!'))
        income_account = self._get_income_account()
        analytic_distribution = {}
        if self.project_id.analytic_account_id:
            analytic_distribution = {str(self.project_id.analytic_account_id.id): 100}
        invoice_lines = []
        for line in self.line_ids.filtered(lambda l: l.amount):
            invoice_lines.append((0, 0, {
                'name': f'{line.name or line.boq_item_id.display_name}: '
                        f'Qty {line.current_quantity} x Rate {line.rate}',
                'quantity': line.current_quantity or 1.0,
                'price_unit': line.rate,
                'account_id': income_account,
                'analytic_distribution': analytic_distribution or None,
            }))
        if not invoice_lines:
            invoice_lines.append((0, 0, {
                'name': f'IPC {self.name}: Work Done from {self.period_from} to {self.period_to}',
                'quantity': 1.0,
                'price_unit': self.net_amount,
                'account_id': income_account,
                'analytic_distribution': analytic_distribution or None,
            }))
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.project_id.partner_id.id,
            'invoice_date': fields.Date.today(),
            'narration': f'IPC {self.name} - {self.project_id.name}',
            'invoice_line_ids': invoice_lines,
            'invoice_origin': self.name,
            'ref': f'IPC:{self.name}',
        })
        self.invoice_id = invoice.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Invoice'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    @api.model
    def _get_next_ipc_number(self, project_id):
        last_ipc = self.search([('project_id', '=', project_id)],
                               order='ipc_number desc', limit=1)
        return (last_ipc.ipc_number or 0) + 1

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                seq = self.env['ir.sequence'].next_by_code('construction.ipc')
                vals['name'] = seq or '/'
            if not vals.get('ipc_number'):
                vals['ipc_number'] = self._get_next_ipc_number(vals.get('project_id'))
            if not vals.get('prev_work_done') and vals.get('project_id'):
                prev_ipcs = self.search([
                    ('project_id', '=', vals['project_id']),
                    ('state', 'in', ('certified', 'approved', 'paid')),
                ], order='ipc_number desc', limit=1)
                if prev_ipcs:
                    vals['prev_work_done'] = prev_ipcs[0].total_approved_amount
        return super().create(vals_list)


class ConstructionIpcLine(models.Model):
    _name = 'construction.ipc.line'
    _description = 'IPC Line'
    _order = 'ipc_id, sequence'

    active = fields.Boolean(default=True)
    ipc_id = fields.Many2one('construction.ipc', string='IPC',
                             required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one('construction.project',
                                 related='ipc_id.project_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='ipc_id.company_id',
                                 store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    sequence = fields.Integer(default=10)
    boq_item_id = fields.Many2one('construction.boq.item', string='BOQ Item',
                                  required=True, index=True)
    name = fields.Char(string='Description', compute='_compute_name', store=True)

    previous_quantity = fields.Float(string='Previous Qty', digits=(16, 3))
    current_quantity = fields.Float(string='Current Qty', default=0.0,
                                    digits=(16, 3))
    total_quantity = fields.Float(string='Total Qty', compute='_compute_totals',
                                  store=True, digits=(16, 3))

    rate = fields.Monetary(string='Rate', default=0.0)
    previous_amount = fields.Monetary(string='Previous Amount',
                                      compute='_compute_amounts', store=True)
    current_amount = fields.Monetary(string='Current Amount',
                                     compute='_compute_amounts', store=True)
    amount = fields.Monetary(string='Total Amount',
                             compute='_compute_amounts', store=True)

    note = fields.Text(string='Notes')

    @api.depends('boq_item_id', 'boq_item_id.name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.boq_item_id.display_name if rec.boq_item_id else ''

    @api.depends('previous_quantity', 'current_quantity')
    def _compute_totals(self):
        for rec in self:
            rec.total_quantity = rec.previous_quantity + rec.current_quantity

    @api.depends('previous_quantity', 'current_quantity', 'total_quantity', 'rate')
    def _compute_amounts(self):
        for rec in self:
            rec.previous_amount = rec.previous_quantity * rec.rate
            rec.current_amount = rec.current_quantity * rec.rate
            rec.amount = rec.total_quantity * rec.rate

    @api.onchange('boq_item_id')
    def _onchange_boq_item(self):
        if self.boq_item_id:
            self.name = self.boq_item_id.display_name
            self.rate = self.boq_item_id.rate
            self.total_quantity = self.boq_item_id.executed_quantity

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.boq_item_id:
                line.boq_item_id.executed_quantity = line.total_quantity
        return lines

    def write(self, vals):
        result = super().write(vals)
        if 'total_quantity' in vals or 'current_quantity' in vals:
            for line in self:
                if line.boq_item_id:
                    line.boq_item_id.executed_quantity = line.total_quantity
        return result


    @api.model
    def cron_send_ipc_reminder(self):
        projects = self.env['construction.project'].search([
            ('active', '=', True),
            ('project_stage', 'in', ('execution', 'planning')),
        ])
        for project in projects:
            last_ipc = self.search([
                ('project_id', '=', project.id),
                ('state', '=', 'paid'),
            ], order='ipc_number desc', limit=1)
            days_since = 0
            if last_ipc and last_ipc.date:
                days_since = (fields.Date.today() - last_ipc.date).days
            if days_since >= 30 or not last_ipc:
                existing_draft = self.search([
                    ('project_id', '=', project.id),
                    ('state', '=', 'draft'),
                ], limit=1)
                if not existing_draft:
                    new_ipc = self.create({
                        'project_id': project.id,
                        'date': fields.Date.today(),
                        'period_from': date_utils.subtract(fields.Date.today(), months=1),
                        'period_to': fields.Date.today(),
                    })
                    new_ipc.message_post(
                        body=f'Auto-generated IPC reminder for {project.name}',
                        subject='IPC Reminder',
                    )


class ConstructionIpcStatus(models.Model):
    _name = 'construction.ipc.status'
    _description = 'IPC Status'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
