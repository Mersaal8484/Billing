import logging
import json
from datetime import datetime, timedelta
from typing import Optional

from odoo import fields
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class VendingEngine:
    """Core vending business logic for prepaid electricity sales.

    Orchestrates the full vending lifecycle: quote calculation, payment
    processing, STS token generation, and completion/failure handling.
    All methods accept Odoo environment/records as parameters and are
    company-aware.
    """

    def __init__(self, env):
        """Initialize with an Odoo environment.

        Args:
            env: Odoo environment (self.env from a model).
        """
        self.env = env

    def calculate_vending_quote(self, account, meter, amount, vending_date=None,
                                channel=None, agent=None):
        """Calculate a complete vending quote with all charge breakdowns.

        Args:
            account: utility.customer record.
            meter: utility.meter record.
            amount: gross amount the customer wants to pay.
            vending_date: optional datetime for tariff snapshot.
            channel: optional utility.vending.channel record.
            agent: optional res.users record for agent-based sales.

        Returns:
            dict with keys: gross_amount, energy_amount, service_charge,
            tax_amount, debt_recovery_amount, other_deduction_amount,
            net_vending_amount, kwh_purchased, charge_lines, tariff_snapshot.
        """
        if not account:
            raise UserError("Account is required for vending quote.")
        if not meter:
            raise UserError("Meter is required for vending quote.")
        if meter.customer_id != account:
            raise ValidationError(
                f"Meter {meter.meter_number} does not belong to account {account.customer_number}."
            )
        if not amount or amount <= 0:
            raise UserError("Vending amount must be greater than zero.")

        company = account.company_id
        vending_date = vending_date or fields.Datetime.now()

        policy = self.env['utility.vending.policy'].get_applicable_policy(
            account, meter, channel)
        if not policy:
            raise UserError("No applicable vending policy found for this account.")

        if amount < policy.minimum_vending_amount:
            raise UserError(
                f"Minimum vending amount is {policy.minimum_vending_amount}."
            )
        if policy.maximum_vending_amount and amount > policy.maximum_vending_amount:
            raise UserError(
                f"Maximum vending amount is {policy.maximum_vending_amount}."
            )

        service_charge = policy.service_charge_fixed
        if policy.service_charge_percentage:
            service_charge += amount * (policy.service_charge_percentage / 100.0)

        tax_amount = 0.0
        if policy.tax_percentage:
            tax_amount = (amount - service_charge) * (policy.tax_percentage / 100.0)

        debt_recovery_amount = self._apply_debt_recovery(
            account, amount, policy)

        other_deduction_amount = 0.0
        if agent and channel and channel.channel_type == 'agent':
            agent_commission = self._calculate_agent_commission(
                amount, agent, company)
            other_deduction_amount += agent_commission

        energy_amount = (
            amount - service_charge - tax_amount
            - debt_recovery_amount - other_deduction_amount
        )

        tariff = account.contract_template_id.price_per_kwh if account.contract_template_id else 0
        kwh_purchased = energy_amount / tariff if tariff else 0.0

        charge_lines = self._build_charge_lines(
            energy_amount, service_charge, tax_amount,
            debt_recovery_amount, other_deduction_amount, agent)

        tariff_snapshot = json.dumps({
            'policy_id': policy.id,
            'policy_name': policy.name,
            'tariff_per_kwh': tariff,
            'service_charge_fixed': policy.service_charge_fixed,
            'service_charge_pct': policy.service_charge_percentage,
            'tax_pct': policy.tax_percentage,
            'debt_recovery_enabled': policy.enable_debt_recovery,
            'computed_at': vending_date.isoformat(),
        })

        return {
            'gross_amount': amount,
            'energy_amount': energy_amount,
            'service_charge': service_charge,
            'tax_amount': tax_amount,
            'debt_recovery_amount': debt_recovery_amount,
            'other_deduction_amount': other_deduction_amount,
            'net_vending_amount': energy_amount - debt_recovery_amount - other_deduction_amount,
            'kwh_purchased': kwh_purchased,
            'charge_lines': charge_lines,
            'tariff_snapshot': tariff_snapshot,
        }

    def create_vending_request(self, quote, payment_data):
        """Create a utility.vending.request record from a calculated quote.

        Args:
            quote: dict returned by calculate_vending_quote().
            payment_data: dict with payment info (pos_order_id, shift_id,
                payment_method, operator_id, etc.).

        Returns:
            utility.vending.request record.
        """
        account = self.env['utility.customer'].browse(quote.get('account_id'))
        meter = self.env['utility.meter'].browse(quote.get('meter_id'))

        if not account.exists() or not meter.exists():
            raise UserError("Invalid account or meter for vending request.")

        vals = {
            'account_id': account.id,
            'meter_id': meter.id,
            'gross_amount': quote['gross_amount'],
            'energy_amount': quote['energy_amount'],
            'service_charge_amount': quote['service_charge'],
            'tax_amount': quote['tax_amount'],
            'debt_recovery_amount': quote['debt_recovery_amount'],
            'other_deduction_amount': quote['other_deduction_amount'],
            'kwh_purchased': quote['kwh_purchased'],
            'tariff_snapshot': quote['tariff_snapshot'],
            'state': 'draft',
            'vending_date': fields.Datetime.now(),
            'operator_id': payment_data.get('operator_id', self.env.user.id),
        }
        if payment_data.get('channel_id'):
            vals['channel_id'] = payment_data['channel_id']
        if payment_data.get('policy_id'):
            vals['policy_id'] = payment_data['policy_id']
        if payment_data.get('pos_order_id'):
            vals['pos_order_id'] = payment_data['pos_order_id']
        if payment_data.get('shift_id'):
            vals['shift_id'] = payment_data['shift_id']
        if payment_data.get('idempotency_key'):
            vals['idempotency_key'] = payment_data['idempotency_key']
        if payment_data.get('notes'):
            vals['notes'] = payment_data['notes']

        request = self.env['utility.vending.request'].create(vals)
        self._create_charge_lines(request, quote['charge_lines'])
        _logger.info(
            "Vending request %s created for account %s, amount %s",
            request.reference, account.customer_number, quote['gross_amount'],
        )
        return request

    def confirm_payment(self, request):
        """Process payment for a vending request and transition to paid state.

        Args:
            request: utility.vending.request record.

        Returns:
            request record after state transition.
        """
        request.ensure_one()
        if request.state not in ('draft', 'quoted', 'confirmed'):
            raise UserError(
                f"Cannot confirm payment for request in '{request.state}' state."
            )
        if request.gross_amount <= 0:
            raise UserError("Cannot confirm payment with zero amount.")

        request.write({
            'state': 'paid',
            'paid_date': fields.Datetime.now(),
        })
        _logger.info(
            "Payment confirmed for vending request %s", request.reference,
        )
        return request

    def submit_to_sts(self, request):
        """Submit a paid vending request to the STS provider for token generation.

        Args:
            request: utility.vending.request record (must be in 'paid' state).

        Returns:
            utility.sts.transaction record created for the request.
        """
        request.ensure_one()
        if request.state != 'paid':
            raise UserError(
                "Request must be in 'paid' state before submitting to STS."
            )

        provider = self._get_sts_provider(request.company_id)
        if not provider:
            raise UserError("No active STS provider configured for this company.")

        request.write({'state': 'token_pending'})

        sts_tx_vals = {
            'vending_request_id': request.id,
            'provider_id': provider.id,
            'meter_id': request.meter_id.id,
            'account_id': request.account_id.id,
            'amount': request.energy_amount,
            'kwh': request.kwh_purchased,
            'state': 'pending',
        }
        if request.idempotency_key:
            sts_tx_vals['idempotency_key'] = request.idempotency_key

        sts_tx = self.env['utility.sts.transaction'].create(sts_tx_vals)
        sts_tx.action_send_request()

        if sts_tx.state == 'success' and sts_tx.token_value:
            self._create_token_record(request, sts_tx)
            request.write({'state': 'token_generated'})
        else:
            request.write({
                'state': 'token_failed',
                'last_error': sts_tx.error_message or 'Token generation failed',
            })

        _logger.info(
            "STS submission for request %s: state=%s, tx=%s",
            request.reference, request.state, sts_tx.reference,
        )
        return sts_tx

    def complete_vending(self, request, provider_result=None):
        """Finalize a vending request after successful token generation.

        Creates accounting entries and marks as completed.

        Args:
            request: utility.vending.request record.
            provider_result: optional dict from STS provider response.

        Returns:
            request record in 'completed' state.
        """
        request.ensure_one()
        if request.state not in ('token_generated', 'paid'):
            raise UserError(
                f"Cannot complete request in '{request.state}' state."
            )

        if provider_result and provider_result.get('success'):
            if not request.token_ids.filtered(lambda t: t.status == 'success'):
                self._create_token_from_result(request, provider_result)

        request.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now(),
        })
        self._post_accounting_entries(request)

        _logger.info(
            "Vending request %s completed", request.reference,
        )
        return request

    def fail_vending(self, request, error):
        """Mark a vending request as failed with an error message.

        Args:
            request: utility.vending.request record.
            error: str or Exception describing the failure.
        """
        request.ensure_one()
        error_msg = str(error) if error else 'Unknown error'

        request.write({
            'state': 'token_failed',
            'last_error': error_msg,
        })
        _logger.warning(
            "Vending request %s failed: %s", request.reference, error_msg,
        )

    def _apply_debt_recovery(self, account, amount, policy):
        """Calculate debt recovery deduction based on policy and account balance.

        Args:
            account: utility.customer record.
            amount: gross vending amount before deductions.
            policy: utility.vending.policy record.

        Returns:
            float: debt recovery amount to deduct.
        """
        if not policy.enable_debt_recovery:
            return 0.0

        debt = account.accounting_balance or 0.0
        if debt <= 0:
            return 0.0

        max_debt = amount * (policy.max_debt_recovery_percentage / 100.0)
        min_energy = amount * (policy.min_energy_after_recovery / 100.0)

        debt_recovery = min(max_debt, debt)

        service_charge = policy.service_charge_fixed
        if policy.service_charge_percentage:
            service_charge += amount * (policy.service_charge_percentage / 100.0)

        tax_amount = 0.0
        if policy.tax_percentage:
            tax_amount = (amount - service_charge) * (policy.tax_percentage / 100.0)

        net_after_debt = amount - service_charge - tax_amount - debt_recovery
        if net_after_debt < min_energy:
            debt_recovery = max(0, amount - service_charge - tax_amount - min_energy)

        return min(debt_recovery, debt)

    def _calculate_tariff(self, amount, tariff, contract_template):
        """Breakdown vending amount based on tariff rules from contract template.

        Args:
            amount: gross amount to calculate.
            tariff: tariff rate per kWh or tariff record.
            contract_template: utility.contract.template record.

        Returns:
            dict with kwh, service_charge, tax, breakdown details.
        """
        if not contract_template:
            return {'kwh': 0, 'service_charge': 0, 'tax': 0}

        price_per_kwh = tariff or contract_template.price_per_kwh
        kwh = amount / price_per_kwh if price_per_kwh else 0

        service_charge = contract_template.service_charge or 0.0
        tax_amount = 0.0
        if contract_template.tax_percentage:
            tax_amount = (amount - service_charge) * (contract_template.tax_percentage / 100.0)

        return {
            'kwh': kwh,
            'price_per_kwh': price_per_kwh,
            'service_charge': service_charge,
            'tax': tax_amount,
            'net_energy': amount - service_charge - tax_amount,
        }

    def _calculate_agent_commission(self, amount, agent, company):
        """Calculate agent commission based on company settings.

        Args:
            amount: gross vending amount.
            agent: res.users record.
            company: res.company record.

        Returns:
            float: commission amount.
        """
        commission_pct = getattr(company, 'agent_commission_pct', 0)
        if not commission_pct:
            return 0.0
        return amount * (commission_pct / 100.0)

    def _build_charge_lines(self, energy, service, tax, debt, other, agent=None):
        """Build charge line dicts for the vending quote.

        Args:
            energy: energy amount value.
            service: service charge value.
            tax: tax amount value.
            debt: debt recovery amount value.
            other: other deduction amount value.
            agent: optional agent record for commission line.

        Returns:
            list of dict charge line data.
        """
        lines = []
        seq = 10
        if energy:
            lines.append({
                'charge_type': 'energy',
                'description': 'Energy Value',
                'amount': energy,
                'sequence': seq,
            })
            seq += 10
        if service:
            lines.append({
                'charge_type': 'service',
                'description': 'Service Charge',
                'amount': service,
                'sequence': seq,
            })
            seq += 10
        if tax:
            lines.append({
                'charge_type': 'tax',
                'description': 'Tax',
                'amount': tax,
                'sequence': seq,
            })
            seq += 10
        if debt:
            lines.append({
                'charge_type': 'debt_recovery',
                'description': 'Debt Recovery',
                'amount': debt,
                'sequence': seq,
            })
            seq += 10
        if other:
            lines.append({
                'charge_type': 'other',
                'description': 'Other Deductions',
                'amount': other,
                'sequence': seq,
            })
        return lines

    def _create_charge_lines(self, request, charge_lines):
        """Create utility.vending.charge.line records for a vending request.

        Args:
            request: utility.vending.request record.
            charge_lines: list of charge line dicts.
        """
        if not charge_lines:
            return
        line_data = []
        for cl in charge_lines:
            line_data.append({
                'vending_request_id': request.id,
                'charge_type': cl.get('charge_type', 'energy'),
                'description': cl.get('description', ''),
                'amount': cl.get('amount', 0.0),
                'sequence': cl.get('sequence', 0),
            })
        self.env['utility.vending.charge.line'].create(line_data)

    def _get_sts_provider(self, company):
        """Get the active STS provider for a company.

        Args:
            company: res.company record.

        Returns:
            utility.sts.provider record or None.
        """
        provider = company.default_sts_provider_id
        if not provider:
            provider = self.env['utility.sts.provider'].search([
                ('active', '=', True),
                ('company_id', '=', company.id),
            ], limit=1)
        return provider

    def _create_token_record(self, request, sts_tx):
        """Create a utility.token record from a successful STS transaction.

        Args:
            request: utility.vending.request record.
            sts_tx: utility.sts.transaction record with success state.
        """
        token_vals = {
            'vending_request_id': request.id,
            'account_id': request.account_id.id,
            'meter_id': request.meter_id.id,
            'customer_id': request.partner_id.id,
            'token_number': sts_tx.token_value,
            'token_identifier': sts_tx.token_identifier,
            'amount': request.energy_amount,
            'kwh': request.kwh_purchased,
            'status': 'success',
            'response_date': fields.Datetime.now(),
            'response_code': '00',
            'response_message': 'Token generated successfully',
            'sts_server': sts_tx.provider_id.name,
            'provider_reference': sts_tx.provider_reference,
        }
        self.env['utility.token'].create(token_vals)

    def _create_token_from_result(self, request, provider_result):
        """Create token directly from provider result dict.

        Args:
            request: utility.vending.request record.
            provider_result: dict with token_value, token_identifier, etc.
        """
        token_vals = {
            'vending_request_id': request.id,
            'account_id': request.account_id.id,
            'meter_id': request.meter_id.id,
            'customer_id': request.partner_id.id,
            'token_number': provider_result.get('token_value'),
            'token_identifier': provider_result.get('token_identifier'),
            'amount': request.energy_amount,
            'kwh': request.kwh_purchased,
            'status': 'success',
            'response_date': fields.Datetime.now(),
            'response_code': provider_result.get('response_code', '00'),
            'response_message': provider_result.get('response_message', 'Success'),
            'provider_reference': provider_result.get('provider_reference'),
        }
        self.env['utility.token'].create(token_vals)

    def _post_accounting_entries(self, request):
        """Create accounting journal entries for a completed vending request.

        Args:
            request: utility.vending.request record in 'completed' state.
        """
        if not request.company_id.prepaid_revenue_policy:
            return
        try:
            service = self.env['utility.prepaid.accounting.service']
            service.create_vending_entry(request)
        except Exception:
            _logger.exception(
                "Failed to create accounting entry for vending request %s",
                request.reference,
            )
