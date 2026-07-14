import logging
from collections import defaultdict
from datetime import timedelta

from odoo import fields

_logger = logging.getLogger(__name__)


class ReconciliationEngine:
    """Reconciles prepaid vending transactions across POS, STS, and accounting.

    Detects duplicates, matches POS sessions with vending requests,
    and generates reconciliation reports.
    """

    def __init__(self, env):
        """Initialize with an Odoo environment.

        Args:
            env: Odoo environment.
        """
        self.env = env

    def reconcile_pos_with_vending(self, pos_session):
        """Match POS orders in a session with their corresponding vending requests.

        Args:
            pos_session: pos.session record.

        Returns:
            dict with matched, unmatched, and error counts.
        """
        pos_session.ensure_one()

        pos_orders = self.env['pos.order'].search([
            ('session_id', '=', pos_session.id),
            ('state', '=', 'paid'),
        ])

        matched = 0
        unmatched = 0
        errors = 0

        for order in pos_orders:
            if order.vending_request_id:
                matched += 1
                continue

            vending_request = self.env['utility.vending.request'].search([
                ('pos_order_id', '=', order.id),
            ], limit=1)

            if vending_request:
                order.vending_request_id = vending_request.id
                if vending_request.state == 'draft':
                    vending_request.action_confirm()
                matched += 1
            else:
                unmatched += 1
                _logger.warning(
                    "POS order %s has no matching vending request",
                    order.name,
                )

        result = {
            'total_orders': len(pos_orders),
            'matched': matched,
            'unmatched': unmatched,
            'errors': errors,
        }
        _logger.info(
            "POS session %s reconciliation: %s", pos_session.name, result,
        )
        return result

    def reconcile_sts_transactions(self, provider, date_from, date_to):
        """Match STS transactions with provider records.

        Queries the provider for transactions in the date range and
        compares with local records to find mismatches.

        Args:
            provider: utility.sts.provider record.
            date_from: date start of range.
            date_to: date end of range.

        Returns:
            dict with matched, mismatched, missing_local, missing_remote counts.
        """
        local_txs = self.env['utility.sts.transaction'].search([
            ('provider_id', '=', provider.id),
            ('request_date', '>=', date_from),
            ('request_date', '<=', date_to),
        ])

        matched = 0
        mismatched = 0
        missing_remote = 0

        for tx in local_txs:
            if not tx.provider_reference:
                missing_remote += 1
                continue

            try:
                result = provider.send_query_transaction(tx.provider_reference)
                if result.get('success'):
                    if tx.state == 'success' and result.get('state') == 'success':
                        matched += 1
                    elif tx.state != result.get('state'):
                        mismatched += 1
                        _logger.warning(
                            "State mismatch for STS tx %s: local=%s, remote=%s",
                            tx.reference, tx.state, result.get('state'),
                        )
                    else:
                        matched += 1
                else:
                    missing_remote += 1
            except Exception:
                missing_remote += 1
                _logger.exception(
                    "Failed to query provider for STS tx %s", tx.reference,
                )

        result = {
            'total_local': len(local_txs),
            'matched': matched,
            'mismatched': mismatched,
            'missing_remote': missing_remote,
        }
        _logger.info(
            "STS reconciliation for provider %s: %s", provider.name, result,
        )
        return result

    def detect_duplicates(self, date_from, date_to):
        """Find potential duplicate vending transactions in a date range.

        Identifies transactions with the same account, meter, similar
        amount, and close timestamps.

        Args:
            date_from: date start of range.
            date_to: date end of range.

        Returns:
            list of dict with duplicate group details.
        """
        requests = self.env['utility.vending.request'].search([
            ('vending_date', '>=', date_from),
            ('vending_date', '<=', date_to),
            ('state', 'not in', ('cancelled',)),
        ], order='account_id, meter_id, vending_date')

        groups = defaultdict(list)
        for req in requests:
            key = (req.account_id.id, req.meter_id.id, round(req.gross_amount, 2))
            groups[key].append(req)

        duplicates = []
        for key, reqs in groups.items():
            if len(reqs) < 2:
                continue

            dup_group = []
            sorted_reqs = sorted(reqs, key=lambda r: r.vending_date or r.create_date)

            for i in range(len(sorted_reqs)):
                for j in range(i + 1, len(sorted_reqs)):
                    r1 = sorted_reqs[i]
                    r2 = sorted_reqs[j]
                    time_diff = abs(
                        (r2.vending_date or r2.create_date)
                        - (r1.vending_date or r1.create_date)
                    ).total_seconds()

                    if time_diff <= 120:
                        dup_group.append({
                            'request_1': r1.reference,
                            'request_2': r2.reference,
                            'account': r1.account_id.customer_number,
                            'meter': r1.meter_id.meter_number,
                            'amount': r1.gross_amount,
                            'time_diff_seconds': time_diff,
                        })

            if dup_group:
                duplicates.append({
                    'group_key': key,
                    'duplicates': dup_group,
                    'count': len(dup_group),
                })

        if duplicates:
            _logger.warning(
                "Detected %d potential duplicate groups in date range %s to %s",
                len(duplicates), date_from, date_to,
            )
        return duplicates

    def generate_reconciliation_report(self, session_or_date_range):
        """Generate a summary reconciliation report.

        Args:
            session_or_date_range: pos.session record or dict with
                date_from and date_to keys.

        Returns:
            dict with comprehensive reconciliation summary.
        """
        if isinstance(session_or_date_range, dict):
            date_from = session_or_date_range['date_from']
            date_to = session_or_date_range['date_to']
            company = session_or_date_range.get(
                'company_id', self.env.company,
            )

            vending_requests = self.env['utility.vending.request'].search([
                ('vending_date', '>=', date_from),
                ('vending_date', '<=', date_to),
                ('company_id', '=', company.id),
            ])
        else:
            session = session_or_date_range
            session.ensure_one()
            date_from = session.start_at
            date_to = session.stop_at or fields.Datetime.now()
            company = session.company_id

            vending_requests = self.env['utility.vending.request'].search([
                ('pos_session_id', '=', session.id),
            ])

        completed = vending_requests.filtered(lambda r: r.state == 'completed')
        pending = vending_requests.filtered(lambda r: r.state in ('token_pending', 'token_failed'))
        cancelled = vending_requests.filtered(lambda r: r.state == 'cancelled')

        total_amount = sum(vending_requests.mapped('gross_amount'))
        completed_amount = sum(completed.mapped('gross_amount'))

        tokens = self.env['utility.token'].search([
            ('vending_request_id', 'in', vending_requests.ids),
            ('status', '=', 'success'),
        ])

        report = {
            'company': company.name,
            'date_from': str(date_from),
            'date_to': str(date_to),
            'total_requests': len(vending_requests),
            'completed': len(completed),
            'pending': len(pending),
            'cancelled': len(cancelled),
            'total_amount': total_amount,
            'completed_amount': completed_amount,
            'tokens_generated': len(tokens),
            'reconciliation_rate': (
                len(completed) / len(vending_requests) * 100
                if vending_requests else 0
            ),
        }
        _logger.info("Reconciliation report generated: %s", report)
        return report
