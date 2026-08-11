import calendar
from datetime import date, datetime, time, timedelta, timezone
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from ..models.utility_date_range import normalize_billing_cadence


class UtilityPeriodGenerator(models.TransientModel):
    _name = 'utility.period.generator'
    _description = 'معالج إنشاء الفترات الزمنية والدورات التشغيلية'

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

    override_offsets = fields.Boolean(
        string="تخصيص إزاحات النوافذ التشغيلية",
        default=False,
        help="تفعيل لتحديد إزاحات النوافذ يدوياً بدلاً من الاعتماد على إعدادات نوع الفترة"
    )
    reading_start_offset_days = fields.Integer(
        string="بداية القراءة (أيام بالنسبة لنهاية الاستهلاك)",
        default=-2
    )
    reading_end_offset_days = fields.Integer(
        string="نهاية القراءة (أيام بالنسبة لنهاية الاستهلاك)",
        default=3
    )
    payment_start_offset_days = fields.Integer(
        string="بداية التحصيل (أيام بالنسبة لنهاية الاستهلاك)",
        default=1
    )
    payment_end_offset_days = fields.Integer(
        string="نهاية التحصيل (أيام بالنسبة لنهاية الاستهلاك)",
        default=13
    )

    def action_generate_periods(self):
        self.ensure_one()
        year = self.year
        month = int(self.month)
        weekday, last_day = calendar.monthrange(year, month)

        DateRange = self.env['date.range'].sudo()
        generated_periods = DateRange

        cadences = ['monthly', 'semi_monthly'] if self.billing_cadence == 'all' else [self.billing_cadence]

        for cadence in cadences:
            target_regions = DateRange._get_regions_for_billing_cadence(cadence)
            if not target_regions:
                raise ValidationError(_(
                    "لا توجد مناطق نشطة مرتبطة بدورية الفوترة المحددة (%s)."
                ) % cadence)

            if cadence == 'monthly':
                c_start = date(year, month, 1)
                c_end = date(year, month, last_day)
                cycle_key = f"MONTHLY-{year:04d}-{month:02d}"
                r_name = f"شهر {month:02d}-{year:04d} (قراءة ومراجعة)"
                p_name = f"شهر {month:02d}-{year:04d} (سداد وتحصيل)"

                r_period, p_period = self._create_cycle_pair(
                    cycle_key, cadence, c_start, c_end, r_name, p_name, target_regions
                )
                generated_periods |= r_period | p_period

            elif cadence == 'semi_monthly':
                # H1: 01 to 15
                h1_start = date(year, month, 1)
                h1_end = date(year, month, 15)
                h1_cycle_key = f"SEMI-{year:04d}-{month:02d}-H1"
                h1_r_name = f"النصف الأول {month:02d}-{year:04d} (قراءة ومراجعة)"
                h1_p_name = f"النصف الأول {month:02d}-{year:04d} (سداد وتحصيل)"

                h1_reading, h1_payment = self._create_cycle_pair(
                    h1_cycle_key, cadence, h1_start, h1_end, h1_r_name, h1_p_name, target_regions
                )

                # H2: 16 to month-end
                h2_start = date(year, month, 16)
                h2_end = date(year, month, last_day)
                h2_cycle_key = f"SEMI-{year:04d}-{month:02d}-H2"
                h2_r_name = f"النصف الثاني {month:02d}-{year:04d} (قراءة ومراجعة)"
                h2_p_name = f"النصف الثاني {month:02d}-{year:04d} (سداد وتحصيل)"

                h2_reading, h2_payment = self._create_cycle_pair(
                    h2_cycle_key, cadence, h2_start, h2_end, h2_r_name, h2_p_name, target_regions,
                    prev_reading_id=h1_reading.id, prev_payment_id=h1_payment.id
                )

                generated_periods |= h1_reading | h1_payment | h2_reading | h2_payment

        return {
            'type': 'ir.actions.act_window',
            'name': _('الفترات والدورات المنشأة'),
            'res_model': 'date.range',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', generated_periods.ids)],
        }

    def _create_cycle_pair(self, cycle_key, cadence, c_start, c_end, reading_name, payment_name, target_regions, prev_reading_id=False, prev_payment_id=False):
        """إنشاء زوج متكامل (Reading & Review Period + Payment Period) في Transaction واحدة مع ربطهما بـ cycle_key."""
        DateRange = self.env['date.range'].sudo()
        DateRangeType = self.env['date.range.type'].sudo()

        reading_type = DateRangeType._resolve_period_type(cadence, role='reading')
        payment_type = DateRangeType._resolve_period_type(cadence, role='payment')

        # تحديد إزاحات النوافذ
        if self.override_offsets:
            r_start_off = self.reading_start_offset_days
            r_end_off = self.reading_end_offset_days
            p_start_off = self.payment_start_offset_days
            p_end_off = self.payment_end_offset_days
        else:
            r_start_off = reading_type.reading_start_offset_days
            r_end_off = reading_type.reading_end_offset_days
            p_start_off = reading_type.payment_start_offset_days
            p_end_off = reading_type.payment_end_offset_days

        rw_start = self._to_utc_start_of_day(c_end + timedelta(days=r_start_off))
        rw_end = self._to_utc_end_of_day(c_end + timedelta(days=r_end_off))
        pw_start = self._to_utc_start_of_day(c_end + timedelta(days=p_start_off))
        pw_end = self._to_utc_end_of_day(c_end + timedelta(days=p_end_off))

        existing_reading = DateRange.search([('cycle_key', '=', cycle_key), ('period_role', '=', 'reading')], limit=1)
        existing_payment = DateRange.search([('cycle_key', '=', cycle_key), ('period_role', '=', 'payment')], limit=1)

        # Idempotency Guard Policy
        if existing_reading and existing_reading.state != 'planned':
            raise ValidationError(_(
                "الدورة التشغيلية [%s] موجودة مسبقاً وتمر بالحالة العملياتية '%s'. لا يمكن إعادة التوليد التلقائي فوق دورة نشطة."
            ) % (cycle_key, existing_reading.state))
        if existing_payment and existing_payment.state != 'planned':
            raise ValidationError(_(
                "فترة السداد للدورة [%s] موجودة مسبقاً وتمر بالحالة '%s'."
            ) % (cycle_key, existing_payment.state))

        if existing_reading and existing_payment:
            return existing_reading, existing_payment

        read_code = f"READ-{cycle_key}"
        pay_code = f"PAY-{cycle_key}"

        reading_vals = {
            'name': reading_name,
            'period_code': read_code,
            'cycle_key': cycle_key,
            'period_role': 'reading',
            'billing_cadence': cadence,
            'region_ids': [(6, 0, target_regions.ids)],
            'type_id': reading_type.id,
            'consumption_start': c_start,
            'consumption_end': c_end,
            'date_start': c_start,
            'date_end': c_end,
            'reading_window_start': rw_start,
            'reading_window_end': rw_end,
        }
        if prev_reading_id:
            reading_vals['previous_period_id'] = prev_reading_id

        if existing_reading:
            reading_period = existing_reading
        else:
            reading_vals['state'] = 'planned'
            reading_period = DateRange.create(reading_vals)

        payment_vals = {
            'name': payment_name,
            'period_code': pay_code,
            'cycle_key': cycle_key,
            'period_role': 'payment',
            'billing_cadence': cadence,
            'region_ids': [(6, 0, target_regions.ids)],
            'type_id': payment_type.id,
            'date_start': pw_start.date(),
            'date_end': pw_end.date(),
            'payment_window_start': pw_start,
            'payment_window_end': pw_end,
            'reading_period_id': reading_period.id,
        }
        if prev_payment_id:
            payment_vals['previous_period_id'] = prev_payment_id

        if existing_payment:
            payment_period = existing_payment
        else:
            payment_vals['state'] = 'planned'
            payment_period = DateRange.create(payment_vals)

        return reading_period, payment_period

    def _to_utc_start_of_day(self, local_date):
        """Convert a local date to a UTC naive datetime at 00:00:00."""
        user_tz = self.env.user.tz or self.env.context.get('tz') or 'UTC'
        local_dt = pytz.timezone(user_tz).localize(datetime.combine(local_date, time.min))
        return local_dt.astimezone(timezone.utc).replace(tzinfo=None)

    def _to_utc_end_of_day(self, local_date):
        """Convert a local date to a UTC naive datetime at 23:59:59.999999."""
        user_tz = self.env.user.tz or self.env.context.get('tz') or 'UTC'
        local_dt = pytz.timezone(user_tz).localize(datetime.combine(local_date, time.max))
        return local_dt.astimezone(timezone.utc).replace(tzinfo=None)
