from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilityMeterExt(models.Model):
    _inherit = 'utility.meter'

    # stock.lot.name is the sole physical serial source. This is a read-only
    # projection for integrations and legacy screens, not an independent value.
    serial_number = fields.Char(
        related='lot_id.name', string='الرقم التسلسلي', store=True,
        readonly=True, index=True,
    )

    product_id = fields.Many2one('product.product', 'المنتج', ondelete='restrict',
                                  help='منتج العداد المستخدم في المخزون لتتبع الرقم التسلسلي')
    lot_id = fields.Many2one('stock.lot', 'الرقم التسلسلي (Lot/Serial)', ondelete='restrict',
                             help='ربط العداد بالرقم التسلسلي في نظام المخزون')

    physical_state = fields.Selection([
        ('unresolved', 'غير محدد بالمخزون'),
        ('available', 'متاح بالمخزون'),
        ('installed', 'مركب لدى مشترك'),
        ('inspection', 'تحت الفحص'),
        ('repair', 'قيد الصيانة'),
        ('scrap', 'تالف / خردة'),
    ], string='الحالة الفيزيائية', compute='_compute_physical_state', store=False)

    def _get_lot_current_location(self):
        self.ensure_one()
        if not self.lot_id:
            return False
        quant = self.env['stock.quant'].search([
            ('lot_id', '=', self.lot_id.id),
            ('quantity', '>', 0),
        ], limit=1)
        return quant.location_id if quant else False

    @api.depends('lot_id', 'product_id')
    def _compute_physical_state(self):
        for meter in self:
            if not meter.lot_id or not meter.product_id:
                meter.physical_state = 'unresolved'
                continue
            loc = meter._get_lot_current_location()
            if not loc:
                meter.physical_state = 'available'
            elif loc.scrap_location:
                meter.physical_state = 'scrap'
            elif loc.usage == 'customer':
                meter.physical_state = 'installed'
            elif 'repair' in (loc.name or '').lower() or 'صيانة' in (loc.name or ''):
                meter.physical_state = 'repair'
            elif 'inspection' in (loc.name or '').lower() or 'فحص' in (loc.name or ''):
                meter.physical_state = 'inspection'
            else:
                meter.physical_state = 'available'

    def _get_physical_serial(self):
        self.ensure_one()
        return self.lot_id.name or ''

    @api.depends('lot_id.name')
    def _compute_qr_code(self):
        return super()._compute_qr_code()

    @api.model
    def _name_search_domain(self, name, operator='ilike'):
        domain = super()._name_search_domain(name, operator)
        if name:
            return ['|', ('lot_id.name', operator, name)] + domain
        return domain

    @api.model
    def _scan_domain(self, value):
        return ['|', ('meter_number', '=', value), ('lot_id.name', '=', value)]

    @api.model_create_multi
    def create(self, vals_list):
        """Convert legacy serial input into the canonical stock lot."""
        Lot = self.env['stock.lot']
        for vals in vals_list:
            legacy_serial = (vals.pop('serial_number', None) or '').strip() or False
            if not legacy_serial:
                continue
            lot = Lot.browse(vals.get('lot_id')).exists() if vals.get('lot_id') else Lot
            if lot and lot.name != legacy_serial:
                raise ValidationError(_(
                    'الرقم التسلسلي المدخل لا يطابق الرقم التسلسلي في المخزون.'
                ))
            if not lot:
                product = self.env['product.product'].browse(vals.get('product_id')).exists()
                if not product:
                    raise ValidationError(_(
                        'يجب تحديد منتج مهدأ بالتتبع التسلسلي قبل إنشاء رقم عداد مادي.'
                    ))
                lot = Lot.search([
                    ('name', '=', legacy_serial),
                    ('product_id', '=', product.id),
                ], limit=1)
                if not lot:
                    lot = Lot.create({
                        'name': legacy_serial,
                        'product_id': product.id,
                        'company_id': vals.get('company_id') or self.env.company.id,
                    })
                vals['lot_id'] = lot.id
        return super().create(vals_list)

    def write(self, vals):
        """Reject independent serial edits and route legacy input to stock."""
        vals = dict(vals)
        if 'serial_number' in vals:
            legacy_serial = (vals.pop('serial_number') or '').strip() or False
            for meter in self:
                if legacy_serial and meter.lot_id and meter.lot_id.name != legacy_serial:
                    raise ValidationError(_(
                        'لا يمكن تعديل الرقم التسلسلي من شاشة العداد؛ عدّل رقم Lot/Serial في المخزون.'
                    ))
                if legacy_serial and not meter.lot_id:
                    product = meter.product_id
                    if not product:
                        raise ValidationError(_(
                            'يجب تحديد منتج مهدأ بالتتبع التسلسلي قبل ربط الرقم المادي.'
                        ))
                    lot = self.env['stock.lot'].search([
                        ('name', '=', legacy_serial),
                        ('product_id', '=', product.id),
                    ], limit=1) or self.env['stock.lot'].create({
                        'name': legacy_serial,
                        'product_id': product.id,
                        'company_id': meter.company_id.id,
                    })
                    vals['lot_id'] = lot.id
        return super().write(vals)

    @api.onchange('model_id')
    def _onchange_model_id_product(self):
        if self.model_id and getattr(self.model_id, 'product_id', False) and not self.product_id:
            self.product_id = self.model_id.product_id

    @api.constrains('model_id', 'product_id')
    def _check_utility_inventory_model_product_consistency(self):
        for meter in self:
            if meter.model_id and getattr(meter.model_id, 'product_id', False) and meter.product_id:
                if meter.product_id != meter.model_id.product_id:
                    raise ValidationError(_(
                        'منتج العداد المختار بالمخزون (%s) لا يطابق منتج موديل العداد (%s).'
                    ) % (meter.product_id.display_name, meter.model_id.product_id.display_name))

    @api.constrains('product_id', 'lot_id', 'company_id')
    def _check_utility_inventory_serial_integrity(self):
        for meter in self:
            if meter.lot_id and meter.product_id:
                if meter.lot_id.product_id != meter.product_id:
                    raise ValidationError(_(
                        'الرقم التسلسلي (%s) غير مطابق لمنتج العداد (%s).'
                    ) % (meter.lot_id.name, meter.product_id.display_name))
            if meter.product_id and meter.product_id.tracking != 'serial':
                raise ValidationError(_(
                    'منتج العداد (%s) يجب أن يكون مهدأ بالتتبع التسلسلي (serial tracking).'
                ) % meter.product_id.display_name)
            if meter.lot_id:
                duplicate = self.search([
                    ('id', '!=', meter.id),
                    ('lot_id', '=', meter.lot_id.id),
                    ('active', '=', True),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'الرقم التسلسلي (%s) مستخدم مسبقًا لعداد آخر (%s).'
                    ) % (meter.lot_id.name, duplicate.meter_number or duplicate.display_name))
                if meter.lot_id.company_id and meter.company_id and meter.lot_id.company_id != meter.company_id:
                    raise ValidationError(_(
                        'شركة الرقم التسلسلي تسند إلى شركة مختلفة عن العداد.'
                    ))
                scrap_quant = self.env['stock.quant'].search([
                    ('lot_id', '=', meter.lot_id.id),
                    ('quantity', '>', 0),
                    ('location_id.scrap_location', '=', True),
                ], limit=1)
                if scrap_quant:
                    raise ValidationError(_(
                        'لا يمكن اختيار رقم تسلسلي مكهن أو تالف من مخزن الخردة (%s).'
                    ) % scrap_quant.location_id.display_name)

    # ── Canonical Physical Inventory Execution API ──────────────────────

    def _ensure_physical_identity(self, action_name='حركة مخزنية'):
        self.ensure_one()
        if not self.product_id or not self.lot_id:
            raise ValidationError(_(
                'العداد %s ليس له هوية مخزنية مادية مكتملة (يلزم تحديد المنتج والرقم التسلسلي بالمخزون) '
                'لتنفيذ إجراء "%s". لا يمكن تنفيذ عمليات مخزنية مادية لعدادات تراثية غير مهدأة بالمخزون.'
            ) % (self.meter_number or self.operational_number or self.display_name, action_name))

    def _resolve_meter_inspection_location(self, company=None, warehouse=None):
        company = company or self.company_id or self.env.company
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)

        if warehouse:
            warehouse._ensure_meter_inspection_location()
            if warehouse.meter_inspection_location_id:
                return warehouse.meter_inspection_location_id

        loc = self.env.ref('utility_inventory.stock_location_meter_inspection', raise_if_not_found=False)
        if not loc:
            loc = self.env['stock.location'].search([
                ('name', 'ilike', 'Meter Inspection'),
                '|', ('company_id', '=', False), ('company_id', '=', company.id),
            ], limit=1) or self.env['stock.location'].search([
                ('name', 'ilike', 'فحص العدادات'),
                '|', ('company_id', '=', False), ('company_id', '=', company.id),
            ], limit=1)
        if not loc:
            parent_loc = self.env.ref('stock.stock_location_locations', raise_if_not_found=False)
            loc = self.env['stock.location'].create({
                'name': 'فحص العدادات (Meter Inspection)',
                'usage': 'internal',
                'location_id': parent_loc.id if parent_loc else False,
                'company_id': company.id,
            })
        return loc

    def _resolve_meter_picking_type(self, source_loc, dest_loc, warehouse=None, company=None):
        company = company or self.company_id or self.env.company
        if source_loc.usage == 'internal' and dest_loc.usage == 'customer':
            code = 'outgoing'
            label = 'إخراج / تسليم (Outgoing)'
        elif source_loc.usage == 'customer' and dest_loc.usage == 'internal':
            code = 'incoming'
            label = 'إدخال / استلام (Incoming)'
        else:
            code = 'internal'
            label = 'نقل داخلي (Internal)'

        domain = [('code', '=', code), ('company_id', '=', company.id)]
        if warehouse:
            domain.append(('warehouse_id', '=', warehouse.id))

        picking_type = self.env['stock.picking.type'].search(domain, limit=1)
        if not picking_type and warehouse:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', code),
                ('company_id', '=', company.id),
            ], limit=1)

        if not picking_type:
            raise ValidationError(_('تعذر تحديد نوع الحركة المخزنية (%s - Code: %s) للشركة %s.') % (label, code, company.name))
        return picking_type

    def _validate_physical_meter_location(self, expected_usage=None):
        self.ensure_one()
        self._ensure_physical_identity(_('التحقق من موقع العداد'))
        loc = self._get_lot_current_location()

        if expected_usage and loc and loc.usage != expected_usage:
            raise ValidationError(_(
                'العداد %s موجود حاليًا في موقع "%s" وليس في الموقع المتوقع (%s).'
            ) % (self.meter_number, loc.display_name, expected_usage))

    def _validate_physical_meter_for_installation(self, source_loc=None):
        self.ensure_one()
        self._ensure_physical_identity(_('تركيب عداد'))

        if self.product_id.tracking != 'serial':
            raise ValidationError(_('منتج العداد (%s) لا يستخدم التتبع التسلسلي.') % self.product_id.display_name)

        if self.lot_id.product_id != self.product_id:
            raise ValidationError(_(
                'الرقم التسلسلي %s غير مطابق لمنتج العداد %s.'
            ) % (self.lot_id.name, self.product_id.display_name))

        if self.lot_id.company_id and self.company_id and self.lot_id.company_id != self.company_id:
            raise ValidationError(_('شركة الرقم التسلسلي تختلف عن شركة العداد.'))

        scrap_quant = self.env['stock.quant'].search([
            ('lot_id', '=', self.lot_id.id),
            ('quantity', '>', 0),
            ('location_id.scrap_location', '=', True),
        ], limit=1)
        if scrap_quant:
            raise ValidationError(_(
                'الرقم التسلسلي (%s) موجود في موقع التكهين/الخردة (%s) ولا يمكن تركيبه.'
            ) % (self.lot_id.name, scrap_quant.location_id.display_name))

        if source_loc and source_loc.usage == 'customer':
            current_loc = self._get_lot_current_location()
            if current_loc and current_loc.usage == 'customer':
                raise ValidationError(_('العداد %s مُركب بالفعل لدى مشترك آخر في المخزون.') % self.meter_number)

    def _get_existing_meter_picking(self, operation_type, operation_ref):
        if not operation_ref:
            return False
        return self.env['stock.picking'].search([
            ('utility_operation_ref', '=', operation_ref),
            ('utility_inventory_operation', '=', operation_type),
            ('state', '!=', 'cancel'),
        ], limit=1)

    def _create_single_stock_movement(self, source_loc, dest_loc, operation_type, operation_ref=None, origin=None):
        self.ensure_one()
        existing = self._get_existing_meter_picking(operation_type, operation_ref)
        if existing:
            return existing

        company = self.company_id or self.env.company
        picking_type = self._resolve_meter_picking_type(source_loc, dest_loc, company=company)

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source_loc.id,
            'location_dest_id': dest_loc.id,
            'origin': origin or operation_ref or self.meter_number,
            'utility_inventory_operation': operation_type,
            'utility_meter_id': self.id,
            'utility_operation_ref': operation_ref,
            'company_id': company.id,
        })

        move = self.env['stock.move'].create({
            'name': self.meter_number,
            'product_id': self.product_id.id,
            'product_uom_qty': 1,
            'product_uom': self.product_id.uom_id.id,
            'picking_id': picking.id,
            'location_id': source_loc.id,
            'location_dest_id': dest_loc.id,
            'company_id': company.id,
        })

        self.env['stock.move.line'].create({
            'move_id': move.id,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_id.uom_id.id,
            'qty_done': 1,
            'lot_id': self.lot_id.id,
            'picking_id': picking.id,
            'location_id': source_loc.id,
            'location_dest_id': dest_loc.id,
            'company_id': company.id,
        })

        picking.action_confirm()
        picking.button_validate()
        return picking

    def inventory_install_meter(self, customer=None, origin=None, operation_ref=None):
        """Execute physical meter installation (Stock -> Customers)."""
        self.ensure_one()
        self._ensure_physical_identity(_('تركيب عداد'))

        stock_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        cust_loc = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not stock_loc or not cust_loc:
            raise ValidationError(_('مواقع المخزون (Stock/Customers) غير معرفة في النظام.'))

        self._validate_physical_meter_for_installation(source_loc=stock_loc)

        op_ref = operation_ref or (f"{origin}:INSTALL:{self.id}" if origin else f"INSTALL:{self.id}")
        return self._create_single_stock_movement(
            source_loc=stock_loc,
            dest_loc=cust_loc,
            operation_type='install',
            operation_ref=op_ref,
            origin=origin,
        )

    def inventory_remove_meter(self, origin=None, operation_ref=None, destination='inspection'):
        """Execute physical meter removal (Customers -> Meter Inspection / Stock / Scrap)."""
        self.ensure_one()
        self._ensure_physical_identity(_('إزالة عداد'))

        cust_loc = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not cust_loc:
            raise ValidationError(_('موقع العملاء (Customers Location) غير معرف.'))

        if destination == 'scrap':
            dest_loc = self.env.ref('stock.stock_location_scrapped', raise_if_not_found=False)
        elif destination == 'stock':
            dest_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        else:
            dest_loc = self._resolve_meter_inspection_location()

        if not dest_loc:
            raise ValidationError(_('موقع الوجهة المخزنية للإزالة غير معرف.'))

        op_ref = operation_ref or (f"{origin}:REMOVE:{self.id}" if origin else f"REMOVE:{self.id}")
        return self._create_single_stock_movement(
            source_loc=cust_loc,
            dest_loc=dest_loc,
            operation_type='remove',
            operation_ref=op_ref,
            origin=origin,
        )

    def inventory_replace_meter(self, new_meter, origin=None, operation_ref=None, old_destination='inspection'):
        """Atomic physical meter replacement:
        1. Validate old & new physical meters completely upfront
        2. Remove old meter (Customers -> Inspection)
        3. Install new meter (Stock -> Customers)
        """
        self.ensure_one()
        old_meter = self

        # 1. Atomic Upfront Validation
        old_meter._ensure_physical_identity(_('إزالة عداد للاستبدال'))
        if not new_meter:
            raise ValidationError(_('يجب تحديد العداد الجديد المراد تركيبه.'))
        new_meter._ensure_physical_identity(_('تركيب عداد للاستبدال'))

        cust_loc = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        stock_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        if not cust_loc or not stock_loc:
            raise ValidationError(_('مواقع المخزون (Stock/Customers) غير معرفة.'))

        new_meter._validate_physical_meter_for_installation(source_loc=stock_loc)

        company = old_meter.company_id or self.env.company
        if new_meter.company_id and new_meter.company_id != company:
            raise ValidationError(_('شركة العداد الجديد تختلف عن شركة العداد القديم.'))

        # 2. Execute Movements
        base_ref = operation_ref or origin or f"REPLACE:{old_meter.id}:{new_meter.id}"
        old_op_ref = f"{base_ref}:REPLACE_REMOVE:{old_meter.id}"
        new_op_ref = f"{base_ref}:REPLACE_INSTALL:{new_meter.id}"

        old_picking = old_meter.inventory_remove_meter(
            origin=origin,
            operation_ref=old_op_ref,
            destination=old_destination,
        )

        new_picking = new_meter.inventory_install_meter(
            origin=origin,
            operation_ref=new_op_ref,
        )

        return {
            'old_picking': old_picking,
            'new_picking': new_picking,
        }

    def inventory_return_to_stock(self, origin=None, operation_ref=None):
        """Return meter from Inspection -> Stock."""
        self.ensure_one()
        self._ensure_physical_identity(_('إعادة العداد للمخزون'))

        inspection_loc = self._resolve_meter_inspection_location()
        stock_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        if not inspection_loc or not stock_loc:
            raise ValidationError(_('مواقع المخزون (Inspection/Stock) غير معرفة.'))

        op_ref = operation_ref or (f"{origin}:RETURN:{self.id}" if origin else f"RETURN:{self.id}")
        return self._create_single_stock_movement(
            source_loc=inspection_loc,
            dest_loc=stock_loc,
            operation_type='return',
            operation_ref=op_ref,
            origin=origin,
        )

    def inventory_scrap_meter(self, origin=None, operation_ref=None):
        """Route meter from Inspection/Stock -> Scrap."""
        self.ensure_one()
        self._ensure_physical_identity(_('تكهين عداد'))

        current_loc = self._get_lot_current_location() or self._resolve_meter_inspection_location()
        scrap_loc = self.env.ref('stock.stock_location_scrapped', raise_if_not_found=False)
        if not current_loc or not scrap_loc:
            raise ValidationError(_('مواقع المخزون (Scrap Location) غير معرفة.'))

        op_ref = operation_ref or (f"{origin}:SCRAP:{self.id}" if origin else f"SCRAP:{self.id}")
        return self._create_single_stock_movement(
            source_loc=current_loc,
            dest_loc=scrap_loc,
            operation_type='scrap',
            operation_ref=op_ref,
            origin=origin,
        )


class UtilityMeterModelInventory(models.Model):
    _inherit = 'utility.meter.model'

    product_id = fields.Many2one(
        'product.product', 'المنتج بالمخزون', ondelete='restrict',
        domain="[('tracking', '=', 'serial')]",
        help='المنتج الذي يمثل هذا الموديل الفني في نظام المخزون',
    )

    def action_open_product(self):
        self.ensure_one()
        if self.product_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'المنتج في المخزون',
                'res_model': 'product.product',
                'res_id': self.product_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
