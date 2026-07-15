from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io

try:
    import openpyxl
except ImportError:
    openpyxl = None


class UtilityMigrationImportWizard(models.TransientModel):
    _name = 'utility.migration.import.wizard'
    _description = 'معالج استيراد بيانات المشتركين'

    import_file = fields.Binary(string='ملف الإكسل', required=True)
    file_name = fields.Char(string='اسم الملف')

    def action_import_file(self):
        if not openpyxl:
            raise UserError(_("مكتبة openpyxl غير مثبتة. يرجى تثبيتها لقراءة ملفات الإكسل."))
            
        if not self.file_name or not self.file_name.endswith('.xlsx'):
            raise UserError(_("يجب أن يكون الملف بصيغة .xlsx فقط."))

        # Read the file
        file_content = base64.b64decode(self.import_file)
        wb = openpyxl.load_workbook(filename=io.BytesIO(file_content), data_only=True)
        sheet = wb.active

        # We assume the columns map exactly as our template
        # 0: name, 1: mobile, 2: national_id, 3: customer_number, 4: subscriber_no, 5: char_code, 6: is_active
        # 7: legacy_region, 8: legacy_area, 9: legacy_category, 10: legacy_subscriber_type
        # 11: legacy_contract, 12: meter_number, 13: meter_reading, 14: opening_reading
        # 15: last_reading, 16: previous_balance, 17: current_balance

        migration_customer_obj = self.env['utility.migration.customer']
        
        # Keep track of created records to run mapping on them later
        created_records = self.env['utility.migration.customer']
        
        row_idx = 1
        for row in sheet.iter_rows(min_row=2, values_only=True):
            row_idx += 1
            # Check if row is empty
            if not row[0] and not row[3]:
                continue
                
            name = str(row[0] or '').strip()
            mobile = str(row[1] or '').strip()
            national_id = str(row[2] or '').strip()
            customer_number = str(row[3] or '').strip()
            subscriber_no = str(row[4] or '').strip()
            char_code = str(row[5] or '').strip()
            
            # Boolean is_active
            is_active_val = str(row[6] or '').strip().lower()
            is_active = is_active_val not in ('false', '0', 'no', 'لا')
            
            legacy_region = str(row[7] or '').strip()
            legacy_area = str(row[8] or '').strip()
            legacy_category = str(row[9] or '').strip()
            legacy_subscriber_type = str(row[10] or '').strip()
            legacy_contract = str(row[11] or '').strip()
            
            meter_number = str(row[12] or '').strip()
            
            # Numeric fields
            def parse_float(val):
                try:
                    return float(val) if val else 0.0
                except ValueError:
                    return 0.0

            def parse_int(val):
                try:
                    return int(val) if val else 0
                except ValueError:
                    return 0
                    
            meter_reading = parse_int(row[13])
            opening_reading = parse_int(row[14])
            last_reading = parse_float(row[15])
            previous_balance = str(row[16] or '').strip() # Previous balance is Char
            current_balance = parse_float(row[17])
            
            # New fields: phase and is_private_transformer
            phase_val = str(row[18] if len(row) > 18 else '').strip().lower()
            phase = 'three' if '3' in phase_val or 'three' in phase_val or 'ثلاث' in phase_val else 'single'
            
            is_private_val = str(row[19] if len(row) > 19 else '').strip().lower()
            is_private_transformer = is_private_val in ('true', '1', 'yes', 'نعم', 'خاص')
            
            if not name:
                raise UserError(_("الاسم مطلوب في الصف رقم %s") % row_idx)
            if not customer_number:
                raise UserError(_("رقم المشترك مطلوب في الصف رقم %s") % row_idx)

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
                'meter_reading': meter_reading,
                'opening_reading': opening_reading,
                'last_reading': last_reading,
                'previous_balance': previous_balance,
                'current_balance': current_balance,
                'phase': phase,
                'is_private_transformer': is_private_transformer,
                'state': 'draft'
            }
            
            # Search if customer number already exists in migration staging to update or create
            existing = migration_customer_obj.search([('customer_number', '=', customer_number)], limit=1)
            if existing:
                existing.write(vals)
                created_records |= existing
            else:
                new_record = migration_customer_obj.create(vals)
                created_records |= new_record

        # Trigger mapping
        if created_records:
            created_records.action_map_codes()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('تم الاستيراد بنجاح'),
                'message': _('تم رفع %s سجل ومطابقتها تلقائياً.') % len(created_records),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
