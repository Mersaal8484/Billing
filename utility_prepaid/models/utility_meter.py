from odoo import fields, models, _
from odoo.exceptions import UserError


class UtilityMeterModelPrepaid(models.Model):
    _inherit = 'utility.meter.model'

    supports_prepaid = fields.Boolean('يدعم الدفع المسبق (STS/Prepaid)')
    communication_capabilities = fields.Char('تقنيات الاتصال المدعومة بالموديل')


class UtilityMeterPrepaid(models.Model):
    _inherit = 'utility.meter'

    sts_key_revision = fields.Char('مراجعة مفتاح STS')
    communication_type = fields.Selection([
        ('gsm', 'جي إس إم (GSM)'),
        ('nbiot', 'إن بي آي أو تي (NB-IoT)'),
        ('lora', 'لورا (LoRa)'),
        ('rf', 'تردد لاسلكي (RF)'),
        ('plc', 'خط الطاقة (PLC)'),
        ('manual', 'يدوي'),
    ], string='نوع الاتصال الذكي')
    sim_number = fields.Char('رقم شريحة SIM')

    def action_request_ami_reading(self):
        """Request an AMI reading through the configured smart provider."""
        provider = self.env['utility.integration.provider'].sudo().search([
            ('provider_type', '=', 'ami'),
            ('active', '=', True),
        ], limit=1)
        if not provider:
            raise UserError(_('لا يوجد مزود AMI نشط.'))
        for meter in self:
            provider.call_json({
                'meter_number': meter.meter_number,
                'operational_number': meter.operational_number or '',
                'serial_number': meter.serial_number or '',
                'customer': meter.customer_id.customer_number if meter.customer_id else False,
            }, 'ami.reading.request', record=meter)
        return True

    def create_ami_reading(self, reading_value, reading_date=False, date_range_id=False):
        """Create a standard utility reading from an AMI event."""
        self.ensure_one()
        return self.env['utility.reading'].sudo().create({
            'meter_id': self.id,
            'account_id': self.customer_id.id if self.customer_id else False,
            'reading_value': reading_value,
            'reading_date': reading_date or fields.Datetime.now(),
            'date_range_id': date_range_id or False,
            'reading_type': 'ami',
            'reading_category': 'customer',
            'reading_source': 'ami_integration',
        })
