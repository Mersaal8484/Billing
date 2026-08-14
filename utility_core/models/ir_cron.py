import base64
import datetime
import dateutil
import logging
import pytz
import time
import traceback
import zlib

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class IrCron(models.Model):
    _inherit = 'ir.cron'

    utility_managed = fields.Boolean(
        string='مُدار عبر نظام الكهرباء / Managed by Utility ERP',
        default=False,
        index=True,
        help='حدد هذا الخيار لتمكين المراقبة والتحكم في المهمة من خلال لوحة تحكم الكهرباء',
    )
    utility_code = fields.Char(
        string='رمز المهمة الفني / Utility Job Code',
        index=True,
        copy=False,
        help='معرف تقني فريد ومستقر للمهمة المجدولة لا يتغير بالترجمة',
    )
    utility_category = fields.Selection([
        ('reading', 'قراءات / Reading'),
        ('billing', 'فوترة / Billing'),
        ('accounting', 'محاسبة / Accounting'),
        ('operations', 'عمليات / Operations'),
        ('integration', 'تكامل / Integration'),
        ('notification', 'إشعارات / Notification'),
        ('maintenance', 'صيانة / Maintenance'),
    ], string='التصنيف التشغيلي / Utility Category', index=True)

    utility_description = fields.Text(
        string='الوصف التشغيلي / Operational Description',
        help='شرح تفصيلي للغرض من المهمة وتأثيرها التشغيلي والمالي',
    )

    allow_manual_run = fields.Boolean(
        string='السماح بالتشغيل اليدوي / Allow Manual Run',
        default=True,
        help='إتاحة زر التشغيل الفوري للمشرفين ومدراء العمليات',
    )
    allow_schedule_edit = fields.Boolean(
        string='السماح بتعديل الجدولة / Allow Schedule Edit',
        default=True,
        help='السماح لمدير النظام بتعديل فترات التكرار ووقت التنفيذ القادم',
    )
    allow_disable = fields.Boolean(
        string='السماح بالتعطيل / Allow Disable',
        default=True,
        help='السماح بتعطيل المهمة (يجب إلغاء التحديد للمهام الحيوية التي لا يجوز تعطيلها)',
    )
    prevent_overlap = fields.Boolean(
        string='منع التداخل والتزامن / Prevent Parallel Overlap',
        default=True,
        help='استخدام قفل استشاري بقاعدة البيانات لمنع تشغيل أكثر من نسخة في نفس الوقت',
    )
    batch_size = fields.Integer(
        string='حجم الدفعة الافتراضي / Batch Size',
        default=0,
        help='الحد الأقصى لعدد السجلات المعالجة في الدورة الواحدة',
    )

    last_started_at = fields.Datetime(
        string='وقت آخر تشغيل / Last Started At',
        readonly=True,
    )
    last_finished_at = fields.Datetime(
        string='وقت آخر انتهاء / Last Finished At',
        readonly=True,
    )
    last_success_at = fields.Datetime(
        string='وقت آخر نجاح / Last Success At',
        readonly=True,
    )
    last_failure_at = fields.Datetime(
        string='وقت آخر فشل / Last Failure At',
        readonly=True,
    )
    last_duration_seconds = fields.Float(
        string='مدة آخر تشغيل (ث) / Last Duration (s)',
        digits=(12, 3),
        readonly=True,
    )
    last_execution_status = fields.Selection([
        ('never', 'لم ينفذ قط / Never Run'),
        ('running', 'قيد التنفيذ / Running'),
        ('success', 'ناجح / Success'),
        ('partial', 'ناجح جزئياً / Partial'),
        ('failed', 'فاشل / Failed'),
        ('skipped', 'تم التخطي / Skipped'),
    ], string='حالة آخر تشغيل / Last Execution Status', default='never', readonly=True)

    consecutive_failure_count = fields.Integer(
        string='الإخفاقات المتتالية / Consecutive Failures',
        default=0,
        readonly=True,
    )
    last_error_message = fields.Text(
        string='آخر رسالة خطأ / Last Error Message',
        readonly=True,
    )

    health_status = fields.Selection([
        ('disabled', 'معطل / Disabled'),
        ('never_run', 'لم ينفذ / Never Run'),
        ('healthy', 'سليم / Healthy'),
        ('running', 'قيد التشغيل / Running'),
        ('warning', 'تحذير (نجاح جزئي) / Warning'),
        ('delayed', 'متأخر عن الموعد / Delayed'),
        ('failed', 'فاشل / Failed'),
    ], string='الحالة التشغيلية / Health Status', compute='_compute_health_status', store=True, index=True)

    execution_count = fields.Integer(
        string='إجمالي مرات التنفيذ / Total Executions',
        compute='_compute_execution_counts',
    )
    failure_count = fields.Integer(
        string='مرات الفشل / Total Failures',
        compute='_compute_execution_counts',
    )
    target_model_name = fields.Char(
        string='النموذج المستهدف / Target Model',
        related='model_id.model',
        readonly=True,
    )

    _sql_constraints = [
        ('uniq_utility_code', 'unique(utility_code)', 'رمز المهمة المجدولة يجب أن يكون فريداً! / Utility Job Code must be unique!')
    ]

    @api.constrains('utility_code', 'utility_managed')
    def _check_utility_code(self):
        for rec in self:
            if rec.utility_managed and rec.utility_code:
                duplicates = self.search([
                    ('id', '!=', rec.id),
                    ('utility_code', '=', rec.utility_code),
                ])
                if duplicates:
                    raise ValidationError(_('رمز المهمة المجدولة (%s) مستخدم بالفعل في مهمة أخرى!') % rec.utility_code)

    @api.depends('active', 'last_execution_status', 'consecutive_failure_count', 'nextcall', 'interval_number', 'interval_type', 'last_started_at')
    def _compute_health_status(self):
        now = fields.Datetime.now()
        interval_map = {
            'minutes': 60,
            'hours': 3600,
            'days': 86400,
            'weeks': 604800,
            'months': 2592000,
        }
        for rec in self:
            if not rec.active:
                rec.health_status = 'disabled'
                continue
            if rec.last_execution_status == 'never' and not rec.last_started_at:
                rec.health_status = 'never_run'
                continue
            if rec.last_execution_status == 'running':
                if rec.last_started_at and (now - rec.last_started_at).total_seconds() > 7200:
                    rec.health_status = 'delayed'
                else:
                    rec.health_status = 'running'
                continue
            if rec.last_execution_status == 'failed' or rec.consecutive_failure_count > 0:
                rec.health_status = 'failed'
                continue
            if rec.last_execution_status == 'partial':
                rec.health_status = 'warning'
                continue

            interval_secs = rec.interval_number * interval_map.get(rec.interval_type, 3600)
            delay_tolerance = max(2 * interval_secs, 900)
            if rec.nextcall and (now - rec.nextcall).total_seconds() > delay_tolerance:
                rec.health_status = 'delayed'
                continue

            rec.health_status = 'healthy'

    def _compute_execution_counts(self):
        Execution = self.env['utility.cron.execution']
        for rec in self:
            rec.execution_count = Execution.search_count([('cron_id', '=', rec.id)])
            rec.failure_count = Execution.search_count([('cron_id', '=', rec.id), ('status', '=', 'failed')])

    # -------------------------------------------------------------------------
    # PostgreSQL Advisory Lock Mechanisms
    # -------------------------------------------------------------------------
    def _get_advisory_lock_key(self):
        self.ensure_one()
        ident = f"utility_cron_{self.utility_code or self.id}"
        return zlib.crc32(ident.encode('utf-8'))

    def _acquire_advisory_lock(self):
        self.ensure_one()
        lock_key = self._get_advisory_lock_key()
        self.env.cr.execute("SELECT pg_try_advisory_lock(%s);", (lock_key,))
        row = self.env.cr.fetchone()
        return bool(row and row[0])

    def _release_advisory_lock(self):
        self.ensure_one()
        lock_key = self._get_advisory_lock_key()
        try:
            self.env.cr.execute("SELECT pg_advisory_unlock(%s);", (lock_key,))
        except Exception as exc:
            _logger.warning("Error releasing advisory lock %s for cron %s: %s", lock_key, self.utility_code, exc)

    # -------------------------------------------------------------------------
    # Unified Execution Engine
    # -------------------------------------------------------------------------
    def _run_business_job(self):
        self.ensure_one()
        if self.code and self.model_id:
            model = self.env[self.model_id.model]
            eval_context = {
                'env': self.env,
                'model': model,
                'time': time,
                'datetime': datetime,
                'dateutil': dateutil,
                'timezone': pytz.timezone,
                'b64encode': base64.b64encode,
                'b64decode': base64.b64decode,
                '_logger': _logger,
            }
            clean_code = self.code.strip()
            try:
                return safe_eval(clean_code, eval_context, mode="eval", nocopy=True)
            except SyntaxError:
                safe_eval(clean_code, eval_context, mode="exec", nocopy=True)
                return eval_context.get('result') or eval_context.get('action')
        else:
            return self.with_context(active_model=self.model_name, active_id=self.id).ir_actions_server_id.run()

    def _execute_utility_managed_cron(self, trigger_type='scheduled'):
        self.ensure_one()
        if not self.utility_managed:
            raise UserError(_('لا يمكن تطبيق هذه العملية إلا على المهام المدارة بواسطة نظام الكهرباء.'))

        has_lock = False
        if self.prevent_overlap:
            has_lock = self._acquire_advisory_lock()
            if not has_lock:
                _logger.info("Utility Cron [%s] skipped because another execution is currently active (lock held).", self.utility_code or self.name)
                self.env['utility.cron.execution'].sudo().with_context(_cron_internal_write=True).create({
                    'cron_id': self.id,
                    'utility_code': self.utility_code,
                    'started_at': fields.Datetime.now(),
                    'finished_at': fields.Datetime.now(),
                    'duration_seconds': 0.0,
                    'trigger_type': trigger_type,
                    'triggered_by': self.env.user.id,
                    'status': 'skipped',
                    'error_message': _('تم التخطي: هناك جلسة معالجة أخرى نشطة حالياً لنفس المهمة (قفل التزامن).'),
                    'company_id': self.env.company.id,
                })
                return {'status': 'skipped', 'reason': 'locked'}

        started_at = fields.Datetime.now()
        exec_log = self.env['utility.cron.execution'].sudo().with_context(_cron_internal_write=True).create({
            'cron_id': self.id,
            'utility_code': self.utility_code,
            'started_at': started_at,
            'trigger_type': trigger_type,
            'triggered_by': self.env.user.id,
            'status': 'running',
            'company_id': self.env.company.id,
        })

        self.sudo().with_context(_cron_internal_write=True).write({
            'last_started_at': started_at,
            'last_execution_status': 'running',
        })

        status = 'success'
        err_msg = False
        err_details = False
        processed = 0
        success_cnt = 0
        failed_cnt = 0
        skipped_cnt = 0
        duration = 0.0

        try:
            _logger.info("Utility Cron [%s] started (trigger=%s)", self.utility_code or self.name, trigger_type)
            result = self._run_business_job()

            if isinstance(result, dict):
                processed = result.get('processed', result.get('total', 0))
                success_cnt = result.get('success', 0)
                failed_cnt = result.get('failed', result.get('errors', 0))
                skipped_cnt = result.get('skipped', 0)
                if failed_cnt > 0:
                    status = 'partial'
                else:
                    status = 'success'
            elif isinstance(result, int):
                processed = result
                success_cnt = result
                failed_cnt = 0
                status = 'success'
            else:
                status = 'success'

            _logger.info(
                "Utility Cron [%s] completed: status=%s, processed=%d, success=%d, failed=%d, skipped=%d",
                self.utility_code or self.name, status, processed, success_cnt, failed_cnt, skipped_cnt
            )

        except Exception as exc:
            status = 'failed'
            err_msg = str(exc)
            err_details = traceback.format_exc()
            _logger.exception("Utility Cron [%s] failed with exception: %s", self.utility_code or self.name, exc)

        finally:
            finished_at = fields.Datetime.now()
            duration = (finished_at - started_at).total_seconds()

            exec_log.with_context(_cron_internal_write=True).write({
                'finished_at': finished_at,
                'duration_seconds': duration,
                'status': status,
                'processed_count': processed,
                'success_count': success_cnt,
                'failure_count': failed_cnt,
                'skipped_count': skipped_cnt,
                'error_message': err_msg,
                'error_details': err_details,
            })

            cron_vals = {
                'last_finished_at': finished_at,
                'last_duration_seconds': duration,
                'last_execution_status': status,
            }
            if status in ('success', 'partial'):
                cron_vals['last_success_at'] = finished_at
                cron_vals['consecutive_failure_count'] = 0
                cron_vals['last_error_message'] = False
            elif status == 'failed':
                cron_vals['last_failure_at'] = finished_at
                cron_vals['consecutive_failure_count'] = self.consecutive_failure_count + 1
                cron_vals['last_error_message'] = err_msg

            self.sudo().with_context(_cron_internal_write=True).write(cron_vals)

            if has_lock:
                self._release_advisory_lock()

            if status == 'failed':
                self._check_failure_alert()

        return {
            'status': status,
            'processed': processed,
            'success': success_cnt,
            'failed': failed_cnt,
            'skipped': skipped_cnt,
            'duration': duration,
            'error_message': err_msg,
        }

    def _check_failure_alert(self):
        """Send notification or log alert if consecutive failures exceed threshold."""
        ICP = self.env['ir.config_parameter'].sudo()
        threshold = int(ICP.get_param('utility.cron_failure_alert_threshold', 3))
        if self.consecutive_failure_count >= threshold:
            _logger.warning(
                "ALERT: Utility Cron [%s] has failed %d consecutive times! Last error: %s",
                self.utility_code or self.name, self.consecutive_failure_count, self.last_error_message
            )

    @classmethod
    def _callback(cls, cron_name, server_action_id, job_id):
        """Intercept Odoo scheduler execution for Utility-managed scheduled actions."""
        # Find record in database
        cron = cls.browse(job_id)
        if cron.exists() and cron.utility_managed:
            return cron._execute_utility_managed_cron(trigger_type='scheduled')
        return super()._callback(cron_name, server_action_id, job_id)

    def method_direct_trigger(self):
        """Intercept direct manual triggers for Utility-managed scheduled actions."""
        if self.utility_managed:
            self._verify_manual_run_security()
            return self._execute_utility_managed_cron(trigger_type='manual')
        return super().method_direct_trigger()

    # -------------------------------------------------------------------------
    # Security & Action Controls
    # -------------------------------------------------------------------------
    def _verify_manual_run_security(self):
        self.ensure_one()
        if not self.utility_managed:
            raise UserError(_('العملية متاحة فقط للمهام المدارة بواسطة نظام الكهرباء.'))
        if not self.allow_manual_run:
            raise UserError(_('التشغيل اليدوي غير مسموح لهذه المهمة (%s).') % self.name)
        user = self.env.user
        allowed_groups = [
            'utility_core.group_utility_supervisor',
            'utility_core.group_utility_billing_manager',
            'utility_core.group_utility_revenue_manager',
            'utility_core.group_utility_admin',
            'base.group_system',
            'base.group_erp_manager',
        ]
        if not any(user.has_group(g) for g in allowed_groups):
            raise AccessError(_('ليس لديك صلاحية تشغيل المهام المجدولة يدوياً / Permission denied for manual cron execution.'))

    def _verify_admin_security(self):
        self.ensure_one()
        if not self.utility_managed:
            raise UserError(_('العملية متاحة فقط للمهام المدارة بواسطة نظام الكهرباء.'))
        user = self.env.user
        allowed_groups = [
            'utility_core.group_utility_admin',
            'base.group_system',
            'base.group_erp_manager',
        ]
        if not any(user.has_group(g) for g in allowed_groups):
            raise AccessError(_('هذه العملية تتطلب صلاحية مدير نظام الكهرباء / Utility Administrator permission required.'))

    def action_run_now(self):
        """زر التشغيل اليدوي الفوري من شاشة إدارة المهام المجدولة."""
        self.ensure_one()
        self._verify_manual_run_security()
        res = self._execute_utility_managed_cron(trigger_type='manual')
        status = res.get('status')
        msg_type = 'success' if status == 'success' else ('warning' if status in ('partial', 'skipped') else 'danger')
        if status == 'skipped':
            msg = _('تم تخطي التنفيذ: هناك عملية أخرى نشطة حالياً لنفس المهمة (قفل التزامن).')
        elif status == 'failed':
            msg = _('فشل تنفيذ المهمة: %s') % (res.get('error_message') or _('خطأ غير معروف'))
        elif status == 'partial':
            msg = _('اكتمل التنفيذ مع وجود أخطاء جزئية: معالج: %d, ناجح: %d, فاشل: %d') % (
                res.get('processed', 0), res.get('success', 0), res.get('failed', 0)
            )
        else:
            msg = _('تم تنفيذ المهمة بنجاح في %.2f ثانية (معالج: %d, ناجح: %d)') % (
                res.get('duration', 0.0), res.get('processed', 0), res.get('success', 0)
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('تنفيذ المهمة: %s') % self.name,
                'message': msg,
                'type': msg_type,
                'sticky': False,
            }
        }

    def action_enable(self):
        """تمكين المهمة المجدولة."""
        for rec in self:
            rec._verify_admin_security()
            rec.write({'active': True})

    def action_disable(self):
        """تعطيل المهمة المجدولة."""
        for rec in self:
            rec._verify_admin_security()
            if not rec.allow_disable:
                raise UserError(_('لا يمكن تعطيل هذه المهمة الجوهرية (%s).') % rec.name)
            rec.write({'active': False})

    def action_reset_failure_count(self):
        """تصفير عداد الإخفاقات المتتالية."""
        for rec in self:
            rec._verify_admin_security()
            rec.sudo().with_context(_cron_internal_write=True).write({
                'consecutive_failure_count': 0,
                'last_execution_status': 'never' if rec.last_execution_status == 'failed' else rec.last_execution_status,
                'last_error_message': False,
            })

    def action_view_executions(self):
        """عرض سجلات تنفيذ هذه المهمة."""
        self.ensure_one()
        return {
            'name': _('سجل تنفيذ: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'utility.cron.execution',
            'view_mode': 'tree,form',
            'domain': [('cron_id', '=', self.id)],
            'context': {'default_cron_id': self.id, 'search_default_cron_id': self.id},
        }

    def action_view_failures(self):
        """عرض سجلات الإخفاقات فقط لهذه المهمة."""
        self.ensure_one()
        return {
            'name': _('سجل إخفاقات: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'utility.cron.execution',
            'view_mode': 'tree,form',
            'domain': [('cron_id', '=', self.id), ('status', '=', 'failed')],
            'context': {'default_cron_id': self.id, 'search_default_cron_id': self.id},
        }
