import logging
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UtilityVendingPolicy(models.Model):
    _name = 'utility.vending.policy'
    _description = 'سياسة بيع الكهرباء مسبقة الدفع'
    _order = 'sequence, name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم السياسة', required=True)
    sequence = fields.Integer('التسلسل', default=10)

    policy_type = fields.Selection([
        ('standard', 'قياسية'),
        ('promotional', 'ترويجية'),
        ('emergency', 'طارئة'),
    ], 'نوع السياسة', default='standard', required=True)

    scope = fields.Selection([
        ('all', 'جميع العملاء'),
        ('category', 'حسب الفئة'),
        ('subscriber', 'حسب النوع'),
        ('region', 'حسب المنطقة التجارية'),
        ('route', 'حسب المسار'),
        ('transformer', 'حسب المحول'),
        ('contract', 'حسب العقد'),
    ], 'النطاق', default='all', required=True)

    category_ids = fields.Many2many('utility.subscriber.category', 'utility_vending_policy_category_rel', string='فئات المشتركين')
    subscriber_ids = fields.Many2many('utility.subscriber', 'utility_vending_policy_subscriber_rel', string='أنواع المشتركين')
    # التسلسل التجاري
    region_ids = fields.Many2many('utility.region', string='المناطق التجارية',
        domain="[('type', 'in', ('region', 'area', 'zone'))]")
    route_ids = fields.Many2many('utility.route', string='المسارات')
    # تسلسل التوزيع
    substation_ids = fields.Many2many('utility.substation', string='المحطات الفرعية')
    transformer_ids = fields.Many2many('utility.transformer', string='المحولات')
    contract_template_ids = fields.Many2many('utility.contract.template', 'utility_vending_policy_contract_rel', string='قوالب العقود')

    minimum_vending_amount = fields.Monetary('أقل مبلغ شحن', currency_field='currency_id', default=0.0)
    maximum_vending_amount = fields.Monetary('أقصى مبلغ شحن', currency_field='currency_id', default=0.0)

    service_charge_fixed = fields.Monetary('رسوم خدمة ثابتة', currency_field='currency_id', default=0.0)
    service_charge_percentage = fields.Float('نسبة رسوم الخدمة (%)', default=0.0)

    tax_percentage = fields.Float('نسبة الضريبة (%)', default=0.0)

    enable_debt_recovery = fields.Boolean('تفعيل استقطاع الديون', default=True)
    max_debt_recovery_percentage = fields.Float('أقصى نسبة استقطاع (%)', default=100.0)
    min_energy_after_recovery = fields.Float('أقل نسبة طاقة بعد الاستقطاع (%)', default=10.0)

    description = fields.Text('الوصف')
    date_from = fields.Date('ساري من')
    date_to = fields.Date('ساري حتى')

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)

    @api.model
    def get_applicable_policy(self, account, meter, channel=None):
        domain = [
            ('active', '=', True),
            ('company_id', '=', account.company_id.id),
        ]
        if account.contract_template_id:
            policies = self.search(domain + [('scope', '=', 'contract'),
                                              ('contract_template_ids', 'in', account.contract_template_id.id)])
            if policies:
                return policies[0]
        if account.route_id:
            policies = self.search(domain + [('scope', '=', 'route'),
                                              ('route_ids', 'in', account.route_id.id)])
            if policies:
                return policies[0]
        if meter and getattr(meter, 'transformer_id', False):
            policies = self.search(domain + [('scope', '=', 'transformer'),
                                              ('transformer_ids', 'in', meter.transformer_id.id)])
            if policies:
                return policies[0]
        if account.subscriber_id:
            policies = self.search(domain + [('scope', '=', 'subscriber'),
                                              ('subscriber_ids', 'in', account.subscriber_id.id)])
            if policies:
                return policies[0]
        if account.category_id:
            policies = self.search(domain + [('scope', '=', 'category'),
                                              ('category_ids', 'in', account.category_id.id)])
            if policies:
                return policies[0]
        if account.region_id:
            policies = self.search(domain + [('scope', '=', 'region'),
                                              ('region_ids', 'in', account.region_id.id)])
            if policies:
                return policies[0]
        default_policies = self.search(domain + [('scope', '=', 'all')], order='sequence, id', limit=1)
        return default_policies[0] if default_policies else self.env['utility.vending.policy']

    @api.model
    def calculate_quote(self, account, meter, gross_amount, vending_date=None, channel=None):
        policy = self.get_applicable_policy(account, meter, channel)
        if not policy:
            raise UserError(_('لا توجد سياسة بيع سارية لهذا الحساب.'))

        if gross_amount < policy.minimum_vending_amount:
            raise UserError(
                _('أقل مبلغ شحن هو %s.')
                % (policy.minimum_vending_amount)
            )
        if policy.maximum_vending_amount and gross_amount > policy.maximum_vending_amount:
            raise UserError(
                _('أقصى مبلغ شحن هو %s.')
                % (policy.maximum_vending_amount)
            )

        service_charge = policy.service_charge_fixed
        if policy.service_charge_percentage:
            service_charge += gross_amount * (policy.service_charge_percentage / 100.0)

        tax_amount = 0.0
        if policy.tax_percentage:
            tax_amount = (gross_amount - service_charge) * (policy.tax_percentage / 100.0)

        debt_recovery_amount = 0.0
        if policy.enable_debt_recovery and account.accounting_balance > 0:
            max_debt = gross_amount * (policy.max_debt_recovery_percentage / 100.0)
            min_energy = gross_amount * (policy.min_energy_after_recovery / 100.0)
            debt_recovery_amount = min(max_debt, account.accounting_balance)
            net_after_debt = gross_amount - service_charge - tax_amount - debt_recovery_amount
            if net_after_debt < min_energy:
                debt_recovery_amount = max(0, gross_amount - service_charge - tax_amount - min_energy)

        energy_amount = gross_amount - service_charge - tax_amount - debt_recovery_amount

        tariff = account.contract_template_id.price_per_kwh if account.contract_template_id else 0
        kwh = energy_amount / tariff if tariff else 0

        charge_lines = []
        if energy_amount:
            charge_lines.append({
                'charge_type': 'energy',
                'description': _('قيمة الطاقة'),
                'amount': energy_amount,
                'sequence': 10,
            })
        if service_charge:
            charge_lines.append({
                'charge_type': 'service',
                'description': _('رسوم الخدمة'),
                'amount': service_charge,
                'sequence': 20,
            })
        if tax_amount:
            charge_lines.append({
                'charge_type': 'tax',
                'description': _('الضريبة'),
                'amount': tax_amount,
                'sequence': 30,
            })
        if debt_recovery_amount:
            charge_lines.append({
                'charge_type': 'debt_recovery',
                'description': _('استقطاع الديون'),
                'amount': debt_recovery_amount,
                'sequence': 40,
            })

        tariff_snapshot = json.dumps({
            'policy_id': policy.id,
            'policy_name': policy.name,
            'tariff_per_kwh': tariff,
            'service_charge_fixed': policy.service_charge_fixed,
            'service_charge_pct': policy.service_charge_percentage,
            'tax_pct': policy.tax_percentage,
            'debt_recovery_enabled': policy.enable_debt_recovery,
            'computed_at': vending_date and vending_date.isoformat() or fields.Datetime.now().isoformat(),
        })

        return {
            'energy_amount': energy_amount,
            'service_charge': service_charge,
            'tax_amount': tax_amount,
            'debt_recovery_amount': debt_recovery_amount,
            'other_deduction_amount': 0.0,
            'kwh_purchased': kwh,
            'charge_lines': charge_lines,
            'tariff_snapshot': tariff_snapshot,
        }

    @api.model
    def calculate_quote_by_ids(self, account_id, meter_id, gross_amount):
        """RPC-compatible wrapper for POS frontend.

        Accepts integer IDs instead of record objects.
        """
        account = self.env['utility.customer'].browse(account_id)
        meter = self.env['utility.meter'].browse(meter_id)
        if not account.exists():
            raise UserError(_('الحساب غير موجود.'))
        if not meter.exists():
            raise UserError(_('العداد غير موجود.'))
        return self.calculate_quote(account, meter, gross_amount)

    @api.model
    def get_pos_config(self):
        """Return POS-specific vending configuration."""
        company = self.env.company
        policy = self.search([
            ('active', '=', True),
            ('company_id', '=', company.id),
            ('scope', '=', 'all'),
        ], order='sequence, id', limit=1)
        return {
            'minimum_vending_amount': policy.minimum_vending_amount if policy else 1.0,
            'maximum_vending_amount': policy.maximum_vending_amount if policy else 100000.0,
            'service_charge_fixed': policy.service_charge_fixed if policy else 0.0,
            'service_charge_percentage': policy.service_charge_percentage if policy else 0.0,
            'tax_percentage': policy.tax_percentage if policy else 0.0,
            'enable_debt_recovery': policy.enable_debt_recovery if policy else False,
        }
