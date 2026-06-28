from odoo import api, fields, models, _


class PropertyProperty(models.Model):
    _name = 'property.property'
    _description = 'Real Estate Property'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id desc'
    _rec_name = 'display_name'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    name = fields.Char(string='Property Name', required=True, tracking=True, translate=True)
    code = fields.Char(string='Property Code', required=True, tracking=True, index=True)
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    arabic_name = fields.Char(string='Arabic Name')

    property_type = fields.Many2one('property.property.type', string='Property Type', required=True)
    status = fields.Many2one('property.property.status', string='Status', required=True,
                             default=lambda self: self.env.ref('property_management.property_status_active', raise_if_not_found=False))
    status_code = fields.Char(related='status.code', store=True)

    owner_id = fields.Many2one('property.owner', string='Owner', tracking=True)
    manager_id = fields.Many2one('res.users', string='Property Manager', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client/Owner Contact')
    rent_journal_id = fields.Many2one('account.journal', string='Rent Journal')
    deposit_journal_id = fields.Many2one('account.journal', string='Deposit Journal')
    maintenance_journal_id = fields.Many2one('account.journal', string='Maintenance Journal')
    cash_journal_id = fields.Many2one('account.journal', string='Cash Journal', domain="[('type', '=', 'cash')]")
    bank_journal_id = fields.Many2one('account.journal', string='Bank Journal', domain="[('type', '=', 'bank')]")
    receivable_account_id = fields.Many2one('account.account', string='Receivable Account')
    rent_income_account_id = fields.Many2one('account.account', string='Rent Income Account')
    service_income_account_id = fields.Many2one('account.account', string='Service Income Account')
    deposit_liability_account_id = fields.Many2one('account.account', string='Deposit Liability Account')
    advance_liability_account_id = fields.Many2one('account.account', string='Advance Liability Account')
    maintenance_expense_account_id = fields.Many2one('account.account', string='Maintenance Expense Account')
    cash_account_id = fields.Many2one('account.account', string='Cash/Clearing Account')

    address = fields.Char(string='Address')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='Zip Code')
    country_id = fields.Many2one('res.country', string='Country')
    latitude = fields.Float(string='Latitude', digits=(9, 6))
    longitude = fields.Float(string='Longitude', digits=(9, 6))
    google_map_link = fields.Char(string='Google Maps Link', compute='_compute_google_map')

    description = fields.Text(string='Description', translate=True)
    image = fields.Binary(string='Image', attachment=True)
    image_small = fields.Binary(string='Small Image', attachment=True)

    purchase_date = fields.Date(string='Purchase Date', tracking=True)
    purchase_price = fields.Monetary(string='Purchase Price', currency_field='currency_id', tracking=True)
    current_value = fields.Monetary(string='Current Market Value', currency_field='currency_id', tracking=True)
    construction_date = fields.Date(string='Construction Date')

    total_area = fields.Float(string='Total Area (sqm)', digits=(10, 2))
    total_buildings = fields.Integer(string='Buildings', compute='_compute_building_unit_counts', store=True)
    total_units = fields.Integer(string='Units', compute='_compute_building_unit_counts', store=True)
    occupied_units = fields.Integer(string='Occupied', compute='_compute_occupancy', store=True)
    vacant_units = fields.Integer(string='Vacant', compute='_compute_occupancy', store=True)
    occupancy_rate = fields.Float(string='Occupancy %', compute='_compute_occupancy', store=True, digits=(5, 2))

    building_ids = fields.One2many('property.building', 'property_id', string='Buildings')
    unit_ids = fields.One2many('property.unit', 'property_id', string='Units')
    lease_ids = fields.One2many('property.lease', 'property_id', string='Leases')
    document_ids = fields.One2many('property.document', 'property_id', string='Documents')

    lease_count = fields.Integer(string='Leases', compute='_compute_lease_count')
    maintenance_count = fields.Integer(string='Maintenance Requests', compute='_compute_maintenance_count')

    annual_rent_income = fields.Monetary(string='Annual Rent Income', compute='_compute_financials', store=True)
    total_maintenance_cost = fields.Monetary(string='Total Maintenance Cost', compute='_compute_financials', store=True)
    net_operating_income = fields.Monetary(string='Net Operating Income', compute='_compute_financials', store=True)
    property_value = fields.Monetary(string='Property Value', compute='_compute_financials', store=True)

    note = fields.Text(string='Notes')
    internal_note = fields.Text(string='Internal Notes')

    _sql_constraints = [
        ('code_company_unique', 'UNIQUE(code, company_id)', 'Property code must be unique per company!'),
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.code}] {rec.name}'

    @api.depends('latitude', 'longitude')
    def _compute_google_map(self):
        for rec in self:
            if rec.latitude and rec.longitude:
                rec.google_map_link = f'https://www.google.com/maps?q={rec.latitude},{rec.longitude}'
            else:
                rec.google_map_link = False

    @api.depends('building_ids', 'unit_ids')
    def _compute_building_unit_counts(self):
        for rec in self:
            rec.total_buildings = len(rec.building_ids)
            rec.total_units = len(rec.unit_ids)

    @api.depends('unit_ids.status')
    def _compute_occupancy(self):
        for rec in self:
            rec.occupied_units = len(rec.unit_ids.filtered(lambda u: u.status and u.status.code == 'OCCUPIED'))
            rec.vacant_units = rec.total_units - rec.occupied_units
            rec.occupancy_rate = (rec.occupied_units / rec.total_units * 100) if rec.total_units else 0.0

    def _compute_lease_count(self):
        data = self.env['property.lease'].read_group(
            [('property_id', 'in', self.ids), ('state', '!=', 'cancelled')],
            ['property_id'], ['property_id'])
        mapped = {d['property_id'][0]: d['property_id_count'] for d in data if d.get('property_id')}
        for rec in self:
            rec.lease_count = mapped.get(rec.id, 0)

    def _compute_maintenance_count(self):
        data = self.env['property.maintenance'].read_group(
            [('property_id', 'in', self.ids)],
            ['property_id'], ['property_id'])
        mapped = {d['property_id'][0]: d['property_id_count'] for d in data if d.get('property_id')}
        for rec in self:
            rec.maintenance_count = mapped.get(rec.id, 0)

    @api.depends('lease_ids', 'unit_ids', 'current_value', 'purchase_price')
    def _compute_financials(self):
        for rec in self:
            active_leases = rec.lease_ids.filtered(lambda l: l.state == 'active')
            rec.annual_rent_income = sum(active_leases.mapped('annual_rent'))
            maintenance = self.env['property.maintenance'].search([('property_id', '=', rec.id)])
            rec.total_maintenance_cost = sum(maintenance.mapped('total_cost'))
            rec.net_operating_income = rec.annual_rent_income - rec.total_maintenance_cost
            rec.property_value = rec.current_value or rec.purchase_price or 0.0

    def action_open_units(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Units'),
            'res_model': 'property.unit',
            'view_mode': 'tree,form',
            'domain': [('property_id', '=', self.id)],
            'context': {'default_property_id': self.id},
        }

    def action_open_leases(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Leases'),
            'res_model': 'property.lease',
            'view_mode': 'tree,form',
            'domain': [('property_id', '=', self.id)],
            'context': {'default_property_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                seq = self.env['ir.sequence'].next_by_code('property.property')
                vals['code'] = seq or '/'
        return super().create(vals_list)

    def name_get(self):
        return [(rec.id, f'[{rec.code}] {rec.name}') for rec in self]

    def _get_journal_for_method(self, method):
        self.ensure_one()
        if method == 'rent':
            return self.rent_journal_id or self.company_id.property_rent_journal_id
        elif method == 'deposit':
            return self.deposit_journal_id or self.company_id.property_deposit_journal_id
        elif method == 'maintenance':
            return self.maintenance_journal_id or self.company_id.property_maintenance_journal_id
        elif method == 'cash':
            return self.cash_journal_id or self.company_id.property_cash_journal_id or self.env['account.journal'].search([('company_id', '=', self.company_id.id), ('type', '=', 'cash')], limit=1)
        elif method in ('bank', 'bank_transfer', 'check', 'credit_card', 'online', 'other'):
            return self.bank_journal_id or self.company_id.property_bank_journal_id or self.env['account.journal'].search([('company_id', '=', self.company_id.id), ('type', '=', 'bank')], limit=1)
        return self.env['account.journal']

    def _get_receivable_account(self):
        self.ensure_one()
        return self.receivable_account_id or self.company_id.property_receivable_account_id

    def _get_deposit_liability_account(self):
        self.ensure_one()
        return self.deposit_liability_account_id or self.company_id.property_deposit_liability_account_id

    def _get_advance_liability_account(self):
        self.ensure_one()
        return self.advance_liability_account_id or self.company_id.property_advance_liability_account_id

    def _get_service_income_account(self):
        self.ensure_one()
        return self.service_income_account_id or self.company_id.property_service_income_account_id

    def _get_rent_income_account(self):
        self.ensure_one()
        return self.rent_income_account_id or self.company_id.property_rent_income_account_id

    def _get_cash_account(self):
        self.ensure_one()
        return self.cash_account_id or self.company_id.property_cash_account_id

    def action_create_custom_accounts(self):
        self.ensure_one()
        company = self.company_id or self.env.company

        def get_or_create_account(name, acc_type, base_code):
            acc = self.env['account.account'].search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
            if acc:
                return acc.id
            code = base_code
            step = 1
            while self.env['account.account'].search([('code', '=', code), ('company_id', '=', company.id)], limit=1):
                code = f"{base_code}{step:02d}"
                step += 1
            acc = self.env['account.account'].create({
                'name': name,
                'code': code,
                'account_type': acc_type,
                'company_id': company.id,
            })
            return acc.id

        def get_or_create_journal(name, journal_type, base_code):
            journal = self.env['account.journal'].search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
            if journal:
                return journal.id
            code = base_code[:5]
            step = 1
            while self.env['account.journal'].search([('code', '=', code), ('company_id', '=', company.id)], limit=1):
                suffix = str(step)
                code = f"{base_code[:5-len(suffix)]}{suffix}"
                step += 1
            journal = self.env['account.journal'].create({
                'name': name,
                'code': code,
                'type': journal_type,
                'company_id': company.id,
            })
            return journal.id

        prop_name = self.name[:30]
        receivable_id = get_or_create_account(f"Receivable - {prop_name}", 'asset_receivable', f"121{self.id}")
        rent_income_id = get_or_create_account(f"Rent Income - {prop_name}", 'income', f"411{self.id}")
        service_income_id = get_or_create_account(f"Service Income - {prop_name}", 'income', f"412{self.id}")
        deposit_liability_id = get_or_create_account(f"Deposit Liability - {prop_name}", 'liability_current', f"221{self.id}")
        advance_liability_id = get_or_create_account(f"Advance Liability - {prop_name}", 'liability_current', f"222{self.id}")
        maintenance_expense_id = get_or_create_account(f"Maintenance Expense - {prop_name}", 'expense', f"511{self.id}")
        cash_account_id = get_or_create_account(f"Clearing Account - {prop_name}", 'asset_current', f"111{self.id}")

        p_code = (self.code or 'PRP')[:3].upper()
        rent_journal_id = get_or_create_journal(f"Rent - {prop_name}", 'sale', f"R{p_code}")
        deposit_journal_id = get_or_create_journal(f"Deposit - {prop_name}", 'general', f"D{p_code}")
        maintenance_journal_id = get_or_create_journal(f"Maintenance - {prop_name}", 'purchase', f"M{p_code}")
        cash_journal_id = get_or_create_journal(f"Cash - {prop_name}", 'cash', f"C{p_code}")
        bank_journal_id = get_or_create_journal(f"Bank - {prop_name}", 'bank', f"B{p_code}")

        self.write({
            'receivable_account_id': receivable_id,
            'rent_income_account_id': rent_income_id,
            'service_income_account_id': service_income_id,
            'deposit_liability_account_id': deposit_liability_id,
            'advance_liability_account_id': advance_liability_id,
            'maintenance_expense_account_id': maintenance_expense_id,
            'cash_account_id': cash_account_id,
            'rent_journal_id': rent_journal_id,
            'deposit_journal_id': deposit_journal_id,
            'maintenance_journal_id': maintenance_journal_id,
            'cash_journal_id': cash_journal_id,
            'bank_journal_id': bank_journal_id,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }



class PropertyPropertyType(models.Model):
    _name = 'property.property.type'
    _description = 'Property Type'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)


class PropertyPropertyStatus(models.Model):
    _name = 'property.property.status'
    _description = 'Property Status'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
