from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityTransformerReading(models.Model):
    _name = 'utility.transformer.reading'
    _description = 'Transformer / Cell Reading'
    _inherit = ['mail.thread']
    _order = 'reading_date desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    name = fields.Char('رقم القراءة', default=lambda self: _('New'), readonly=True)

    transformer_id = fields.Many2one(
        'utility.transformer', 'المحول', required=True, index=True)
    meter_id = fields.Many2one(
        'utility.meter', 'العداد', required=True, index=True,
        domain="[('transformer_id', '=', transformer_id)]")
    customer_id = fields.Many2one(
        'utility.customer', 'المشترك',
        help='مشترك الخلية (فقط لقراءات الخلايا)')

    reading_type = fields.Selection([
        ('coupling', 'عداد ربط'),
        ('cell', 'خلية / مشترك'),
    ], string='نوع القراءة', default='coupling', required=True)

    reading_date = fields.Datetime('تاريخ القراءة', default=fields.Datetime.now, required=True)
    reading_value = fields.Float('قيمة القراءة', required=True)
    consumption = fields.Float('الاستهلاك', compute='_compute_consumption', store=True)
    previous_reading = fields.Float('القراءة السابقة')
    previous_reading_date = fields.Datetime('تاريخ القراءة السابقة')

    date_range_id = fields.Many2one('date.range', 'الفترة', index=True)

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('confirmed', 'مؤكدة'),
        ('cancelled', 'ملغاة'),
    ], string='الحالة', default='draft', tracking=True)

    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('unique_meter_reading_date',
         'unique(meter_id, reading_date)',
         'يوجد قراءة لنفس العداد في نفس التاريخ!'),
    ]

    @api.depends('reading_value', 'previous_reading')
    def _compute_consumption(self):
        for r in self:
            r.consumption = r.reading_value - r.previous_reading if r.previous_reading else 0.0

    @api.depends('meter_id', 'reading_date')
    def _compute_previous_reading(self):
        for r in self:
            prev = self.search([
                ('meter_id', '=', r.meter_id.id),
                ('reading_date', '<', r.reading_date),
                ('state', '=', 'confirmed'),
                ('id', '!=', r.id),
            ], order='reading_date desc', limit=1)
            r.previous_reading = prev.reading_value if prev else 0.0
            r.previous_reading_date = prev.reading_date if prev else False

    def action_confirm(self):
        for r in self:
            if r.state != 'draft':
                raise ValidationError(_('يمكن تأكيد القراءات المسودة فقط!'))
            r.state = 'confirmed'

    def action_cancel(self):
        for r in self:
            if r.state == 'cancelled':
                raise ValidationError(_('القراءة ملغاة بالفعل!'))
            r.state = 'cancelled'

    def action_draft(self):
        for r in self:
            r.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.transformer.reading') or _('New')
        return super().create(vals_list)
