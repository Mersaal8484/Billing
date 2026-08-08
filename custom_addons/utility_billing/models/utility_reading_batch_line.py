from odoo import fields, models


class UtilityReadingBatchLine(models.Model):
    _name = 'utility.reading.batch.line'
    _description = 'Reading Batch Detail Line'
    _order = 'seq asc, id asc'

    batch_id = fields.Many2one(
        'utility.reading.batch',
        string='Batch',
        required=True,
        ondelete='cascade',
        index=True,
    )
    seq = fields.Integer('Sequence', default=1)
    meter_number = fields.Char('Meter Number', required=True, index=True)
    reading_value = fields.Float('Reading Value', required=True)
    reading_date = fields.Datetime('Reading Date', default=fields.Datetime.now)
    reading_category = fields.Selection([
        ('customer', 'Customer'),
        ('transformer', 'Transformer'),
        ('feeder', 'Feeder'),
        ('cell', 'Cell'),
    ], string='Reading Category', default='customer')
    reading_purpose = fields.Selection([
        ('opening', 'Opening'),
        ('periodic', 'Periodic'),
        ('closing', 'Closing'),
        ('replacement_closing', 'Replacement Closing'),
    ], string='Reading Purpose', default='periodic', required=True)
    reading_type = fields.Selection([
        ('manual', 'Manual'),
        ('estimated', 'Estimated'),
        ('ami', 'AMI'),
    ], string='Reading Type', default='manual', required=True)
    reading_event = fields.Selection([
        ('normal', 'Normal'),
        ('installation', 'Installation'),
        ('replacement', 'Replacement'),
        ('disconnection', 'Disconnection'),
        ('removal', 'Removal'),
        ('contract_closure', 'Contract Closure'),
    ], string='Reading Event', default='normal', required=True)
    is_estimated = fields.Boolean('Estimated Reading', default=False)
    client_reading_uuid = fields.Char('Mobile Client Reading UUID', index=True, copy=False)
    asset_uuid = fields.Char('Media Asset UUID', index=True, copy=False)
    image_filename = fields.Char('Image Filename')
    raw_payload_json = fields.Text('Original NDJSON Line')
    reading_id = fields.Many2one('utility.reading', string='Created Reading', ondelete='set null')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string='Line State', default='pending', required=True, index=True)

    error_message = fields.Text('Error Message')

    _sql_constraints = [
        ('unique_batch_client_reading_uuid',
         'unique(batch_id, client_reading_uuid)',
         'Mobile client reading UUID must be unique inside the same batch.'),
    ]
