import calendar
from datetime import date, datetime, time, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from ..models.utility_date_range import normalize_billing_cadence


class UtilityPeriodGenerator(models.TransientModel):
    _name = 'utility.period.generator'
    _description = 'معالج إنشاء الفترات الزمنية التلقائي'

    year = fields.Integer(
        string="السنة",
        default=lambda self: fields.Date.today().year,
        required=True
    )
    month = fields.Selection([
        ('1', 'يناير (1)'), ('2', 'فبراير (2)'), ('3', 'مارس (3)'),
        ('4', 'أبريل (4)'), ('5', 'مايو (5)'), ('6', 'يونيو (6)'),
        ('7', 'يوليو (7)'), ('8', 'أغسطس (8)'), ('9', 'سبتمبر (9)'),
        ('10', 'أكتوبر (10)'), ('11', 'نوفمبر (11)'), ('12', 'ديسمبر (12)'),
    ], string="الشهر", default=lambda self: str(fields.Date.today().month), required=True)

    billing_cadence = fields.Selection([
        ('all', 'جميع الدورات (شهري + نصف شهري)'),
        ('monthly', 'شهري فقط'),
        ('semi_monthly', 'نصف شهري فقط'),
    ], string="نوع دورة الفوترة", default='all', required=True)

    region_ids = fields.Many2many(
        'utility.region',
        string="المناطق المستهدفة",
        domain="[('type', '=', 'region')]",
        help="اتركه فارغاً لجميع المناطق التابعة للدورية المختارة"
    )

    reading_window_open_days_before = fields.Integer(
        string="فتح نافذة القراءة (أيام قبل نهاية الاستهلاك)",
        default=2
    )
    reading_window_close_days_after = fields.Integer(
        string="إغلاق نافذة القراءة (أيام بعد نهاية الاستهلاك)",
        default=3
    )
    payment_window_open_days_after = fields.Integer(
        string="فتح نافذة السداد (أيام بعد نهاية الاستهلاك)",
        default=1
    )
    payment_window_duration_days = fields.Integer(
        string="مدة نافذة السداد (أيام)",
        default=12
    )

    def action_generate_periods(self):
        self.ensure_one()
        year = self.year
        month = int(self.month)
        _, last_day = calendar.monthrange(year, month)

        DateRange = self.env['date.range'].sudo()

        generated_periods = DateRange

        cadences = ['monthly', 'semi_monthly'] if self.billing_cadence == 'all' else [self.billing_cadence]

        for cadence in cadences:
            # مصدر حقيقة واحد: _get_regions_for_billing_cadence هو الـ Authority
            if self.region_ids:
                # المستخدم حدد مناطق يدوياً → نُضيّق فقط ما يطابق الدورية منها
                target_regions = self.region_ids.filtered(
                    lambda r: normalize_billing_cadence(r.recurring_rule_type) == cadence
                )
            else:
                # لا تحديد يدوي → نستخدم الـ Helper كمصدر حقيقة وحيد
                target_regions = DateRange._get_regions_for_billing_cadence(cadence)


            if cadence == 'monthly':
                c_start = date(year, month, 1)
                c_end = date(year, month, last_day)

                r_code = f"MONTHLY-{year:04d}-{month:02d}"
                r_name = f"شهر {month:02d}-{year:04d} (قراءة)"
                p_code = f"PAY-MONTHLY-{year:04d}-{month:02d}"
                p_name = f"شهر {month:02d}-{year:04d} (تحصيل)"

                rw_start = datetime.combine(c_end - timedelta(days=self.reading_window_open_days_before), time.min)
                rw_end = datetime.combine(c_end + timedelta(days=self.reading_window_close_days_after), time.max)
                pw_start = datetime.combine(c_end + timedelta(days=self.payment_window_open_days_after), time.min)
                pw_end = datetime.combine(pw_start.date() + timedelta(days=self.payment_window_duration_days), time.max)

                reading_period = self._create_or_update_period(
                    DateRange, r_code, r_name, 'reading', cadence,
                    c_start, c_end, rw_start, rw_end, target_regions
                )
                payment_period = self._create_or_update_period(
                    DateRange, p_code, p_name, 'payment', cadence,
                    c_start, c_end, pw_start, pw_end, target_regions,
                    reading_period_id=reading_period.id
                )
                generated_periods |= reading_period | payment_period

            elif cadence == 'semi_monthly':
                # H1: 01 to 15
                h1_start = date(year, month, 1)
                h1_end = date(year, month, 15)
                h1_r_code = f"SEMI-{year:04d}-{month:02d}-H1"
                h1_r_name = f"النصف الأول {month:02d}-{year:04d} (قراءة)"
                h1_p_code = f"PAY-SEMI-{year:04d}-{month:02d}-H1"
                h1_p_name = f"النصف الأول {month:02d}-{year:04d} (تحصيل)"

                h1_rw_start = datetime.combine(h1_end - timedelta(days=self.reading_window_open_days_before), time.min)
                h1_rw_end = datetime.combine(h1_end + timedelta(days=self.reading_window_close_days_after), time.max)
                h1_pw_start = datetime.combine(h1_end + timedelta(days=self.payment_window_open_days_after), time.min)
                h1_pw_end = datetime.combine(h1_pw_start.date() + timedelta(days=self.payment_window_duration_days), time.max)

                h1_reading = self._create_or_update_period(
                    DateRange, h1_r_code, h1_r_name, 'reading', cadence,
                    h1_start, h1_end, h1_rw_start, h1_rw_end, target_regions
                )
                h1_payment = self._create_or_update_period(
                    DateRange, h1_p_code, h1_p_name, 'payment', cadence,
                    h1_start, h1_end, h1_pw_start, h1_pw_end, target_regions,
                    reading_period_id=h1_reading.id
                )

                # H2: 16 to month-end
                h2_start = date(year, month, 16)
                h2_end = date(year, month, last_day)
                h2_r_code = f"SEMI-{year:04d}-{month:02d}-H2"
                h2_r_name = f"النصف الثاني {month:02d}-{year:04d} (قراءة)"
                h2_p_code = f"PAY-SEMI-{year:04d}-{month:02d}-H2"
                h2_p_name = f"النصف الثاني {month:02d}-{year:04d} (تحصيل)"

                h2_rw_start = datetime.combine(h2_end - timedelta(days=self.reading_window_open_days_before), time.min)
                h2_rw_end = datetime.combine(h2_end + timedelta(days=self.reading_window_close_days_after), time.max)
                h2_pw_start = datetime.combine(h2_end + timedelta(days=self.payment_window_open_days_after), time.min)
                h2_pw_end = datetime.combine(h2_pw_start.date() + timedelta(days=self.payment_window_duration_days), time.max)

                h2_reading = self._create_or_update_period(
                    DateRange, h2_r_code, h2_r_name, 'reading', cadence,
                    h2_start, h2_end, h2_rw_start, h2_rw_end, target_regions,
                    previous_period_id=h1_reading.id
                )
                h2_payment = self._create_or_update_period(
                    DateRange, h2_p_code, h2_p_name, 'payment', cadence,
                    h2_start, h2_end, h2_pw_start, h2_pw_end, target_regions,
                    reading_period_id=h2_reading.id,
                    previous_period_id=h1_payment.id
                )
                generated_periods |= h1_reading | h1_payment | h2_reading | h2_payment

        return {
            'type': 'ir.actions.act_window',
            'name': _('الفترات الزمنية المنشأة'),
            'res_model': 'date.range',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', generated_periods.ids)],
        }

    def _create_or_update_period(self, DateRange, code, name, role, cadence, c_start, c_end, w_start, w_end, regions, reading_period_id=False, previous_period_id=False):
        existing = DateRange.search([('period_code', '=', code)], limit=1)
        type_id = self.env['date.range.type'].search([], limit=1).id

        vals = {
            'name': name,
            'period_code': code,
            'period_role': role,
            'billing_cadence': cadence,
            'region_ids': [(6, 0, regions.ids)] if regions else False,
            'type_id': type_id,
        }

        if role == 'reading':
            vals.update({
                'consumption_start': c_start,
                'consumption_end': c_end,
                'date_start': c_start,
                'date_end': c_end,
                'reading_window_start': w_start,
                'reading_window_end': w_end,
            })
        else:
            vals.update({
                'date_start': w_start.date(),
                'date_end': w_end.date(),
                'payment_window_start': w_start,
                'payment_window_end': w_end,
                'reading_period_id': reading_period_id,
            })

        if previous_period_id:
            vals['previous_period_id'] = previous_period_id

        if existing:
            existing.write(vals)
            return existing
        else:
            vals['state'] = 'planned'
            return DateRange.create(vals)
