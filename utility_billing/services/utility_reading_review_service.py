import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError

_logger = logging.getLogger(__name__)


class UtilityReadingReviewService(models.AbstractModel):
    _name = 'utility.reading.review.service'
    _description = 'مخدم مراجعة وتدقيق قراءات العدادات الرقمية'

    @api.model
    def get_review_queue(self, period_id=False, region_id=False, batch_id=False, status='under_review', anomaly_filter='all', review_tab='commercial', search='', offset=0, limit=40):
        """
        جلب قائمة مراجعة القراءات مقسمة حسب التبويب والطلب العملياتي (Commercial, Network, Replacements, Exceptions):
        - Commercial: القراءات التجارية القابلة للفوترة (المشتركين والمحولات الخاصة).
        - Network: قراءات الفيدرات والمحولات العامة ذات الطابع الفني والهندسي.
        - Replacements: عمليات استبدال العدادات المزدوجة (إغلاق القديم + افتتاح الجديد) بميزانية 20 عملية = 40 صورة مصغرة.
        - Exceptions: القراءات ذات التنبيهات الشديدة أو المشاكل الفنية بالصور.
        """
        user = self.env.user
        Reading = self.env['utility.reading'].sudo()

        domain = []

        # 1. القيد الجغرافي للمستخدم (Geographic Scope)
        if not (user.has_group('utility_core.group_utility_admin') or user.has_group('utility_core.group_utility_auditor')):
            if hasattr(user, 'utility_region_ids') and user.utility_region_ids:
                domain.append(('account_id.region_id', 'in', user.utility_region_ids.ids))

        # 2. الفلاتر الأفقية (Period, Region, Batch)
        if period_id:
            domain.append(('date_range_id', '=', int(period_id)))
        if region_id:
            domain.append(('account_id.region_id', '=', int(region_id)))
        if batch_id:
            domain.append(('image_asset_id.batch_id', '=', int(batch_id)))

        # 3. التبويب العملياتي (Review Context Tab)
        if review_tab == 'commercial':
            domain.append(('is_billable', '=', True))
        elif review_tab == 'network':
            domain.append(('reading_category', 'in', ['transformer', 'feeder']))
            domain.append(('is_private_transformer', '=', False))
        elif review_tab == 'exceptions':
            domain.append('|')
            domain.append(('consumption_alert', '!=', 'normal'))
            domain.append(('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read']))

        # 4. فلتر الحالة (Review Status)
        if status == 'under_review':
            domain.append(('state', '=', 'under_review'))
        elif status == 'approved':
            domain.append(('state', '=', 'approved'))
        elif status == 'rejected':
            domain.append(('state', '=', 'draft'))
            domain.append(('rejection_reason', '!=', False))
        elif status == 'exceptions':
            domain.append('|')
            domain.append(('state', '=', 'error'))
            domain.append(('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read']))
        elif status == 'all':
            domain.append(('state', 'in', ['under_review', 'approved', 'draft', 'error']))

        # 5. فلتر الشذوذ والمعاينة الفنية (VEE / Anomaly Filter)
        if anomaly_filter == 'high_consumption':
            domain.append(('consumption_alert', '=', 'high'))
        elif anomaly_filter == 'negative_consumption':
            domain.append(('consumption_alert', '=', 'negative'))
        elif anomaly_filter == 'zero_consumption':
            domain.append(('consumption_alert', '=', 'zero'))
        elif anomaly_filter == 'image_issues':
            domain.append(('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read']))
        elif anomaly_filter == 'anomalies':
            domain.append('|')
            domain.append(('consumption_alert', '!=', 'normal'))
            domain.append(('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read']))

        # 6. البحث النصي السريع (Debounce Search)
        if search and search.strip():
            term = search.strip()
            domain.append('|')
            domain.append('|')
            domain.append(('meter_id.meter_number', 'ilike', term))
            domain.append(('account_id.name', 'ilike', term))
            domain.append(('account_id.subscriber_code', 'ilike', term))

        # معالجة خاصة لتبويب الاستبدال (Meter Replacement Pair View)
        if review_tab == 'replacements':
            Replacement = self.env['utility.meter.replacement'].sudo()
            repl_domain = []
            if region_id:
                repl_domain.append(('utility_account_id.region_id', '=', int(region_id)))
            
            total_repls = Replacement.search_count(repl_domain)
            replacements = Replacement.search(repl_domain, offset=offset, limit=20, order='replace_date desc, id desc')
            
            repl_items = []
            for r in replacements:
                closing = r.closing_reading_id
                opening = r.opening_reading_id
                
                closing_asset = closing.image_asset_id if closing else False
                opening_asset = opening.image_asset_id if opening else False

                repl_items.append({
                    'id': r.id,
                    'name': r.name,
                    'target_type': r.target_type,
                    'target_name': r.utility_account_id.name if r.utility_account_id else (r.feeder_id.name if r.feeder_id else (r.transformer_id.name if r.transformer_id else '')),
                    'subscriber_code': r.utility_account_id.subscriber_code if r.utility_account_id else '',
                    'replace_date': fields.Datetime.to_string(r.replace_date) if r.replace_date else '',
                    'reason': r.reason or '',
                    'state': r.state,
                    'old_meter': {
                        'reading_id': closing.id if closing else False,
                        'meter_number': r.old_meter_number or (closing.meter_id.meter_number if closing else ''),
                        'closing_reading': r.old_closing_reading,
                        'previous_reading': r.old_last_invo_reading,
                        'uninvoiced_consumption': r.old_uninvoiced_consumption,
                        'image_state': closing.image_state if closing else 'none',
                        'thumbnail_url': f"/utility/media/{closing_asset.asset_uuid}/thumbnail" if closing_asset else '',
                        'review_url': f"/utility/media/{closing_asset.asset_uuid}/review" if closing_asset else '',
                    },
                    'new_meter': {
                        'reading_id': opening.id if opening else False,
                        'meter_number': r.new_meter_number or (opening.meter_id.meter_number if opening else ''),
                        'opening_reading': r.new_opening_reading,
                        'multiplier': r.new_meter_val or 1.0,
                        'image_state': opening.image_state if opening else 'none',
                        'thumbnail_url': f"/utility/media/{opening_asset.asset_uuid}/thumbnail" if opening_asset else '',
                        'review_url': f"/utility/media/{opening_asset.asset_uuid}/review" if opening_asset else '',
                    }
                })

            pages_count = (total_repls + 19) // 20 if total_repls > 0 else 1
            current_page = (offset // 20) + 1 if total_repls > 0 else 1

            return {
                'items': repl_items,
                'is_replacement_tab': True,
                'pagination': {
                    'page': current_page,
                    'page_size': 20,
                    'total': total_repls,
                    'pages': pages_count,
                    'offset': offset,
                },
                'stats': {
                    'pending': Reading.search_count([('state', '=', 'under_review')]),
                    'approved': Reading.search_count([('state', '=', 'approved')]),
                    'rejected': Reading.search_count([('state', '=', 'draft'), ('rejection_reason', '!=', False)]),
                    'exceptions': Reading.search_count(['|', ('state', '=', 'error'), ('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read'])]),
                }
            }

        # 7. جلب عدد السجلات الإجمالي والمجموعة الحالية المفهرسة
        total_count = Reading.search_count(domain)
        readings = Reading.search(domain, offset=offset, limit=limit, order='reading_date desc, id desc')

        # 7. حساب الإحصائيات الشاملة لطابور العمل (Queue Statistics Summary)
        base_stats_domain = [d for d in domain if d[0] != 'state' and not (isinstance(d, tuple) and d[0] == 'rejection_reason')]
        pending_count = Reading.search_count(base_stats_domain + [('state', '=', 'under_review')])
        approved_count = Reading.search_count(base_stats_domain + [('state', '=', 'approved')])
        rejected_count = Reading.search_count(base_stats_domain + [('state', '=', 'draft'), ('rejection_reason', '!=', False)])
        exceptions_count = Reading.search_count(base_stats_domain + ['|', ('state', '=', 'error'), ('image_state', 'in', ['not_clear', 'not_same', 'none', 'loss_read'])])

        items = []
        for r in readings:
            asset = r.image_asset_id
            asset_uuid = asset.asset_uuid if asset else False
            
            # توليد روابط التداول الخفيفة دون ثنائيات Base64
            if asset_uuid:
                thumb_url = f"/utility/media/{asset_uuid}/thumbnail"
                review_url = f"/utility/media/{asset_uuid}/review"
                orig_url = f"/utility/media/{asset_uuid}/original"
            elif r.attachment_id:
                thumb_url = f"/web/image/{r.attachment_id.id}"
                review_url = f"/web/image/{r.attachment_id.id}"
                orig_url = f"/web/image/{r.attachment_id.id}"
            else:
                thumb_url = ''
                review_url = ''
                orig_url = ''

            vee_flags = []
            if r.consumption_alert == 'high':
                vee_flags.append({'code': 'HIGH_CONSUMPTION', 'label': _('استهلاك مرتفع جدًا'), 'level': 'warning'})
            elif r.consumption_alert == 'negative':
                vee_flags.append({'code': 'NEGATIVE_CONSUMPTION', 'label': _('استهلاك سلبي'), 'level': 'danger'})
            elif r.consumption_alert == 'zero':
                vee_flags.append({'code': 'ZERO_CONSUMPTION', 'label': _('استهلاك صفر'), 'level': 'info'})

            if r.image_state == 'not_clear':
                vee_flags.append({'code': 'IMAGE_UNREADABLE', 'label': _('صورة غير واضحة'), 'level': 'danger'})
            elif r.image_state == 'not_same':
                vee_flags.append({'code': 'IMAGE_MISMATCH', 'label': _('صورة لا تطابق العداد'), 'level': 'danger'})
            elif r.image_state == 'none':
                vee_flags.append({'code': 'MISSING_IMAGE', 'label': _('بدون صورة عداد'), 'level': 'warning'})

            items.append({
                'id': r.id,
                'meter_number': r.meter_id.meter_number if r.meter_id else '',
                'account_name': r.account_id.name if r.account_id else (r.feeder_id.name if r.feeder_id else (r.transformer_id.name if r.transformer_id else '')),
                'subscriber_code': r.account_id.subscriber_code if r.account_id else '',
                'region_name': r.account_id.region_id.name if r.account_id and r.account_id.region_id else '',
                'previous_reading': r.previous_reading,
                'current_reading': r.reading_value,
                'consumption': r.consumption,
                'reading_date': fields.Datetime.to_string(r.reading_date) if r.reading_date else '',
                'previous_reading': r.previous_reading or 0.0,
                'current_reading': r.reading_value or 0.0,
                'consumption': r.billing_consumption or r.consumption or 0.0,
                'reading_category': r.reading_category,
                'reading_purpose': r.reading_purpose,
                'reading_event': r.reading_event,
                'billing_behavior': r.billing_behavior,
                'billing_behavior_label': dict(r._fields['billing_behavior'].selection).get(r.billing_behavior, ''),
                'is_billable': r.is_billable,
                'meter_multiplier': r.meter_multiplier or 1.0,
                'reading_type': r.reading_type or 'manual',
                'state': r.state,
                'image_state': r.image_state or 'none',
                'consumption_alert': r.consumption_alert or 'normal',
                'asset_uuid': asset_uuid,
                'thumbnail_url': thumb_url,
                'review_url': review_url,
                'original_url': orig_url,
                'rejection_reason': r.rejection_reason or '',
                'review_notes': r.review_notes or '',
                'reviewer_id': r.reviewer_id.id if r.reviewer_id else False,
                'reviewer_name': r.reviewer_id.name if r.reviewer_id else '',
                'review_date': fields.Datetime.to_string(r.review_date) if r.review_date else '',
                'has_anomaly': bool(r.consumption_alert != 'normal' or r.image_state in ['not_clear', 'not_same', 'none', 'loss_read']),
                'vee_flags': vee_flags,
            })

        limit_val = limit if limit > 0 else 40
        pages_count = (total_count + limit_val - 1) // limit_val if total_count > 0 else 1
        current_page = (offset // limit_val) + 1 if limit_val > 0 else 1

        return {
            'items': items,
            'pagination': {
                'page': current_page,
                'page_size': limit_val,
                'total': total_count,
                'pages': pages_count,
                'offset': offset,
            },
            'stats': {
                'pending': pending_count,
                'approved': approved_count,
                'rejected': rejected_count,
                'exceptions': exceptions_count,
            }
        }

    @api.model
    def action_approve_review(self, reading_ids):
        """اعتماد قراءة أو مجموعة قراءات وتسجيل وقت واسم المراجع"""
        if not reading_ids:
            return {'status': 'error', 'message': _('لم يتم تحديد أي قراءة للإعتماد.')}

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids)])
        if not readings:
            raise ValidationError(_("القراءات المحددة غير موجودة."))

        # فحص الصلاحيات الجغرافية
        user = self.env.user
        if not (user.has_group('utility_core.group_utility_admin') or user.has_group('utility_core.group_utility_auditor')):
            if hasattr(user, 'utility_region_ids') and user.utility_region_ids:
                unauthorized = readings.filtered(lambda r: r.account_id and r.account_id.region_id and r.account_id.region_id not in user.utility_region_ids)
                if unauthorized:
                    raise AccessError(_("ليس لديك صلاحية مراجعة قراءات المنطقة: %s") % ", ".join(unauthorized.mapped('account_id.region_id.name')))

        valid_readings = readings.filtered(lambda r: r.state in ['under_review', 'draft'])
        if not valid_readings:
            return {'status': 'error', 'message': _('القراءات المحددة تم اعتمادها أو فوترتها سابقاً.')}

        valid_readings.sudo().write({
            'state': 'approved',
            'reviewer_id': user.id,
            'review_date': fields.Datetime.now(),
            'rejection_reason': False,
        })

        # تحديث قيمة آخر قراءة على العداد والحساب
        for r in valid_readings:
            if r.account_id:
                current_last = r.account_id.last_reading_date
                if not current_last or r.reading_date > current_last:
                    r.account_id.sudo().write({
                        'last_reading_date': r.reading_date,
                        'last_reading_value': r.reading_value,
                    })
            if r.meter_id:
                r.meter_id._update_last_reading()

        return {
            'status': 'success',
            'approved_ids': valid_readings.ids,
            'count': len(valid_readings)
        }

    @api.model
    def action_reject_review(self, reading_ids, rejection_reason=_('مرفوضة من قبل المراجع'), review_notes=''):
        """رفض قراءة أو مجموعة قراءات وتسجيل سبب الرفض المعتمد"""
        if not reading_ids:
            return {'status': 'error', 'message': _('لم يتم تحديد أي قراءة للرفض.')}

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids)])
        if not readings:
            raise ValidationError(_("القراءات المحددة غير موجودة."))

        user = self.env.user
        if not (user.has_group('utility_core.group_utility_admin') or user.has_group('utility_core.group_utility_auditor')):
            if hasattr(user, 'utility_region_ids') and user.utility_region_ids:
                unauthorized = readings.filtered(lambda r: r.account_id and r.account_id.region_id and r.account_id.region_id not in user.utility_region_ids)
                if unauthorized:
                    raise AccessError(_("ليس لديك صلاحية مراجعة قراءات المنطقة المحددة."))

        billed_readings = readings.filtered(lambda r: r.state == 'billed')
        if billed_readings:
            raise ValidationError(_("لا يمكن رفض قراءات مفوترة مباشرة (%s). يُرجى إلغاء الفاتورة أولاً.") % ", ".join(billed_readings.mapped('reading_id')))

        readings.sudo().write({
            'state': 'draft',
            'reviewer_id': user.id,
            'review_date': fields.Datetime.now(),
            'rejection_reason': rejection_reason,
            'review_notes': review_notes or False,
        })

        return {
            'status': 'success',
            'rejected_ids': readings.ids,
            'count': len(readings)
        }

    @api.model
    def action_bulk_approve_safe(self, reading_ids):
        """الاعتماد الجملي الآمن للقراءات المؤهلة خالياً من الشذوذ الحرج"""
        if not reading_ids:
            return {'status': 'error', 'message': _('لم يتم تحديد قراءات للاعتماد الجملي.')}

        readings = self.env['utility.reading'].search([('id', 'in', reading_ids), ('state', '=', 'under_review')])
        
        # تصفية القراءات السليمة التي ليس بها شذوذ مانع
        eligible = readings.filtered(lambda r: r.image_state not in ['not_clear', 'not_same', 'none', 'loss_read'] and r.consumption_alert != 'negative')
        
        if not eligible:
            return {'status': 'error', 'message': _('لا توجد قراءات مراجعة سليمة مؤهلة للاعتماد الجملي بدون مراجعة ثانوية.')}

        return self.action_approve_review(eligible.ids)

    @api.model
    def action_approve_replacement_pair(self, replacement_id):
        """اعتماد عملية استبدال العداد المزدوجة (القراءة الختامية + القراءة الافتتاحية) دفعة واحدة"""
        repl = self.env['utility.meter.replacement'].sudo().browse(replacement_id).exists()
        if not repl:
            raise ValidationError(_("عملية الاستبدال غير موجودة."))
        
        reading_ids = []
        if repl.closing_reading_id:
            reading_ids.append(repl.closing_reading_id.id)
        if repl.opening_reading_id:
            reading_ids.append(repl.opening_reading_id.id)
            
        if not reading_ids:
            return {'status': 'error', 'message': _('لا توجد قراءات مراجعة مسجلة لهذه العملية.')}
            
        res = self.action_approve_review(reading_ids)
        repl.write({'state': 'done'})
        return res
