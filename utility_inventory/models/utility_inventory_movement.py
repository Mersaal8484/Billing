from odoo import api, fields, models, _


class UtilityInventoryMovement(models.Model):
    _name = 'utility.inventory.movement'
    _description = 'حركة مخزون'
    _rec_name = 'name'
    _order = 'movement_date desc, id desc'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('رقم الحركة', required=True, index=True, default=lambda self: _('New'))
    item_id = fields.Many2one('utility.inventory.item', 'الصنف', required=True, ondelete='restrict')
    movement_type = fields.Selection([
        ('in', 'وارد'),
        ('out', 'صادر'),
        ('adjustment', 'تسوية'),
    ], string='نوع الحركة', required=True)
    quantity = fields.Float('الكمية', required=True)
    reference = fields.Char('المرجع')
    movement_date = fields.Datetime('تاريخ الحركة', default=fields.Datetime.now)
    partner_id = fields.Many2one('res.partner', 'الطرف', ondelete='set null')
    notes = fields.Text('ملاحظات')
    state = fields.Selection([
        ('draft', 'مسودة'),
        ('done', 'تم'),
        ('cancelled', 'ملغي'),
    ], string='الحالة', default='draft')
    user_id = fields.Many2one('res.users', 'المستخدم', default=lambda self: self.env.user)

    def action_done(self):
        for move in self:
            item = move.item_id
            if move.movement_type == 'in':
                item.quantity += move.quantity
            elif move.movement_type == 'out':
                if item.quantity < move.quantity:
                    raise models.ValidationError(
                        _('الكمية غير كافية في المخزون! الكمية المتاحة: %s') % item.quantity
                    )
                item.quantity -= move.quantity
            elif move.movement_type == 'adjustment':
                item.quantity = move.quantity
            move.state = 'done'

    def action_cancel(self):
        self.state = 'cancelled'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('utility.inventory.movement') or _('New')
        return super().create(vals_list)
