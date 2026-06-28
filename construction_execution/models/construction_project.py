from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ConstructionProject(models.Model):
    _name = 'construction.project'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id desc'
    _rec_name = 'name'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='Client', tracking=True)
    user_id = fields.Many2one('res.users', string='Project Manager',
                              default=lambda self: self.env.user, tracking=True)
    project_manager_id = fields.Many2one('res.users', string='Project Director',
                                         tracking=True)
    consultant_id = fields.Many2one('res.partner', string='Consultant/Engineer')
    contractor_id = fields.Many2one('res.partner', string='Main Contractor')
    subcontractor_ids = fields.Many2many('res.partner', string='Subcontractors')

    name = fields.Char(string='Project Name', required=True, tracking=True,
                       translate=True)
    code = fields.Char(string='Project Code', required=True, tracking=True,
                       index=True)
    description = fields.Text(string='Description', translate=True)
    arabic_name = fields.Char(string='Arabic Name')
    arabic_description = fields.Text(string='Arabic Description')

    project_type = fields.Selection([
        ('building', 'Building'),
        ('infrastructure', 'Infrastructure'),
        ('industrial', 'Industrial'),
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('road', 'Road & Bridge'),
        ('utility', 'Utility'),
        ('other', 'Other'),
    ], string='Project Type', default='building', tracking=True)

    project_stage = fields.Selection([
        ('tender', 'Tender'),
        ('awarded', 'Awarded'),
        ('planning', 'Planning'),
        ('execution', 'Execution'),
        ('closeout', 'Closeout'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ], string='Stage', default='planning', tracking=True)

    analytic_account_id = fields.Many2one('account.analytic.account',
        string='Analytic Account', tracking=True, index=True,
        help='Linked analytic account for tracking costs and timesheets')
    project_project_id = fields.Many2one('project.project',
        string='Odoo Project', tracking=True, index=True,
        help='Linked Odoo project for task management and collaboration')
    sale_order_ids = fields.One2many('sale.order', 'construction_project_id',
        string='Sales Orders')
    timesheet_line_ids = fields.One2many('account.analytic.line',
        'construction_project_id', string='Timesheet Lines')
    total_hours_spent = fields.Float(string='Total Hours Spent',
        compute='_compute_timesheet_hours', digits=(16, 2))
    total_timesheet_cost = fields.Monetary(string='Total Timesheet Cost',
        compute='_compute_timesheet_hours')

    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)
    duration_days = fields.Integer(string='Duration (Days)', compute='_compute_duration')
    remaining_days = fields.Integer(string='Remaining Days', compute='_compute_remaining_days')
    progress_percent = fields.Float(string='Progress %', compute='_compute_progress',
                                    group_operator='avg', digits=(5, 2), store=True)

    location = fields.Char(string='Location')
    city = fields.Char(string='City')
    country_id = fields.Many2one('res.country', string='Country')
    latitude = fields.Float(string='Latitude', digits=(9, 6))
    longitude = fields.Float(string='Longitude', digits=(9, 6))

    contract_amount = fields.Monetary(string='Contract Amount', currency_field='currency_id',
                                      tracking=True)
    contract_type = fields.Selection([
        ('lumpsum', 'Lump Sum'),
        ('unit_price', 'Unit Price'),
        ('cost_plus', 'Cost Plus'),
        ('target', 'Target Price'),
        ('design_build', 'Design & Build'),
    ], string='Contract Type', default='lumpsum', tracking=True)

    boq_count = fields.Integer(string='BOQ Count', compute='_compute_boq_count')
    variation_count = fields.Integer(string='Variation Orders',
                                     compute='_compute_variation_count')
    progress_count = fields.Integer(string='Progress Records',
                                    compute='_compute_progress_count')
    ipc_count = fields.Integer(string='IPC Count', compute='_compute_ipc_count')
    material_request_count = fields.Integer(string='Material Requests',
                                            compute='_compute_material_request_count')

    boq_ids = fields.One2many('construction.boq', 'project_id', string='BOQs')
    variation_ids = fields.One2many('construction.variation', 'project_id',
                                    string='Variations')
    progress_ids = fields.One2many('construction.progress', 'project_id',
                                   string='Progress Records')
    ipc_ids = fields.One2many('construction.ipc', 'project_id', string='IPCs')
    material_request_ids = fields.One2many('construction.material.request',
                                           'project_id', string='Material Requests')
    budget_ids = fields.One2many('construction.budget', 'project_id',
                                 string='Budgets')
    cost_entry_ids = fields.One2many('construction.cost.entry', 'project_id',
                                     string='Cost Entries')
    cashflow_ids = fields.One2many('construction.cashflow', 'project_id',
                                   string='Cash Flow')

    project_value = fields.Monetary(string='Project Value',
                                    compute='_compute_financials')
    executed_value = fields.Monetary(string='Executed Value',
                                     compute='_compute_financials')
    remaining_value = fields.Monetary(string='Remaining Value',
                                      compute='_compute_financials')
    budget_cost = fields.Monetary(string='Budget Cost', compute='_compute_financials')
    actual_cost = fields.Monetary(string='Actual Cost', compute='_compute_financials')
    cost_variance = fields.Monetary(string='Cost Variance',
                                    compute='_compute_financials')
    spi = fields.Float(string='SPI', compute='_compute_evm', digits=(12, 4))
    cpi = fields.Float(string='CPI', compute='_compute_evm', digits=(12, 4))
    eac = fields.Monetary(string='EAC', compute='_compute_evm')
    etc = fields.Monetary(string='ETC', compute='_compute_evm')
    vac = fields.Monetary(string='VAC', compute='_compute_evm')

    note = fields.Html(string='Notes')
    internal_note = fields.Text(string='Internal Notes')

    _sql_constraints = [
        ('code_company_unique', 'UNIQUE(code, company_id)',
         'Project code must be unique per company!'),
    ]

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duration_days = (rec.end_date - rec.start_date).days
            else:
                rec.duration_days = 0

    @api.depends('end_date')
    def _compute_remaining_days(self):
        for rec in self:
            if rec.end_date:
                rec.remaining_days = (rec.end_date - fields.Date.today()).days
            else:
                rec.remaining_days = 0

    @api.depends('progress_ids.executed_percent', 'progress_ids.state')
    def _compute_progress(self):
        for rec in self:
            progresses = rec.progress_ids.filtered(lambda p: p.state == 'approved')
            if progresses:
                rec.progress_percent = sum(progresses.mapped('executed_percent')) / len(progresses)
            else:
                rec.progress_percent = 0.0

    def _compute_boq_count(self):
        for rec in self:
            rec.boq_count = self.env['construction.boq'].search_count(
                [('project_id', '=', rec.id)])

    def _compute_variation_count(self):
        for rec in self:
            rec.variation_count = self.env['construction.variation'].search_count(
                [('project_id', '=', rec.id)])

    def _compute_progress_count(self):
        for rec in self:
            rec.progress_count = self.env['construction.progress'].search_count(
                [('project_id', '=', rec.id)])

    def _compute_ipc_count(self):
        for rec in self:
            rec.ipc_count = self.env['construction.ipc'].search_count(
                [('project_id', '=', rec.id)])

    def _compute_material_request_count(self):
        for rec in self:
            rec.material_request_count = self.env['construction.material.request'].search_count(
                [('project_id', '=', rec.id)])

    @api.depends('boq_ids', 'variation_ids', 'ipc_ids', 'cost_entry_ids')
    def _compute_financials(self):
        for rec in self:
            boqs = rec.boq_ids.filtered(lambda b: b.state == 'approved')
            rec.project_value = sum(boqs.mapped('total_amount'))
            executed_ipcs = rec.ipc_ids.filtered(lambda i: i.state in ('certified', 'approved', 'paid'))
            rec.executed_value = sum(executed_ipcs.mapped('total_approved_amount'))
            rec.remaining_value = rec.project_value - rec.executed_value
            cost_entries = rec.cost_entry_ids
            rec.budget_cost = sum(rec.budget_ids.filtered(lambda b: b.state == 'approved').mapped('total_amount'))
            rec.actual_cost = sum(cost_entries.mapped('amount'))
            rec.cost_variance = rec.budget_cost - rec.actual_cost

    @api.depends('executed_value', 'actual_cost')
    def _compute_evm(self):
        for rec in self:
            earned = rec.executed_value or 0.0
            actual = rec.actual_cost or 1.0
            planned = rec.budget_cost or 1.0
            rec.spi = earned / planned if planned else 0.0
            rec.cpi = earned / actual if actual else 0.0
            bac = rec.budget_cost or earned
            rec.eac = bac / rec.cpi if rec.cpi else 0.0
            rec.etc = rec.eac - actual
            rec.vac = bac - rec.eac

    @api.depends('timesheet_line_ids', 'timesheet_line_ids.unit_amount',
                 'timesheet_line_ids.amount')
    def _compute_timesheet_hours(self):
        for rec in self:
            lines = rec.timesheet_line_ids
            rec.total_hours_spent = sum(lines.mapped('unit_amount'))
            rec.total_timesheet_cost = sum(lines.mapped('amount'))

    def action_create_analytic_account(self):
        self.ensure_one()
        if self.analytic_account_id:
            raise UserError(_('Analytic account already exists for this project!'))
        default_plan_id = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'construction.default_analytic_plan_id', default='0') or 0)
        plan = self.env['account.analytic.plan'].browse(default_plan_id) if default_plan_id else \
            self.env['account.analytic.plan'].search([
                ('company_id', 'in', [self.company_id.id, False]),
            ], limit=1)
        analytic = self.env['account.analytic.account'].create({
            'name': f'[{self.code}] {self.name}',
            'code': self.code,
            'plan_id': plan.id if plan else False,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'active': True,
        })
        self.analytic_account_id = analytic.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Analytic Account'),
            'res_model': 'account.analytic.account',
            'view_mode': 'form',
            'res_id': analytic.id,
        }

    def action_create_project_project(self):
        self.ensure_one()
        if self.project_project_id:
            raise UserError(_('Odoo project already exists for this construction project!'))
        if not self.analytic_account_id:
            self.action_create_analytic_account()
        project = self.env['project.project'].create({
            'name': f'[{self.code}] {self.name}',
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'analytic_account_id': self.analytic_account_id.id,
            'allow_timesheets': True,
            'allow_billable': True,
            'construction_project_id': self.id,
            'active': True,
        })
        self.project_project_id = project.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Odoo Project'),
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': project.id,
        }

    def action_create_tasks_from_boq(self):
        self.ensure_one()
        if not self.project_project_id:
            raise UserError(_('Please create an Odoo project first!'))
        boq_items = self.env['construction.boq.item'].search([
            ('project_id', '=', self.id),
            ('parent_id', '=', False),
        ])
        if not boq_items:
            raise UserError(_('No BOQ items found for this project!'))
        Task = self.env['project.task']
        count = 0
        for item in boq_items:
            existing = Task.search([
                ('boq_item_id', '=', item.id),
                ('project_id', '=', self.project_project_id.id),
            ], limit=1)
            if existing:
                continue
            Task.create({
                'name': f'[{item.code}] {item.name}',
                'project_id': self.project_project_id.id,
                'boq_item_id': item.id,
                'planned_hours': item.quantity or 0.0,
                'user_ids': [(4, self.user_id.id)] if self.user_id else [],
                'company_id': self.company_id.id,
                'description': item.description or item.name,
            })
            count += 1
        if count:
            self.project_project_id.message_post(
                body=_('Created %s tasks from BOQ items') % count)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Tasks'),
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.project_project_id.id)],
        }

    def action_open_boq(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bill of Quantities'),
            'res_model': 'construction.boq',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_variations(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Variation Orders'),
            'res_model': 'construction.variation',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_progress(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Progress Records'),
            'res_model': 'construction.progress',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_open_ipc(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Interim Payment Certificates'),
            'res_model': 'construction.ipc',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                seq = self.env['ir.sequence'].next_by_code('construction.project')
                vals['code'] = seq or '/'
        records = super().create(vals_list)
        auto_analytic = self.env['ir.config_parameter'].sudo().get_param(
            'construction.auto_create_analytic', default='True') == 'True'
        if auto_analytic:
            for rec in records:
                if not rec.analytic_account_id:
                    try:
                        self.env.cr.execute(
                            'SAVEPOINT construction_auto_analytic')
                        rec.action_create_analytic_account()
                    except Exception:
                        self.env.cr.execute(
                            'ROLLBACK TO SAVEPOINT construction_auto_analytic')
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get('project_stage') in ('execution', 'awarded'):
            auto_project = self.env['ir.config_parameter'].sudo().get_param(
                'construction.auto_create_project',
                default='True') == 'True'
            if auto_project:
                for rec in self:
                    if not rec.project_project_id and rec.analytic_account_id:
                        try:
                            rec.action_create_project_project()
                        except Exception:
                            pass
        return result

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]

    @api.model
    def _demo_create_full_scenario(self):
        from datetime import date
        from odoo import Command
        company = self.env.company
        admin = self.env.ref('base.user_admin', False) or self.env.user
        partner = self.env.ref('saudi_construction_demo_data.partner_qiddiya', False) or \
                  self.env['res.partner'].search([], limit=1)
        uom_ton = self.env.ref('uom.product_uom_ton')
        uom_m3 = self.env.ref('uom.product_uom_cubic_meter')
        uom_m2 = self.env.ref('uom.product_uom_square_meter')
        uom_unit = self.env.ref('uom.product_uom_unit')
        uom_hour = self.env.ref('uom.product_uom_hour')

        # 1. CRM Lead
        crm_team = self.env['crm.team'].search([], limit=1)
        lead = self.env['crm.lead'].create({
            'name': u'مشروع إنشاء مجمع سكني - SBC 2026',
            'partner_id': partner.id,
            'expected_revenue': 18500000.0,
            'street': u'حي المغرزات، طريق الملك فهد',
            'city': u'الرياض',
            'team_id': crm_team.id,
            'user_id': admin.id,
            'description': u'مشروع إنشاء 6 فلل سكنية بمساحة إجمالية 3000 م²',
        })
        lead.action_create_construction_project()
        project = lead.construction_project_id
        project.write({
            'project_stage': 'execution', 'contract_amount': 18500000.0,
            'start_date': date(2026, 2, 1), 'end_date': date(2027, 6, 30),
            'contract_type': 'unit_price',
        })

        # 2. Resources
        self.env['construction.resource'].create([
            {'name': u'اسمنت بورتلاندي', 'code': 'CEM-002', 'resource_type': 'material',
             'uom_id': uom_ton.id, 'unit_cost': 440.0},
            {'name': u'حديد تسليح 16مم', 'code': 'STL-002', 'resource_type': 'material',
             'uom_id': uom_ton.id, 'unit_cost': 2900.0},
            {'name': u'خرسانة جاهزة 300 كجم/م3', 'code': 'CONC-002', 'resource_type': 'material',
             'uom_id': uom_m3.id, 'unit_cost': 380.0},
            {'name': u'بلوك خرساني مجوف 20سم', 'code': 'BLK-001', 'resource_type': 'material',
             'uom_id': uom_unit.id, 'unit_cost': 3.50},
            {'name': u'عامل بناء ماهر', 'code': 'LAB-003', 'resource_type': 'labor',
             'uom_id': uom_hour.id, 'unit_cost': 28.0, 'productivity_rate': 8},
            {'name': u'خلاطة خرسانة', 'code': 'EQP-003', 'resource_type': 'equipment',
             'uom_id': uom_hour.id, 'unit_cost': 200.0, 'operator_required': True, 'operator_cost': 25.0},
        ])

        # 3. BOQ
        boq = self.env['construction.boq'].create({
            'name': u'مقايسة المشروع الرئيسية', 'code': 'BOQ-2026-001',
            'project_id': project.id, 'state': 'draft', 'date': date(2026, 2, 1), 'version': '1.0',
        })
        sections = self.env['construction.boq.section'].create([
            {'boq_id': boq.id, 'name': u'أعمال الخرسانة', 'code': 'C', 'sequence': 10},
            {'boq_id': boq.id, 'name': u'أعمال البناء', 'code': 'M', 'sequence': 20},
            {'boq_id': boq.id, 'name': u'أعمال التشطيب', 'code': 'F', 'sequence': 30},
        ])
        items_data = [
            (sections[0], 'C.01', u'حفر وردم للأساسات', uom_m3, 1200, 55),
            (sections[0], 'C.02', u'خرسانة عادية نظافة 150 كجم/م3', uom_m3, 200, 320),
            (sections[0], 'C.03', u'خرسانة مسلحة للأساسات 300 كجم/م3', uom_m3, 900, 520),
            (sections[0], 'C.04', u'خرسانة مسلحة للأعمدة والجسور 350 كجم/م3', uom_m3, 650, 580),
            (sections[0], 'C.05', u'خرسانة مسلحة للأسقف 350 كجم/م3', uom_m3, 550, 590),
            (sections[0], 'C.06', u'حديد تسليح عالي المقاومة', uom_ton, 280, 3200),
            (sections[1], 'M.01', u'بلوك خرساني مجوف 20 سم للحوائط الخارجية', uom_m2, 3200, 95),
            (sections[1], 'M.02', u'بلوك خرساني مجوف 15 سم للحوائط الداخلية', uom_m2, 2500, 75),
            (sections[2], 'F.01', u'محارة حوائط داخلية', uom_m2, 6500, 35),
            (sections[2], 'F.02', u'محارة حوائط خارجية', uom_m2, 3200, 42),
            (sections[2], 'F.03', u'دهان حوائط داخلية (بوية لاتكس)', uom_m2, 6500, 30),
            (sections[2], 'F.04', u'دهان حوائط خارجية (بوية أكريليك)', uom_m2, 3200, 45),
            (sections[2], 'F.05', u'سيراميك أرضيات درجة أولى 60×60', uom_m2, 2800, 110),
            (sections[2], 'F.06', u'سيراميك جدران درجة أولى', uom_m2, 1800, 125),
            (sections[2], 'F.07', u'أبواب خشب سويدي داخلي', uom_unit, 120, 1800),
            (sections[2], 'F.08', u'نوافذ ألمنيوم بزجاج مزدوج', uom_m2, 480, 720),
            (sections[2], 'F.09', u'مطابخ ألمنيوم بالكامل', uom_unit, 6, 18000),
        ]
        items = self.env['construction.boq.item'].create([
            {'boq_id': boq.id, 'section_id': s.id, 'code': c, 'name': n,
             'unit': u.id, 'quantity': q, 'rate': r}
            for s, c, n, u, q, r in items_data
        ])
        boq.action_approve()
        task_count = self.env['project.task'].search_count(
            [('project_id', '=', project.project_project_id.id)])

        # 4. Sale Order
        so_result = boq.action_create_sale_order()
        sale_order = self.env['sale.order'].browse(so_result['res_id'])
        sale_order.action_confirm()

        # 5. Budget + accounting bridge
        budget = self.env['construction.budget'].create({
            'name': u'الميزانية المعتمدة', 'project_id': project.id,
            'budget_type': 'original', 'state': 'approved',
            'date': date(2026, 2, 1), 'contingency_percent': 3.0, 'version': '1.0',
        })
        self.env['construction.budget.line'].create([
            {'budget_id': budget.id, 'name': u'موازنة تكاليف المواد', 'cost_code': 'MAT',
             'quantity': 1, 'unit_cost': 6500000},
            {'budget_id': budget.id, 'name': u'موازنة الأجور والعمالة', 'cost_code': 'LAB',
             'quantity': 1, 'unit_cost': 2800000},
            {'budget_id': budget.id, 'name': u'موازنة المعدات', 'cost_code': 'EQP',
             'quantity': 1, 'unit_cost': 1200000},
            {'budget_id': budget.id, 'name': u'موازنة مصاريف الموقع', 'cost_code': 'SIT',
             'quantity': 1, 'unit_cost': 950000},
            {'budget_id': budget.id, 'name': u'موازنة مقاولي الباطن', 'cost_code': 'SUB',
             'quantity': 1, 'unit_cost': 3500000},
        ])
        budget.action_create_crossovered_budget()

        # 6. MR -> PO
        resources = self.env['construction.resource'].search([('project_id', '=', project.id)])
        mr = self.env['construction.material.request'].create({
            'name': u'طلب شراء مواد المرحلة الأولى',
            'project_id': project.id, 'date': date(2026, 2, 5),
            'required_date': date(2026, 2, 20), 'state': 'approved',
        })
        steel_prod = self.env['product.product'].create({
            'name': u'حديد تسليح 16مم', 'detailed_type': 'product',
            'list_price': 3200, 'standard_price': 2900,
            'uom_id': uom_ton.id, 'uom_po_id': uom_ton.id,
        })
        conc_prod = self.env['product.product'].create({
            'name': u'خرسانة جاهزة 300 كجم/م3', 'detailed_type': 'product',
            'list_price': 520, 'standard_price': 380,
            'uom_id': uom_m3.id, 'uom_po_id': uom_m3.id,
        })
        self.env['construction.material.request.line'].create([
            {'request_id': mr.id, 'boq_item_id': items[5].id,
             'resource_id': resources[1].id, 'product_id': steel_prod.id,
             'quantity': 100.0, 'unit_cost': 2900},
            {'request_id': mr.id, 'boq_item_id': items[3].id,
             'resource_id': resources[2].id, 'product_id': conc_prod.id,
             'quantity': 500.0, 'unit_cost': 380},
        ])
        po_res = mr.action_create_purchase_order()
        po = self.env['purchase.order'].browse(po_res['res_id'])
        po.button_confirm()

        # 7. Progress
        progress = self.env['construction.progress'].create({
            'name': u'حصر الأعمال - أبريل 2026',
            'project_id': project.id, 'date': date(2026, 4, 30),
            'period': 'monthly', 'state': 'approved',
            'manpower_on_site': 35, 'equipment_on_site': 6,
        })
        self.env['construction.progress.line'].create([
            {'progress_id': progress.id, 'boq_item_id': items[0].id,
             'total_quantity': 1200, 'previous_quantity': 0, 'current_quantity': 900, 'unit_rate': 55},
            {'progress_id': progress.id, 'boq_item_id': items[2].id,
             'total_quantity': 900, 'previous_quantity': 0, 'current_quantity': 500, 'unit_rate': 520},
            {'progress_id': progress.id, 'boq_item_id': items[3].id,
             'total_quantity': 650, 'previous_quantity': 0, 'current_quantity': 200, 'unit_rate': 580},
            {'progress_id': progress.id, 'boq_item_id': items[5].id,
             'total_quantity': 280, 'previous_quantity': 0, 'current_quantity': 120, 'unit_rate': 3200},
            {'progress_id': progress.id, 'boq_item_id': items[6].id,
             'total_quantity': 3200, 'previous_quantity': 0, 'current_quantity': 800, 'unit_rate': 95},
        ])

        # 8. Variation
        self.env['construction.variation'].create({
            'name': 'VO-2026-001', 'project_id': project.id,
            'date': date(2026, 3, 15), 'state': 'approved',
            'description': u'تغيير نوع الخرسانة للأساسات بناءً على طلب الاستشاري',
            'variation_type': 'consultant', 'reason': u'متطلبات سلامة إنشائية', 'priority': 'high',
            'variation_line_ids': [Command.create({
                'boq_item_id': items[2].id, 'change_type': 'rate',
                'original_quantity': 900, 'revised_quantity': 900,
                'original_rate': 520, 'revised_rate': 580,
            })],
        })

        # 9. IPC + Invoice
        ipc = self.env['construction.ipc'].create({
            'project_id': project.id, 'name': 'IPC-001',
            'date': date(2026, 5, 5), 'period_from': date(2026, 2, 1),
            'period_to': date(2026, 4, 30),
            'ipc_number': 1, 'state': 'certified', 'retention_percent': 5.0,
        })
        self.env['construction.ipc.line'].create([
            {'ipc_id': ipc.id, 'boq_item_id': items[0].id,
             'previous_quantity': 0, 'current_quantity': 900, 'rate': 55},
            {'ipc_id': ipc.id, 'boq_item_id': items[2].id,
             'previous_quantity': 0, 'current_quantity': 500, 'rate': 580},
            {'ipc_id': ipc.id, 'boq_item_id': items[3].id,
             'previous_quantity': 0, 'current_quantity': 200, 'rate': 580},
            {'ipc_id': ipc.id, 'boq_item_id': items[5].id,
             'previous_quantity': 0, 'current_quantity': 120, 'rate': 3200},
            {'ipc_id': ipc.id, 'boq_item_id': items[6].id,
             'previous_quantity': 0, 'current_quantity': 800, 'rate': 95},
        ])
        inv_res = ipc.action_create_invoice()
        invoice = self.env['account.move'].browse(inv_res['res_id'])
        if invoice.state == 'draft':
            invoice.action_post()

        # 10. Cost Entries + Cost Control
        self.env['construction.cost.entry'].create([
            {'project_id': project.id, 'boq_item_id': items[5].id,
             'resource_id': resources[1].id, 'name': u'فاتورة حديد تسليح',
             'amount': 290000, 'date': date(2026, 2, 20)},
            {'project_id': project.id, 'boq_item_id': items[2].id,
             'resource_id': resources[2].id, 'name': u'فاتورة خرسانة جاهزة',
             'amount': 190000, 'date': date(2026, 3, 5)},
            {'project_id': project.id, 'boq_item_id': items[0].id,
             'resource_id': resources[5].id, 'name': u'تكلفة حفر وردم',
             'amount': 49500, 'date': date(2026, 3, 1)},
            {'project_id': project.id, 'boq_item_id': items[6].id,
             'resource_id': resources[3].id, 'name': u'فاتورة بلوك',
             'amount': 2800, 'date': date(2026, 4, 10)},
        ])
        try:
            self.env['construction.cost.control'].cron_update_costs()
        except Exception:
            pass

        # 11. Forecast + Cashflow
        self.env['construction.forecast'].create([
            {'project_id': project.id, 'date': date(2026, 6, 30),
             'forecast_type': 'cost', 'period': 'monthly',
             'planned_amount': 4200000, 'forecast_amount': 4400000, 'actual_amount': 532300},
            {'project_id': project.id, 'date': date(2026, 12, 31),
             'forecast_type': 'cost', 'period': 'monthly',
             'planned_amount': 6500000, 'forecast_amount': 6800000},
            {'project_id': project.id, 'date': date(2027, 3, 31),
             'forecast_type': 'cost', 'period': 'monthly',
             'planned_amount': 7500000, 'forecast_amount': 7800000},
        ])
        self.env['construction.cashflow'].create([
            {'project_id': project.id, 'date': date(2026, 5, 15),
             'flow_type': 'income', 'category': 'client_payment',
             'forecast_amount': 625000, 'ipc_id': ipc.id},
            {'project_id': project.id, 'date': date(2026, 5, 15),
             'flow_type': 'expense', 'category': 'material',
             'forecast_amount': 450000, 'actual_amount': 482300},
            {'project_id': project.id, 'date': date(2026, 6, 15),
             'flow_type': 'expense', 'category': 'labor', 'forecast_amount': 280000},
            {'project_id': project.id, 'date': date(2026, 8, 15),
             'flow_type': 'income', 'category': 'client_payment', 'forecast_amount': 1200000},
            {'project_id': project.id, 'date': date(2026, 8, 15),
             'flow_type': 'expense', 'category': 'subcontract', 'forecast_amount': 600000},
        ])

        # 12. Analytic Lines
        if project.analytic_account_id and project.project_project_id:
            employee = self.env['hr.employee'].search([('company_id', '=', company.id)], limit=1)
            if not employee:
                emp_partner = self.env['res.partner'].search([('company_type', '=', 'person')], limit=1)
                if not emp_partner:
                    emp_partner = admin.partner_id
                timesheet_journal = self.env['account.journal'].search(
                    [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
                employee = self.env['hr.employee'].create({
                    'name': u'مدير المشروع', 'user_id': admin.id,
                    'company_id': company.id, 'address_id': emp_partner.id,
                    'timesheet_cost': 100.0,
                    'journal_id': timesheet_journal.id if timesheet_journal else False,
                })
            self.env['account.analytic.line'].create([
                {'name': u'صرف حديد للموقع',
                 'project_id': project.project_project_id.id,
                 'account_id': project.analytic_account_id.id,
                 'unit_amount': 8, 'amount': -290000, 'employee_id': employee.id,
                 'construction_project_id': project.id,
                 'construction_boq_item_id': items[5].id, 'cost_type': 'material'},
                {'name': u'صب خرسانة أساسات',
                 'project_id': project.project_project_id.id,
                 'account_id': project.analytic_account_id.id,
                 'unit_amount': 40, 'amount': -190000, 'employee_id': employee.id,
                 'construction_project_id': project.id,
                 'construction_boq_item_id': items[2].id, 'cost_type': 'material'},
            ])

        # 13. Dashboard refresh
        self.env['construction.dashboard'].init()
