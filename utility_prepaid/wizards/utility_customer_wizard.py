from odoo import fields, models


class UtilityCustomerPrepaidWizard(models.TransientModel):
    _inherit = 'utility.customer.wizard'

    sts_key_revision = fields.Char(string='مراجعة مفتاح STS')
    communication_type = fields.Selection([
        ('gsm', 'جي إس إم (GSM)'),
        ('nbiot', 'إن بي آي أو تي (NB-IoT)'),
        ('lora', 'لورا (LoRa)'),
        ('rf', 'تردد لاسلكي (RF)'),
        ('plc', 'خط الطاقة (PLC)'),
        ('manual', 'يدوي'),
    ], string='نوع الاتصال الذكي')

    def action_create(self):
        result = super().action_create()
        if self.create_meter and result.get('res_id'):
            customer = self.env['utility.customer'].browse(result['res_id'])
            if customer.meter_id:
                customer.meter_id.write({
                    'sts_key_revision': self.sts_key_revision if self.payment_type == 'prepaid' else False,
                    'communication_type': self.communication_type if self.payment_type == 'postpaid' else False,
                })
        return result
