from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import base64
import io
import datetime

try:
    import openpyxl
except ImportError:
    openpyxl = None


class UtilityMigrationImportWizard(models.TransientModel):
    _name = 'utility.migration.import.wizard'
    _description = 'معالج استيراد بيانات التهيئة والميجريشن'

    import_type = fields.Selection([
        ('customer', 'تهيئة بيانات المشتركين'),
        ('feeder', 'تهيئة بيانات الفيدرات / الخلايا'),
        ('transformer', 'تهيئة بيانات المحولات'),
    ], string='نوع البيانات المراد استيرادها', default='customer', required=True)

    import_file = fields.Binary(string='ملف الإكسل', required=True)
    file_name = fields.Char(string='اسم الملف')

    def action_download_customer_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/utility_core/static/src/Migration_Template.xlsx',
            'target': 'new',
        }

    def action_download_feeder_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/utility_core/static/src/Feeder_Migration_Template.xlsx',
            'target': 'new',
        }

    def action_download_transformer_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/utility_core/static/src/Transformer_Migration_Template.xlsx',
            'target': 'new',
        }

    def _has_cell_value(self, val):
        """التحقق التام من توفر قيمة حقيقية داخل خلية الإكسل (تمييز الفارغ عن الصفر)."""
        return val is not None and str(val).strip() != ''

    def parse_float(self, val):
        try:
            return float(val) if self._has_cell_value(val) else 0.0
        except (ValueError, TypeError):
            return 0.0

    def parse_int(self, val):
        try:
            return int(float(val)) if self._has_cell_value(val) else 0
        except (ValueError, TypeError):
            return 0

    def parse_bool(self, val, default=True):
        if not self._has_cell_value(val):
            return default
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        val_str = str(val).strip().lower()
        if val_str in ('false', '0', '0.0', 'no', 'n', 'لا', 'خطأ', 'f'):
            return False
        if val_str in ('true', '1', '1.0', 'yes', 'y', 'نعم', 'صح', 't'):
            return True
        return default

    def parse_datetime(self, val):
        if isinstance(val, (datetime.datetime, datetime.date)):
            return val
        if not val:
            return False
        val_str = str(val).strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y'):
            try:
                return datetime.datetime.strptime(val_str, fmt)
            except ValueError:
                continue
        return False

    def action_import_file(self):
        if not openpyxl:
            raise UserError(_("مكتبة openpyxl غير مثبتة. يرجى تثبيتها لقراءة ملفات الإكسل."))

        if not self.file_name or not self.file_name.lower().endswith('.xlsx'):
            raise UserError(_("يجب أن يكون الملف بصيغة .xlsx فقط."))

        file_content = base64.b64decode(self.import_file)
        wb = openpyxl.load_workbook(filename=io.BytesIO(file_content), data_only=True)
        sheet = wb.active

        if self.import_type == 'customer':
            return self._import_customers(sheet)
        elif self.import_type == 'feeder':
            return self._import_feeders(sheet)
        elif self.import_type == 'transformer':
            return self._import_transformers(sheet)

    def _import_customers(self, sheet):
        migration_customer_obj = self.env['utility.migration.customer']
        created_records = self.env['utility.migration.customer']
        company_id = self.env.company.id
        row_idx = 0

        for row in sheet.iter_rows(values_only=True):
            row_idx += 1
            if not row or (not row[0] and (len(row) <= 3 or not row[3])):
                continue
            row_head = ' '.join(str(cell or '').strip() for cell in row[:5])
            if any(h in row_head for h in ('الاسم', 'Name', 'منطقة', 'رمز المنطقة', 'نموذج', 'يرجى', 'بيانات')):
                continue

            name = str(row[0] or '').strip()
            mobile = str(row[1] or '').strip() if len(row) > 1 else ''
            national_id = str(row[2] or '').strip() if len(row) > 2 else ''
            customer_number = str(row[3] or '').strip() if len(row) > 3 else ''
            subscriber_no = str(row[4] or '').strip() if len(row) > 4 else ''
            char_code = str(row[5] or '').strip() if len(row) > 5 else ''

            is_active = self.parse_bool(row[6] if len(row) > 6 else True, default=True)

            legacy_region = str(row[7] or '').strip() if len(row) > 7 else ''
            legacy_area = str(row[8] or '').strip() if len(row) > 8 else ''
            legacy_category = str(row[9] or '').strip() if len(row) > 9 else ''
            legacy_subscriber_type = str(row[10] or '').strip() if len(row) > 10 else ''
            legacy_contract = str(row[11] or '').strip() if len(row) > 11 else ''

            meter_number = str(row[12] or '').strip() if len(row) > 12 else ''
            previous_balance = str(row[15] or '').strip() if len(row) > 15 else ''
            current_balance = self.parse_float(row[16]) if len(row) > 16 else 0.0

            phase_val = str(row[17] if len(row) > 17 else '').strip().lower()
            phase = 'three' if '3' in phase_val or 'three' in phase_val or 'ثلاث' in phase_val else 'single'

            is_private_transformer = self.parse_bool(row[18] if len(row) > 18 else False, default=False)
            owner_reference = str(row[19] or '').strip() if len(row) > 19 else ''

            if not name:
                continue
            if not customer_number:
                customer_number = f"CUST-{row_idx}"

            vals = {
                'name': name,
                'mobile': mobile,
                'national_id': national_id,
                'customer_number': customer_number,
                'subscriber_no': subscriber_no,
                'char_code': char_code,
                'is_active': is_active,
                'legacy_region': legacy_region,
                'legacy_area': legacy_area,
                'legacy_category': legacy_category,
                'legacy_subscriber_type': legacy_subscriber_type,
                'legacy_contract': legacy_contract,
                'meter_number': meter_number,
                'previous_balance': previous_balance,
                'current_balance': current_balance,
                'phase': phase,
                'is_private_transformer': is_private_transformer,
                'owner_reference': owner_reference,
                'company_id': company_id,
                'state': 'draft'
            }

            # Preserve cell presence semantics: pass reading fields ONLY if cell has value
            if len(row) > 13 and self._has_cell_value(row[13]):
                vals['meter_reading'] = self.parse_int(row[13])
            if len(row) > 14 and self._has_cell_value(row[14]):
                val_reading = self.parse_float(row[14])
                vals['opening_reading'] = int(val_reading)
                vals['last_reading'] = val_reading

            existing = migration_customer_obj.search([
                ('company_id', '=', company_id),
                ('customer_number', '=', customer_number)
            ], limit=1)
            if existing:
                existing.write(vals)
                created_records |= existing
            else:
                new_record = migration_customer_obj.create(vals)
                created_records |= new_record

        if created_records:
            try:
                created_records.action_map_codes()
            except ValidationError:
                pass

        return self._show_success_notification(len(created_records))

    def _import_feeders(self, sheet):
        feeder_obj = self.env['utility.migration.feeder']
        created_records = self.env['utility.migration.feeder']
        company_id = self.env.company.id
        row_idx = 0

        for row in sheet.iter_rows(values_only=True):
            row_idx += 1
            if not row or not any(row):
                continue

            row_head = ' '.join(str(cell or '').strip() for cell in row[:4])
            if any(h in row_head for h in ('نموذج', 'رمز المنطقة', 'المنطقة/Name', 'المنطقة', 'يرجى', 'بيانات')):
                continue

            legacy_region = str(row[0] or '').strip() if len(row) > 0 else ''
            legacy_area = str(row[1] or '').strip() if len(row) > 1 else ''
            is_active = self.parse_bool(row[2], default=True) if len(row) > 2 else True
            feeder_code = str(row[3] or '').strip() if len(row) > 3 else ''
            feeder_name = str(row[4] or '').strip() if len(row) > 4 else ''
            meter_number = str(row[5] or '').strip() if len(row) > 5 else ''
            meter_multiplier = self.parse_float(row[6]) if len(row) > 6 else 1.0
            is_calc_cell = self.parse_bool(row[8], default=True) if len(row) > 8 else True
            description = str(row[9] or '').strip() if len(row) > 9 else ''

            if not feeder_code and not feeder_name and not meter_number and not description:
                continue

            display_name = feeder_name or feeder_code or description or f"Feeder-{row_idx}"
            code_identity = feeder_code or feeder_name or display_name

            vals = {
                'name': display_name,
                'feeder_code': feeder_code or code_identity,
                'feeder_name': feeder_name,
                'legacy_region': legacy_region,
                'legacy_area': legacy_area,
                'is_active': is_active,
                'meter_number': meter_number,
                'meter_multiplier': meter_multiplier or 1.0,
                'is_calculation_cell': is_calc_cell,
                'description': description,
                'company_id': company_id,
                'state': 'draft'
            }

            # Preserve cell presence semantics: pass reading ONLY if cell has value
            if len(row) > 7 and self._has_cell_value(row[7]):
                vals['current_reading'] = self.parse_float(row[7])

            existing = feeder_obj.search([
                ('company_id', '=', company_id),
                '|', ('feeder_code', '=', code_identity), ('name', '=', display_name)
            ], limit=1)
            if existing:
                existing.write(vals)
                created_records |= existing
            else:
                new_rec = feeder_obj.create(vals)
                created_records |= new_rec

        if created_records:
            try:
                created_records.action_map_codes()
            except ValidationError:
                pass

        return self._show_success_notification(len(created_records))

    def _import_transformers(self, sheet):
        transformer_obj = self.env['utility.migration.transformer']
        created_records = self.env['utility.migration.transformer']
        company_id = self.env.company.id
        row_idx = 0

        for row in sheet.iter_rows(values_only=True):
            row_idx += 1
            if not row or not any(row):
                continue

            row_head = ' '.join(str(cell or '').strip() for cell in row[:4])
            if any(h in row_head for h in ('نموذج', 'رمز المنطقة', 'المنطقة/Name', 'المنطقة', 'يرجى', 'بيانات')):
                continue

            legacy_region = str(row[0] or '').strip() if len(row) > 0 else ''
            legacy_area = str(row[1] or '').strip() if len(row) > 1 else ''
            is_active = self.parse_bool(row[2], default=True) if len(row) > 2 else True
            transformer_code = str(row[3] or '').strip() if len(row) > 3 else ''
            transformer_name = str(row[4] or '').strip() if len(row) > 4 else ''
            meter_number = str(row[5] or '').strip() if len(row) > 5 else ''
            meter_multiplier = self.parse_float(row[6]) if len(row) > 6 else 1.0
            total_consumption = self.parse_float(row[8]) if len(row) > 8 else 0.0
            image_status = str(row[9] or '').strip() if len(row) > 9 else ''
            cell_meter_number = str(row[10] or '').strip() if len(row) > 10 else ''
            cell_meter_multiplier = self.parse_float(row[11]) if len(row) > 11 else 1.0
            reference = str(row[12] or '').strip() if len(row) > 12 else ''
            description = str(row[13] or '').strip() if len(row) > 13 else ''

            if not transformer_code and not transformer_name and not meter_number and not reference and not description:
                continue

            display_name = transformer_name or transformer_code or description or f"Transformer-{row_idx}"
            code_identity = reference or transformer_code or display_name

            vals = {
                'name': display_name,
                'transformer_code': transformer_code or code_identity,
                'transformer_name': transformer_name,
                'legacy_region': legacy_region,
                'legacy_area': legacy_area,
                'is_active': is_active,
                'meter_number': meter_number,
                'meter_multiplier': meter_multiplier or 1.0,
                'total_consumption': total_consumption,
                'image_status': image_status,
                'cell_meter_number': cell_meter_number,
                'cell_meter_multiplier': cell_meter_multiplier or 1.0,
                'reference': reference or code_identity,
                'description': description,
                'company_id': company_id,
                'state': 'draft'
            }

            # Preserve cell presence semantics for current_reading & opening_reading
            if len(row) > 7 and self._has_cell_value(row[7]):
                vals['current_reading'] = self.parse_float(row[7])
            if len(row) > 14 and self._has_cell_value(row[14]):
                vals['opening_reading'] = self.parse_float(row[14])

            existing = transformer_obj.search([
                ('company_id', '=', company_id),
                '|', ('reference', '=', code_identity), ('transformer_code', '=', code_identity)
            ], limit=1)
            if existing:
                existing.write(vals)
                created_records |= existing
            else:
                new_rec = transformer_obj.create(vals)
                created_records |= new_rec

        if created_records:
            try:
                created_records.action_map_codes()
            except ValidationError:
                pass

        return self._show_success_notification(len(created_records))

    def _show_success_notification(self, count):
        return {
            'type': 'ir.actions.act_window_close',
            'tag': 'display_notification',
            'params': {
                'title': _('تم رفع البيانات المبدئية بنجاح'),
                'message': _('تم رفع %s سجل إلى مرحلة التهيئية (Staging).') % count,
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
