from odoo import api, fields, models, _


class UtilityTransformer(models.Model):
    _name = 'utility.transformer'
    _description = 'محول كهرباء'
    _order = 'name'

    active = fields.Boolean('نشط', default=True)
    company_id = fields.Many2one('res.company', 'الشركة', default=lambda self: self.env.company)
    name = fields.Char('اسم المحول', required=True)
    code = fields.Char('رمز المحول', required=True)

    # ===== الموقع في الشبكة =====
    substation_id = fields.Many2one('utility.substation', 'المحطة')
    feeder_id = fields.Many2one('utility.feeder', 'الفيدر / الخلية', index=True)
    zone_region_id = fields.Many2one(
        'utility.region', 'المنطقة (zone)',
        domain="[('type', '=', 'zone')]",
        help='سجل المنطقة (zone) المنشأ تلقائياً في التدرج الهرمي للمناطق'
    )
    area_id = fields.Many2one('utility.region', 'المنطقة الفرعية', related='zone_region_id.parent_id', store=True, readonly=False)
    region_id = fields.Many2one('utility.region', 'المنطقة', related='zone_region_id.parent_id.parent_id', store=True, readonly=False)

    is_private = fields.Boolean(string='محول خاص', default=False, help='يُحدد ما إذا كان المحول خاصاً بمشترك واحد')

    # ===== المواصفات الفنية =====
    capacity = fields.Float('القدرة (kVA)')
    phase = fields.Selection([
        ('single', 'طور واحد'),
        ('three', 'ثلاثة أطوار'),
    ], string='الطور')
    manufacturer = fields.Char('الشركة المصنّعة')
    serial_number = fields.Char('الرقم التسلسلي')
    voltage_primary = fields.Float('الجهد الابتدائي (فولت)')
    voltage_secondary = fields.Float('الجهد الثانوي (فولت)')
    address = fields.Text('العنوان')
    status = fields.Selection([
        ('active', 'نشط'),
        ('inactive', 'غير نشط'),
        ('fault', 'عطل'),
        ('maintenance', 'صيانة'),
    ], string='الحالة', default='active')

    # ===== الربط بالمشتركين والعدادات =====
    meter_ids = fields.One2many('utility.meter', 'transformer_id', string='العدادات')
    coupling_meter_id = fields.Many2one(
        'utility.meter', 'عداد الربط (المقارنة والرصد)',
        domain="[('transformer_id', '=', id)]",
        help='العداد الذي يقيس إجمالي الطاقة الداخلة إلى المحول أو الفيدر',
    )
    customer_ids = fields.One2many(
        'utility.customer', 'transformer_id',
        string='عقود المشتركين',
        help='عقود المشتركين المغذاة من هذا المحول'
    )
    route_ids = fields.One2many(
        'utility.route', 'transformer_id',
        string='مسارات التوزيع',
        help='مسارات التوزيع المرتبطة بهذا المحول'
    )
    customer_count = fields.Integer(
        'عدد العقود',
        compute='_compute_customer_count',
        store=True
    )

    notes = fields.Text('ملاحظات')

    _sql_constraints = [
        ('unique_transformer_code_company', 'unique(code, company_id)',
         'رمز المحول يجب أن يكون فريداً!'),
    ]

    # ===== Compute =====
    @api.depends('customer_ids')
    def _compute_customer_count(self):
        for rec in self:
            rec.customer_count = len(rec.customer_ids)

    # ===== Actions =====
    def action_view_customers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'عقود {self.name}',
            'res_model': 'utility.customer',
            'domain': [('transformer_id', '=', self.id)],
            'views': [(False, 'tree'), (False, 'form')],
        }

    def action_create_coupling_meter(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'إضافة عداد ربط',
            'res_model': 'utility.meter',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_transformer_id': self.id,
                'default_feeder_id': self.feeder_id.id if self.feeder_id else False,
                'default_is_coupling_meter': True,
                'default_payment_type': 'manual',
            },
        }

    def action_open_transformer_balance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'توازن - {self.name}',
            'res_model': 'utility.transformer.balance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_transformer_id': self.id},
        }

    # ===== ORM Overrides =====
    @api.model_create_multi
    def create(self, vals_list):
        # Auto-generate the code from dedicated, fully separated sequences:
        # private transformers (محول خاص) use utility.transformer.private
        # (PRV/...), regular transformers use utility.transformer (TRF/...).
        for vals in vals_list:
            if vals.get('code'):
                continue
            sequence_code = (
                'utility.transformer.private'
                if vals.get('is_private')
                else 'utility.transformer'
            )
            vals['code'] = (
                self.env['ir.sequence'].next_by_code(sequence_code) or _('جديد')
            )

        # Extract initial area_id or region_id passed in vals
        passed_parents = []
        for vals in vals_list:
            area_id = vals.get('area_id', False)
            region_id = vals.get('region_id', False)
            passed_parents.append(area_id or region_id)

        records = super().create(vals_list)

        for idx, rec in enumerate(records):
            if not rec.zone_region_id:
                parent_id = passed_parents[idx]
                zone = self.env['utility.region'].create({
                    'name': rec.name,
                    'code': rec.code,
                    'type': 'zone',
                    'parent_id': parent_id if parent_id else False,
                    'company_id': rec.company_id.id,
                    'transformer_origin_id': rec.id,
                })
                rec.zone_region_id = zone.id
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals or 'code' in vals or 'area_id' in vals or 'region_id' in vals:
            for rec in self:
                if rec.zone_region_id:
                    zone_vals = {}
                    if 'name' in vals:
                        zone_vals['name'] = rec.name
                    if 'code' in vals:
                        zone_vals['code'] = rec.code
                    if 'area_id' in vals or 'region_id' in vals:
                        parent = rec.area_id or rec.region_id
                        zone_vals['parent_id'] = parent.id if parent else False
                    if zone_vals:
                        rec.zone_region_id.write(zone_vals)
        return res

    def unlink(self):
        zones = self.env['utility.region']
        for rec in self:
            if rec.zone_region_id:
                zones |= rec.zone_region_id
        res = super().unlink()
        if zones:
            zones.unlink()
        return res
