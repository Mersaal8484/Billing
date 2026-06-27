from datetime import date, timedelta
from odoo import api, fields, models, _


class UtilityBillingCycle(models.Model):
    _name = 'utility.billing.cycle'
    _description = 'Utility Billing Cycle'
    _order = 'cycle_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('Cycle Name', required=True)
    code = fields.Char('Cycle Code')
    cycle_date = fields.Date('Cycle Date', default=lambda self: date.today().replace(day=1))
    billing_period_start = fields.Date('Billing Period Start')
    billing_period_end = fields.Date('Billing Period End')
    due_date = fields.Date('Due Date')
    cutoff_date = fields.Date('Cutoff Date')
    frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('bi_monthly', 'Bi-Monthly'),
        ('quarterly', 'Quarterly'),
    ], string='Frequency', default='monthly')
    region_id = fields.Many2one('utility.region', 'Region', domain="[('type', '=', 'region')]")
    area_id = fields.Many2one('utility.region', 'Area', domain="[('type', '=', 'area')]")
    meter_ids = fields.Many2many('utility.meter', 'utility_billing_cycle_meter_rel', 'cycle_id', 'meter_id', string='Meters')
    bill_ids = fields.One2many('utility.bill', 'billing_cycle_id', string='Bills')
    total_bills = fields.Integer('Total Bills', compute='_compute_totals', store=True)
    total_amount = fields.Float('Total Amount', compute='_compute_totals', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string='State', default='draft')

    @api.depends('bill_ids', 'bill_ids.amount_total')
    def _compute_totals(self):
        for r in self:
            bills = r.bill_ids
            r.total_bills = len(bills)
            r.total_amount = sum(bills.mapped('amount_total'))

    def action_generate_bills(self):
        """توليد الفواتير من القراءات المعتمدة فقط (approved)"""
        self.ensure_one()
        Reading = self.env['utility.reading']
        meters = self.meter_ids
        if not meters:
            meters = self.env['utility.meter'].search([('company_id', '=', self.company_id.id)])
        for meter in meters:
            account = meter.account_id
            if not account:
                continue
            
            # البحث عن آخر قراءة معتمدة غير مفوترة
            last_reading = Reading.search([
                ('meter_id', '=', meter.id),
                ('state', '=', 'approved'),
            ], order='reading_date desc', limit=1)
            
            if not last_reading:
                continue
                
            # البحث عن القراءة السابقة المعتمدة أو المفوترة
            prev_reading = Reading.search([
                ('meter_id', '=', meter.id),
                ('state', 'in', ['approved', 'billed']),
                ('reading_date', '<', last_reading.reading_date),
            ], order='reading_date desc', limit=1)
            
            prev_value = prev_reading.reading_value if prev_reading else 0.0
            consumption = last_reading.reading_value - prev_value
            if consumption < 0:
                consumption = 0.0
                
            bill_vals = {
                'customer_id': account.customer_id.id,
                'account_id': account.id,
                'meter_id': meter.id,
                'billing_cycle_id': self.id,
                'bill_date': fields.Date.today(),
                'period_start': prev_reading.reading_date.date() if prev_reading else self.billing_period_start,
                'period_end': last_reading.reading_date.date() if last_reading.reading_date else self.billing_period_end,
                'due_date': self.due_date or (fields.Date.today() + timedelta(days=30)),
                'previous_reading': prev_value,
                'current_reading': last_reading.reading_value,
                'consumption': consumption,
                'tariff_id': account.tariff_id.id if account.tariff_id else False,
                'reading_id': last_reading.id,
                'state': 'draft',
            }
            bill = self.env['utility.bill'].create(bill_vals)
            
            # حساب المبالغ
            bill._calculate_amounts()
            
            # تحويل حالة القراءة إلى مفوترة
            last_reading.state = 'billed'
            
        self.state = 'closed'
        return True

    @api.model
    def action_generate_bills_daily(self):
        cycles = self.search([('state', '=', 'open')])
        for cycle in cycles:
            cycle.action_generate_bills()
        return True
