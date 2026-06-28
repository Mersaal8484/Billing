from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ConstructionBoq(models.Model):
    _name = 'construction.boq'
    _description = 'Bill of Quantities'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code, id'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    project_id = fields.Many2one('construction.project', string='Project',
                                 required=True, tracking=True, index=True)
    name = fields.Char(string='BOQ Name', required=True, tracking=True,
                       translate=True)
    code = fields.Char(string='BOQ Code', required=True, tracking=True, index=True)
    version = fields.Char(string='Version', default='1.0', tracking=True)
    description = fields.Text(string='Description', translate=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('revised', 'Revised'),
    ], string='Status', default='draft', tracking=True, index=True)

    date = fields.Date(string='Date', default=fields.Date.today)
    approved_date = fields.Date(string='Approval Date')
    approved_by = fields.Many2one('res.users', string='Approved By')

    total_quantity = fields.Float(string='Total Quantity',
                                  compute='_compute_totals', store=True,
                                  digits=(16, 3))
    total_amount = fields.Monetary(string='Total Amount',
                                   compute='_compute_totals', store=True)
    item_count = fields.Integer(string='Item Count',
                                compute='_compute_totals', store=True)

    section_ids = fields.One2many('construction.boq.section', 'boq_id',
                                  string='Sections', copy=True)
    item_ids = fields.One2many('construction.boq.item', 'boq_id',
                               string='Items', copy=True)

    sale_order_ids = fields.One2many('sale.order',
        'construction_boq_id', string='Sales Orders')
    sale_order_count = fields.Integer(string='Sale Order Count',
        compute='_compute_sale_order_count')

    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('boq_code_project_unique', 'UNIQUE(code, project_id)',
         'BOQ code must be unique per project!'),
    ]

    @api.depends('item_ids.amount', 'item_ids.quantity')
    def _compute_totals(self):
        for rec in self:
            items = rec.item_ids
            rec.total_quantity = sum(items.mapped('quantity'))
            rec.total_amount = sum(items.mapped('amount'))
            rec.item_count = len(items)

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = self.env['sale.order'].search_count(
                [('construction_boq_id', '=', rec.id)])

    def action_create_sale_order(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Only approved BOQs can create sale orders!'))
        items = self.item_ids.filtered(lambda i: not i.parent_id and i.amount)
        if not items:
            raise UserError(_('No BOQ items with amounts found!'))
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
        analytic_distribution = {}
        if self.project_id.analytic_account_id:
            analytic_distribution = {str(self.project_id.analytic_account_id.id): 100}
        so_vals = {
            'partner_id': self.project_id.partner_id.id or self.env.user.partner_id.id,
            'construction_project_id': self.project_id.id,
            'construction_boq_id': self.id,
            'date_order': fields.Datetime.now(),
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id or self.company_id.currency_id.id,
            'order_line': [],
        }
        for item in items:
            so_vals['order_line'].append((0, 0, {
                'product_id': generic_product.id,
                'name': f'[{item.code}] {item.name}',
                'product_uom_qty': item.quantity,
                'product_uom': item.unit.id,
                'price_unit': item.rate,
                'construction_boq_item_id': item.id,
                'analytic_distribution': analytic_distribution or None,
            }))
        so = self.env['sale.order'].create(so_vals)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': so.id,
        }

    def action_open_sale_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Orders'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('construction_boq_id', '=', self.id)],
        }

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_date': fields.Date.today(),
            'approved_by': self.env.user.id,
        })
        auto_tasks = self.env['ir.config_parameter'].sudo().get_param(
            'construction.auto_create_tasks', default='False') == 'True'
        if auto_tasks:
            for boq in self:
                if boq.project_id and boq.project_id.project_project_id:
                    try:
                        boq.project_id.action_create_tasks_from_boq()
                    except Exception:
                        pass

    def action_revise(self):
        self.write({'state': 'revised'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                seq = self.env['ir.sequence'].next_by_code('construction.boq')
                vals['code'] = seq or '/'
        return super().create(vals_list)


class ConstructionBoqStatus(models.Model):
    _name = 'construction.boq.status'
    _description = 'BOQ Status'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
