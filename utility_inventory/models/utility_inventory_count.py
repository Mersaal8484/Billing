from odoo import api, fields, models, _


class UtilityInventoryCount(models.Model):
    _name = 'utility.inventory.count'
    _description = 'جرد مخزون'
    _rec_name = 'name'
    _order = 'date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('رقم الجرد', required=True, index=True, default=lambda self: _('New'))
    date = fields.Date('تاريخ الجرد', default=fields.Date.today, required=True)
    location_id = fields.Many2one('utility.inventory.location', 'موقع الجرد', required=True, ondelete='restrict')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('in_progress', 'قيد التنفيذ'),
        ('done', 'تم'),
        ('cancelled', 'ملغي'),
    ], string='الحالة', default='draft')
    line_ids = fields.One2many('utility.inventory.count.line', 'count_id', 'بنود الجرد')
    user_id = fields.Many2one('res.users', 'المستخدم', default=lambda self: self.env.user)
    notes = fields.Text('ملاحظات')

    def action_start(self):
        self.state = 'in_progress'

    def action_done(self):
        for count in self:
            for line in count.line_ids:
                if line.counted_quantity != line.expected_quantity:
                    line.item_id.quantity = line.counted_quantity
            count.state = 'done'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_load_items(self):
        self.ensure_one()
        existing = self.line_ids.mapped('item_id.id')
        items = self.env['utility.inventory.item'].search([
            ('location_id', '=', self.location_id.id),
            ('active', '=', True),
            ('id', 'not in', existing),
        ])
        lines = []
        for item in items:
            lines.append({
                'count_id': self.id,
                'item_id': item.id,
                'expected_quantity': item.quantity,
                'counted_quantity': item.quantity,
            })
        if lines:
            self.env['utility.inventory.count.line'].create(lines)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'utility.inventory.count',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.inventory.count') or _('New')
        return super().create(vals_list)
