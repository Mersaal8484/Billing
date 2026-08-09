from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class UtilitySaleOrderBilling(models.Model):
    _inherit = 'sale.order'

    def action_recalculate_bill(self):
        for order in self:
            if order.state == 'draft':
                order._calculate_amounts()

    def _calculate_amounts(self):
        if self.state not in ('draft', 'sent'):
            raise ValidationError(
                'لا يمكن إعادة حساب بنود الفاتورة [%s] لأنها في حالة "%s".\nاستخدم إشعار الدائن (Credit Note) لتصحيح المبالغ.' % (self.name, self.state)
            )
        self.ensure_one()
        with self.env.cr.savepoint():
            self._calculate_amounts_inner()

    def _calculate_amounts_inner(self):
        account = self.customer_id
        category = account.subscriber_id if account else False
        consumption = self.consumption or 0.0
        lines = []
        template = account.contract_template_id if account else False

        self.amount_energy = 0.0
        self.amount_service = 0.0
        self.amount_discount = 0.0
        self.amount_local_fee = 0.0
        self.amount_private_transformer_fee = 0.0

        Product = self.env['product.product']
        kwh_product = self.env.ref(
            'utility_core.utility_product_kwh', raise_if_not_found=False
        ) or Product.search([('type', '=', 'service')], limit=1)
        fixed_product = self.env.ref(
            'utility_core.utility_product_fixed_fee', raise_if_not_found=False
        ) or Product.search([('type', '=', 'service')], limit=1)
        service_product = self.env.ref(
            'utility_core.utility_product_service_charge', raise_if_not_found=False
        ) or Product.search([('type', '=', 'service')], limit=1)

        if template:
            for line in template.line_ids.sorted('sequence'):
                if template.pricing_mode in ('block', 'tier') and line.meter_line_type == 'consumption':
                    continue

                if line.meter_line_type == 'discount' and template.discount_block_ids:
                    discount_units = 0.0
                    name = line.name or line.product_id.name or ''
                    if line.qty_formula_id:
                        discount_units, name = line.qty_formula_id.execute(
                            consumption=consumption,
                            previous_reading=self.previous_reading,
                            current_reading=self.current_reading,
                            template=template,
                            account=account,
                            category=category,
                            line=line,
                        )
                    elif template and template.discount_formula_id:
                        discount_units, name = template.discount_formula_id.execute(
                            consumption=consumption,
                            previous_reading=self.previous_reading,
                            current_reading=self.current_reading,
                            template=template,
                            account=account,
                            category=category,
                            line=line,
                        )
                    discount_units = max(discount_units or 0.0, 0.0)
                    if discount_units > 0:
                        sponsor_id = template.sponsor_id.id if template.sponsor_id else False
                        product_id = line.product_id.id if line.product_id else False
                        d_lines, d_amount = self._prepare_block_discount_lines(template, discount_units, name, product_id, sponsor_id)
                        lines.extend(d_lines)
                        self._accumulate_amount('discount', d_amount)
                    continue

                qty, price, name, product_id, sponsor_id = self._compute_line_amounts(
                    line, consumption, account, category, template
                )
                if not qty and not price:
                    continue
                amount = qty * price
                lines.append((0, 0, {
                    'product_id': product_id or kwh_product.id if kwh_product else False,
                    'name': name or line.name or line.product_id.name or '',
                    'product_uom_qty': qty,
                    'price_unit': price,
                    'sponsor_id': sponsor_id,
                    'meter_line_type': line.meter_line_type,
                    'tax_id': [(5, 0, 0)],
                }))
                self._accumulate_amount(line.meter_line_type, amount)

            if template.pricing_mode in ('block', 'tier') and consumption > 0:
                if template.pricing_mode == 'block':
                    block_lines, block_amount = self._prepare_block_consumption_lines(
                        template, consumption, kwh_product
                    )
                else:
                    block_lines, block_amount = self._prepare_tier_consumption_lines(
                        template, consumption, kwh_product
                    )
                lines.extend(block_lines)
                self.amount_energy += block_amount

            existing_local_fee_types = [l.meter_line_type for l in template.line_ids if l.meter_line_type in ('mu_allim', 'cleaning', 'municipality')]
            company = self.company_id or self.env.company

            if 'mu_allim' not in existing_local_fee_types and template.local_fee_mu_allim > 0:
                prod = company.mu_allim_product_id or service_product
                amount = consumption * template.local_fee_mu_allim
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod.id,
                        'name': 'رسم المعلم',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_mu_allim,
                        'meter_line_type': 'mu_allim',
                        'tax_id': [(5, 0, 0)],
                    }))
                    self.amount_local_fee += amount

            if 'cleaning' not in existing_local_fee_types and template.local_fee_cleaning > 0:
                prod = company.cleaning_product_id or service_product
                amount = consumption * template.local_fee_cleaning
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod.id,
                        'name': 'رسم النظافة',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_cleaning,
                        'meter_line_type': 'cleaning',
                        'tax_id': [(5, 0, 0)],
                    }))
                    self.amount_local_fee += amount

            if 'municipality' not in existing_local_fee_types and template.local_fee_per_kwh > 0:
                prod = company.local_fee_product_id or service_product
                amount = consumption * template.local_fee_per_kwh
                if amount > 0:
                    lines.append((0, 0, {
                        'product_id': prod.id,
                        'name': 'رسم محلي (مجالس محلية)',
                        'product_uom_qty': consumption,
                        'price_unit': template.local_fee_per_kwh,
                        'meter_line_type': 'municipality',
                        'tax_id': [(5, 0, 0)],
                    }))
                    self.amount_local_fee += amount

        if template:
            pre_total = (self.amount_energy + self.amount_service + self.amount_local_fee)
            if template.min_charge and pre_total < template.min_charge:
                lines.append((0, 0, {
                    'product_id': fixed_product.id if fixed_product else False,
                    'name': f'تسوية إلى الحد الأدنى ({template.min_charge})',
                    'product_uom_qty': 1,
                    'price_unit': template.min_charge - pre_total,
                    'meter_line_type': 'fixed_fee',
                    'tax_id': [(5, 0, 0)],
                }))
                self.amount_service += template.min_charge - pre_total
            elif template.max_charge and pre_total > template.max_charge:
                lines.append((0, 0, {
                    'product_id': fixed_product.id if fixed_product else False,
                    'name': f'تسوية إلى الحد الأقصى ({template.max_charge})',
                    'product_uom_qty': 1,
                    'price_unit': template.max_charge - pre_total,
                    'meter_line_type': 'discount',
                    'tax_id': [(5, 0, 0)],
                }))
                self.amount_discount += pre_total - template.max_charge

        self._append_private_transformer_fee_line(lines)

        # Give every generated component a deterministic identity.  The key is
        # based on the generated source/type and its stable occurrence order;
        # it is not derived from mutable posted accounting values.
        occurrence = {}
        for command in lines:
            line_vals = command[2]
            component_type = line_vals.get('meter_line_type') or 'other'
            occurrence[component_type] = occurrence.get(component_type, 0) + 1
            line_vals['utility_component_key'] = '%s:%s:%s' % (
                component_type,
                occurrence[component_type],
                line_vals.get('product_id') or 0,
            )

        self.order_line = [(5, 0, 0)] + lines

    def _append_private_transformer_fee_line(self, lines):
        """أضف رسوم المحول الخاص كبند مستقل بعد احتساب الاستهلاك والتعرفة.

        الرسوم تُضاف مرة واحدة فقط لكل دورة فوترة، وتنطبق فقط عندما:
          - يكون الحساب مرتبطاً بمحول خاص (transformer_id.is_private = True)
          - وتكون قيمة الرسوم أكبر من صفر
        بند واحد فقط لكل (حساب + فترة)؛ إعادة الحساب تستبدل البنود ولا تكررها.
        """
        account = self.customer_id
        if not account:
            return
        fee = account.private_transformer_fee or 0.0
        transformer = account.transformer_id
        if not (transformer and transformer.is_private) or fee <= 0:
            return
        company = self.company_id or self.env.company
        fee_product = getattr(company, 'private_transformer_fee_product_id', False)
        if not fee_product:
            raise ValidationError(_(
                'لا يمكن إضافة رسوم المحول الخاص للمشترك [%s] في فترة [%s] '
                'لأنه لم يتم تحديد منتج رسوم المحول الخاص في إعدادات الشركة.'
            ) % (account.customer_number, self.date_range_id.name or ''))
        lines.append((0, 0, {
            'product_id': fee_product.id,
            'name': _('رسوم المحول الخاص'),
            'product_uom_qty': 1,
            'price_unit': fee,
            'meter_line_type': 'private_transformer_fee',
            'private_transformer_id': transformer.id,
            'tax_id': [(5, 0, 0)],
        }))
        self.amount_private_transformer_fee += fee

    def _prepare_block_consumption_lines(self, template, consumption, kwh_product):
        self.ensure_one()
        if not template.block_ids:
            raise ValidationError(
                _('قالب العقد "%s" مضبوط على التسعير بالشرائح، لكن لا توجد شرائح معرفة.')
                % template.name
            )

        lines = []
        priced_qty = 0.0
        amount_energy = 0.0
        for block in template.block_ids.sorted(lambda b: (b.from_kwh, b.sequence, b.id)):
            block_from = block.from_kwh or 0.0
            block_to = block.to_kwh if block.to_kwh > 0 else consumption
            qty_in_block = max(0.0, min(consumption, block_to) - block_from)
            if qty_in_block <= 0:
                continue

            amount = qty_in_block * block.price_per_kwh
            block_to_label = f'{block.to_kwh:.0f}' if block.to_kwh > 0 else _('ما لا نهاية')
            block_name = block.name or _('الشريحة %s') % block.sequence
            lines.append((0, 0, {
                'product_id': kwh_product.id if kwh_product else False,
                'name': _('%s: %.0f - %s kWh') % (block_name, block.from_kwh or 0.0, block_to_label),
                'product_uom_qty': qty_in_block,
                'price_unit': block.price_per_kwh,
                'meter_line_type': 'consumption',
                'tax_id': [(5, 0, 0)],
            }))
            priced_qty += qty_in_block
            amount_energy += amount

        if consumption - priced_qty > 0.000001:
            raise ValidationError(
                _('قالب العقد "%s" لا يغطي كامل الاستهلاك بالشرائح. الاستهلاك: %.2f kWh، المسعر: %.2f kWh.')
                % (template.name, consumption, priced_qty)
            )
        return lines, amount_energy

    def _prepare_block_discount_lines(self, template, discount_units, base_name, product_id, sponsor_id):
        lines = []
        amount_discount = 0.0
        priced_units = 0.0
        for block in template.discount_block_ids.sorted(lambda b: (b.from_kwh, b.sequence, b.id)):
            block_from = block.from_kwh or 0.0
            block_to = block.to_kwh if block.to_kwh > 0 else discount_units
            qty_in_block = max(0.0, min(discount_units, block_to) - block_from)
            if qty_in_block <= 0:
                continue

            price = -abs(block.price_per_kwh)
            amount = qty_in_block * price
            block_name = f"{base_name or 'خصم استهلاك مدعوم'} - شريحة الخصم ({(block.from_kwh or 0.0):.0f} إلى {block.to_kwh if block.to_kwh > 0 else 'ما لا نهاية'})"
            lines.append((0, 0, {
                'product_id': product_id,
                'name': block_name,
                'product_uom_qty': qty_in_block,
                'price_unit': price,
                'sponsor_id': sponsor_id,
                'meter_line_type': 'discount',
                'tax_id': [(5, 0, 0)],
            }))
            amount_discount += amount
            priced_units += qty_in_block

        if discount_units - priced_units > 0.000001:
            raise ValidationError(
                _('قالب العقد "%s" لا يغطي كامل وحدات الخصم بالشرائح. وحدات الخصم: %.2f، المسعر: %.2f.')
                % (template.name, discount_units, priced_units)
            )
        return lines, amount_discount

    def _prepare_tier_consumption_lines(self, template, consumption, kwh_product):
        lines = []
        amount_energy = 0.0
        applicable_block = None

        for block in template.block_ids.sorted(lambda b: (b.from_kwh, b.sequence, b.id)):
            if block.from_kwh <= consumption and (block.to_kwh >= consumption or block.to_kwh == 0.0):
                applicable_block = block
                break

        if not applicable_block and template.block_ids:
            applicable_block = template.block_ids.sorted(lambda b: (b.from_kwh, b.sequence, b.id))[-1]

        price = applicable_block.price_per_kwh if applicable_block else (template.price_per_kwh or 0.0)
        name = applicable_block.name if applicable_block and applicable_block.name else 'استهلاك (مستوى واحد)'

        if price > 0:
            amount = consumption * price
            lines.append((0, 0, {
                'product_id': kwh_product.id if kwh_product else False,
                'name': name,
                'product_uom_qty': consumption,
                'price_unit': price,
                'meter_line_type': 'consumption',
                'tax_id': [(5, 0, 0)],
            }))
            amount_energy += amount

        return lines, amount_energy

    def _compute_line_amounts(self, line, consumption, account, category, template):
        qty = 0.0
        price = 0.0
        name = line.name or line.product_id.name or ''
        product_id = line.product_id.id if line.product_id else False
        sponsor_id = False

        template_price = template.price_per_kwh if template else 0.0
        template_service = template.service_charge if template else 0.0

        if line.meter_line_type == 'consumption':
            if line.qty_formula_id:
                qty, name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )
            else:
                qty = consumption
            price = line.specific_price or template_price

        elif line.meter_line_type in ('fixed_fee', 'service_charge'):
            if line.qty_formula_id:
                qty, name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )
            else:
                qty = 1.0
            price = line.specific_price or template_service

        elif line.meter_line_type in ('mu_allim', 'cleaning', 'municipality'):
            qty = consumption
            if line.specific_price:
                price = line.specific_price
            elif template:
                if line.meter_line_type == 'mu_allim':
                    price = template.local_fee_mu_allim
                elif line.meter_line_type == 'cleaning':
                    price = template.local_fee_cleaning
                else:
                    price = template.local_fee_per_kwh
            else:
                price = 0.0
            if not line.name:
                type_labels = {
                    'municipality': 'رسم مجلس محلي',
                    'mu_allim': 'رسم المعلم',
                    'cleaning': 'رسم نظافة',
                }
                name = type_labels.get(line.meter_line_type, 'رسم محلي')

        elif line.meter_line_type == 'discount':
            discount_units = 0.0
            if line.qty_formula_id:
                discount_units, name = line.qty_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )
            elif template and template.discount_formula_id:
                discount_units, name = template.discount_formula_id.execute(
                    consumption=consumption,
                    previous_reading=self.previous_reading,
                    current_reading=self.current_reading,
                    template=template,
                    account=account,
                    category=category,
                    line=line,
                )

            discount_units = max(discount_units or 0.0, 0.0)
            sponsor_id = template.sponsor_id.id if template and template.sponsor_id else False
            if discount_units > 0 and line.specific_price:
                qty = discount_units
                price = -abs(line.specific_price)
            else:
                qty = 1.0
                price = 0.0

        return qty, price, name, product_id, sponsor_id

    def _accumulate_amount(self, meter_line_type, amount):
        if meter_line_type == 'consumption':
            self.amount_energy += amount
        elif meter_line_type in ('fixed_fee', 'service_charge'):
            self.amount_service += amount
        elif meter_line_type in ('local_fee', 'mu_allim', 'cleaning', 'municipality'):
            self.amount_local_fee += amount
        elif meter_line_type == 'private_transformer_fee':
            self.amount_private_transformer_fee += amount
        elif meter_line_type == 'discount':
            self.amount_discount += abs(amount)
