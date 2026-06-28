# -*- coding: utf-8 -*-
from odoo import models


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    def _prepare_all_journals(self):
        """حجز الأستاذ العام والبنك يكون لهما journals افتراضية عند التحميل"""
        journals = super()._prepare_all_journals()
        # Add a Purchase Journal specific for subcontractor invoices
        journals.append(self._prepare_journal_for_type('po_purchase_subcontractor'))
        return journals

    def _prepare_journal_for_type(self, journal_type):
        """إعداد journal إضافي"""
        self.ensure_one()
        if journal_type == 'po_purchase_subcontractor':
            return {
                'name': 'مشتريات مقاولي الباطن',
                'type': 'purchase',
                'code': 'JSUB',
                'sequence': 10,
                'default_account_id': False,
            }
        return {}
