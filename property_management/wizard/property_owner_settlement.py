from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PropertyOwnerSettlementWizard(models.TransientModel):
    _name = 'property.owner.settlement.wizard'
    _description = 'Owner Settlement Wizard'

    owner_id = fields.Many2one('property.owner', string='Owner', required=True)
    company_id = fields.Many2one('res.company', related='owner_id.company_id')
    currency_id = fields.Many2one('res.currency', related='owner_id.currency_id')

    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True, default=fields.Date.today)

    total_rent_collected = fields.Monetary(string='Total Rent Collected', compute='_compute_settlement_amounts', store=True)
    management_fee_percentage = fields.Float(string='Management Fee %', related='owner_id.management_fee_percentage', readonly=False)
    management_fee_amount = fields.Monetary(string='Management Fee Amount', compute='_compute_settlement_amounts', store=True)
    total_maintenance_cost = fields.Monetary(string='Maintenance Expenses', compute='_compute_settlement_amounts', store=True)
    net_payable = fields.Monetary(string='Net Payable to Owner', compute='_compute_settlement_amounts', store=True)

    journal_id = fields.Many2one('account.journal', string='Settlement Journal', domain="[('type', 'in', ('bank', 'cash', 'general'))]")
    settlement_move_id = fields.Many2one('account.move', string='Settlement Entry')
    notes = fields.Text(string='Notes')

    @api.depends('owner_id', 'start_date', 'end_date', 'management_fee_percentage')
    def _compute_settlement_amounts(self):
        for rec in self:
            if not rec.owner_id or not rec.start_date or not rec.end_date:
                rec.total_rent_collected = 0.0
                rec.management_fee_amount = 0.0
                rec.total_maintenance_cost = 0.0
                rec.net_payable = 0.0
                continue

            payments = self.env['property.payment'].search([
                ('state', '=', 'paid'),
                ('payment_type', '=', 'rent'),
                ('date', '>=', rec.start_date),
                ('date', '<=', rec.end_date),
                '|',
                ('unit_id.owner_id', '=', rec.owner_id.id),
                ('property_id.owner_id', '=', rec.owner_id.id),
            ])
            rent_total = sum(payments.mapped('company_amount')) or sum(payments.mapped('amount'))
            rec.total_rent_collected = rent_total
            rec.management_fee_amount = rent_total * (rec.management_fee_percentage / 100.0)

            maintenance = self.env['property.maintenance'].search([
                ('state', '=', 'done'),
                ('date_completed', '>=', rec.start_date),
                ('date_completed', '<=', rec.end_date),
                '|',
                ('unit_id.owner_id', '=', rec.owner_id.id),
                ('property_id.owner_id', '=', rec.owner_id.id),
            ])
            maintenance_total = sum(maintenance.mapped('total_cost'))
            rec.total_maintenance_cost = maintenance_total

            rec.net_payable = rec.total_rent_collected - rec.management_fee_amount - rec.total_maintenance_cost

    def action_confirm_settlement(self):
        self.ensure_one()
        if self.net_payable <= 0:
            raise UserError(_("Net payable amount is zero or negative. Nothing to settle."))

        journal = self.journal_id
        if not journal:
            journal = self.env['account.journal'].search([('company_id', '=', self.company_id.id), ('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_("Please configure a settlement journal."))

        partner = self.owner_id.partner_id
        if not partner:
            raise UserError(_("Please configure a contact partner for the owner."))

        payable_account = partner.property_account_payable_id or self.env['account.account'].search([('account_type', '=', 'liability_payable'), ('company_id', '=', self.company_id.id)], limit=1)
        receivable_account = self.company_id.property_receivable_account_id or self.env['account.account'].search([('account_type', '=', 'asset_receivable'), ('company_id', '=', self.company_id.id)], limit=1)
        fee_income_account = self.company_id.property_service_income_account_id or self.env['account.account'].search([('account_type', '=', 'income'), ('company_id', '=', self.company_id.id)], limit=1)

        line_ids = [
            (0, 0, {
                'name': f'Owner Settlement: {self.start_date} to {self.end_date}',
                'partner_id': partner.id,
                'account_id': payable_account.id,
                'debit': 0.0,
                'credit': self.net_payable,
            }),
            (0, 0, {
                'name': f'Rent Collected: {self.start_date} to {self.end_date}',
                'partner_id': partner.id,
                'account_id': receivable_account.id,
                'debit': self.total_rent_collected,
                'credit': 0.0,
            }),
        ]

        if self.management_fee_amount > 0:
            line_ids.append((0, 0, {
                'name': f'Management Fee ({self.management_fee_percentage}%)',
                'partner_id': partner.id,
                'account_id': fee_income_account.id,
                'debit': 0.0,
                'credit': self.management_fee_amount,
            }))

        if self.total_maintenance_cost > 0:
            expense_account = self.company_id.property_maintenance_expense_account_id or self.env['account.account'].search([('account_type', '=', 'expense'), ('company_id', '=', self.company_id.id)], limit=1)
            line_ids.append((0, 0, {
                'name': f'Maintenance Deductions: {self.start_date} to {self.end_date}',
                'partner_id': partner.id,
                'account_id': expense_account.id,
                'debit': 0.0,
                'credit': self.total_maintenance_cost,
            }))

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.today(),
            'ref': f'Settlement - {self.owner_id.name}',
            'journal_id': journal.id,
            'line_ids': line_ids,
        })
        move.action_post()
        self.settlement_move_id = move.id
        self.owner_id.last_settlement_date = self.end_date

        return {
            'type': 'ir.actions.act_window',
            'name': _('Settlement Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }
