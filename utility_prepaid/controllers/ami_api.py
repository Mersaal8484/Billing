import hmac

from odoo import http
from odoo.http import request


class UtilityPrepaidAMIController(http.Controller):
    """AMI transport adapter; readings remain standard utility.reading records."""

    def _resolve_meter(self, params):
        Meter = request.env['utility.meter'].sudo()
        identifiers = []
        if params.get('meter_id') not in (None, '', False):
            try:
                meter = Meter.search([('id', '=', int(params['meter_id']))], limit=1)
            except (TypeError, ValueError):
                meter = Meter.browse()
            identifiers.append(meter)
        for key in ('operational_number', 'meter_number'):
            value = params.get(key)
            if value not in (None, '', False):
                identifiers.append(Meter.search([(key, '=', str(value).strip())], limit=1))
        if not identifiers:
            return Meter.browse(), 'IDENTIFIER_REQUIRED'
        if any(not meter for meter in identifiers):
            return Meter.browse(), 'METER_NOT_FOUND'
        if len({meter.id for meter in identifiers}) > 1:
            return Meter.browse(), 'METER_IDENTIFIER_MISMATCH'
        return identifiers[0], False

    @http.route('/api/v1/utility/ami/reading_callback', type='json', auth='public', methods=['POST'], csrf=False)
    def ami_reading_callback(self, **kwargs):
        params = request.jsonrequest or {}
        secret = params.get('secret') or params.get('webhook_secret')
        if not secret:
            return {'error': 'webhook secret is required', 'code': 'VALIDATION_ERROR'}
        providers = request.env['utility.integration.provider'].sudo().search([
            ('provider_type', '=', 'ami'),
            ('active', '=', True),
        ])
        provider = next((item for item in providers if item.webhook_secret and hmac.compare_digest(
            item.webhook_secret.encode('utf-8'), secret.encode('utf-8'))), False)
        if not provider:
            return {'error': 'Invalid AMI provider secret', 'code': 'INVALID_WEBHOOK_SIGNATURE'}
        if params.get('reading_value') is None:
            return {'error': 'reading_value is required', 'code': 'VALIDATION_ERROR'}
        meter, identifier_error = self._resolve_meter(params)
        if identifier_error == 'IDENTIFIER_REQUIRED':
            return {'error': 'meter_id, operational_number or meter_number is required', 'code': 'VALIDATION_ERROR'}
        if identifier_error == 'METER_IDENTIFIER_MISMATCH':
            return {'error': 'المعرفات الممررة للعداد متعارضة', 'code': identifier_error}
        if not meter:
            return {'error': 'Meter not found', 'code': identifier_error or 'METER_NOT_FOUND'}
        if meter.company_id != provider.company_id:
            return {'error': 'Meter is not available for this AMI provider company', 'code': 'ACCESS_DENIED'}
        try:
            reading_value = float(params['reading_value'])
        except (TypeError, ValueError):
            return {'error': 'reading_value must be numeric', 'code': 'VALIDATION_ERROR'}
        date_range_id = params.get('date_range_id') or False
        if date_range_id:
            try:
                date_range_id = int(date_range_id)
            except (TypeError, ValueError):
                return {'error': 'date_range_id must be numeric', 'code': 'VALIDATION_ERROR'}
            period = request.env['date.range'].sudo().browse(date_range_id).exists()
            if (not period or period.company_id not in (False, provider.company_id)
                    or period.period_role != 'reading' or period.state != 'open'):
                return {'error': 'Invalid reading period for this AMI provider company', 'code': 'INVALID_READING_PERIOD'}
        reading = meter.create_ami_reading(
            reading_value,
            reading_date=params.get('reading_date') or False,
            date_range_id=date_range_id,
        )
        provider.call_json({
            'meter_number': meter.meter_number,
            'operational_number': meter.operational_number or '',
            'serial_number': meter.serial_number or '',
            'meter_id': meter.id,
            'reading_id': reading.reading_id,
            'reading_value': reading_value,
        }, 'ami.reading.callback', record=reading)
        return {'success': True, 'reading_id': reading.id, 'reading_number': reading.reading_id}
