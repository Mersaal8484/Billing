from odoo import api, fields, models, _


class PropertyMaintenance(models.Model):
    _name = 'property.maintenance'
    _description = 'Maintenance Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_requested desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', related='property_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    name = fields.Char(string='Request Reference', required=True, index=True,
                       default=lambda self: _('New'))
    property_id = fields.Many2one('property.property', string='Property', index=True)
    building_id = fields.Many2one('property.building', string='Building', index=True)
    unit_id = fields.Many2one('property.unit', string='Unit', index=True)
    tenant_id = fields.Many2one('property.tenant', string='Tenant', index=True)
    owner_id = fields.Many2one('property.owner', string='Property Owner', related='property_id.owner_id', store=True, readonly=False)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (Unit Cost Center)', related='unit_id.analytic_account_id', store=True, readonly=False)
    move_id = fields.Many2one('account.move', string='Maintenance Journal Entry', readonly=True, tracking=True)

    maintenance_type = fields.Many2one('property.maintenance.type',
                                       string='Maintenance Type', required=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal', index=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    date_requested = fields.Datetime(string='Request Date', default=fields.Datetime.now,
                                     required=True)
    date_scheduled = fields.Date(string='Scheduled Date')
    date_completed = fields.Date(string='Completed Date')

    description = fields.Text(string='Description', required=True)
    assigned_to = fields.Many2one('res.users', string='Assigned To', tracking=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor/Contractor')

    parts_cost = fields.Monetary(string='Parts Cost', default=0.0)
    labor_cost = fields.Monetary(string='Labor Cost', default=0.0)
    other_cost = fields.Monetary(string='Other Cost', default=0.0)
    total_cost = fields.Monetary(string='Total Cost',
                                 compute='_compute_total_cost', store=True)

    before_images = fields.One2many('property.maintenance.image', 'maintenance_id',
                                    string='Before Photos', domain=[('image_type', '=', 'before')])
    after_images = fields.One2many('property.maintenance.image', 'maintenance_id',
                                   string='After Photos', domain=[('image_type', '=', 'after')])

    resolution = fields.Text(string='Resolution/Notes')
    completion_report = fields.Text(string='Completion Report')

    _sql_constraints = [
        ('check_costs', 'CHECK(parts_cost >= 0 AND labor_cost >= 0 AND other_cost >= 0)',
         'Costs must be positive!'),
    ]

    @api.depends('parts_cost', 'labor_cost', 'other_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.parts_cost + rec.labor_cost + rec.other_cost

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_start(self):
        self.write({
            'state': 'in_progress',
            'date_scheduled': fields.Date.today(),
        })

    def action_done(self):
        for rec in self:
            if rec.total_cost > 0 and not rec.move_id:
                journal = rec.property_id.maintenance_journal_id or rec.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', rec.company_id.id)], limit=1)
                expense_account = rec.property_id.maintenance_expense_account_id or rec.env['account.account'].search([('internal_group', '=', 'expense'), ('company_id', '=', rec.company_id.id)], limit=1)
                credit_account = rec.property_id.cash_account_id or rec.env['account.account'].search([('internal_group', 'in', ('asset', 'liability')), ('company_id', '=', rec.company_id.id)], limit=1)
                
                if journal and expense_account and credit_account:
                    partner_id = rec.owner_id.partner_id.id if rec.owner_id else False
                    move_vals = {
                        'journal_id': journal.id,
                        'date': fields.Date.today(),
                        'ref': f'Maintenance Expense: {rec.name} - {rec.unit_id.display_name or rec.property_id.name}',
                        'line_ids': [
                            (0, 0, {
                                'name': f'Maintenance Expense - {rec.name}',
                                'account_id': expense_account.id,
                                'partner_id': partner_id,
                                'debit': rec.total_cost,
                                'credit': 0.0,
                                'analytic_distribution': {str(rec.analytic_account_id.id): 100} if rec.analytic_account_id else False,
                            }),
                            (0, 0, {
                                'name': f'Maintenance Payable/Cash - {rec.name}',
                                'account_id': credit_account.id,
                                'partner_id': partner_id,
                                'debit': 0.0,
                                'credit': rec.total_cost,
                            }),
                        ]
                    }
                    move = rec.env['account.move'].create(move_vals)
                    move.action_post()
                    rec.move_id = move.id

        self.write({
            'state': 'done',
            'date_completed': fields.Date.today(),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('property.maintenance')
                vals['name'] = seq or '/'
        return super().create(vals_list)


class PropertyMaintenanceImage(models.Model):
    _name = 'property.maintenance.image'
    _description = 'Maintenance Image'

    maintenance_id = fields.Many2one('property.maintenance', string='Maintenance',
                                     required=True, ondelete='cascade')
    name = fields.Char(string='Name')
    image = fields.Binary(string='Image', required=True, attachment=True)
    image_type = fields.Selection([('before', 'Before'), ('after', 'After')],
                                  string='Type', default='before')


class PropertyMaintenanceType(models.Model):
    _name = 'property.maintenance.type'
    _description = 'Maintenance Type'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
