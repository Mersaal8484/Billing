/** @odoo-module **/

import { AbstractAwaitablePopup } from '@point_of_sale/app/store/abstract_awittable_popup';
import { useState, onMounted, onWillUnmount } from '@odoo/owl';
import { _t } from '@web/core/l10n/translation';

export class PrepaidStatusPopup extends AbstractAwaitablePopup {
    static template = 'utility_prepaid.PrepaidStatusPopup';
    static defaultProps = {
        title: _t('حالة التوكن'),
        posOrderId: null,
        closeText: _t('إغلاق'),
    };

    setup() {
        super.setup(...arguments);
        this.state = useState({
            token: null,
            loading: true,
            error: null,
            lastChecked: null,
        });

        this._refreshInterval = null;

        onMounted(async () => {
            await this._fetchTokenStatus();
            if (this.state.token && this.state.token.status === 'pending') {
                this._startAutoRefresh();
            }
        });

        onWillUnmount(() => {
            this._stopAutoRefresh();
        });
    }

    async _fetchTokenStatus() {
        this.state.loading = true;
        this.state.error = null;

        try {
            const token = await this.env.pos.get_token_status(this.props.posOrderId);
            this.state.token = token;
            this.state.lastChecked = new Date();
        } catch (error) {
            this.state.error = _t('فشل جلب حالة التوكن');
        } finally {
            this.state.loading = false;
        }
    }

    async refreshStatus() {
        await this._fetchTokenStatus();
        if (this.state.token && this.state.token.status === 'pending') {
            this._startAutoRefresh();
        } else {
            this._stopAutoRefresh();
        }
    }

    _startAutoRefresh() {
        this._stopAutoRefresh();
        this._refreshInterval = setInterval(async () => {
            await this._fetchTokenStatus();
            if (!this.state.token || this.state.token.status !== 'pending') {
                this._stopAutoRefresh();
            }
        }, 5000);
    }

    _stopAutoRefresh() {
        if (this._refreshInterval) {
            clearInterval(this._refreshInterval);
            this._refreshInterval = null;
        }
    }

    async retryToken() {
        this.state.loading = true;
        this.state.error = null;

        try {
            const success = await this.env.pos.retry_token_generation(this.props.posOrderId);
            if (success) {
                await this._fetchTokenStatus();
                if (this.state.token && this.state.token.status === 'pending') {
                    this._startAutoRefresh();
                }
            } else {
                this.state.error = _t('فشلت إعادة محاولة توليد التوكن');
            }
        } catch (error) {
            this.state.error = _t('فشلت إعادة محاولة توليد التوكن');
        } finally {
            this.state.loading = false;
        }
    }

    async resendSMS() {
        if (!this.state.token || !this.state.token.id) {
            return;
        }

        try {
            const success = await this.env.pos.resend_token_sms(this.state.token.id);
            if (success) {
                await this.showPopup('InfoPopup', {
                    title: _t('تم'),
                    body: _t('تم إعادة إرسال رمز الشحن عبر SMS بنجاح.'),
                });
            }
        } catch (error) {
            await this.showPopup('ErrorPopup', {
                title: _t('خطأ'),
                body: error.message || _t('فشل إعادة إرسال SMS.'),
            });
        }
    }

    async printReceipt() {
        if (!this.state.token) {
            return;
        }
        this.env.pos.printReceipt();
    }

    get statusClass() {
        if (!this.state.token) return '';
        switch (this.state.token.status) {
            case 'success':
                return 'status-success';
            case 'failed':
                return 'status-failed';
            case 'pending':
                return 'status-pending';
            case 'cancelled':
                return 'status-cancelled';
            default:
                return '';
        }
    }

    get statusLabel() {
        if (!this.state.token) return '';
        switch (this.state.token.status) {
            case 'success':
                return _t('تم التوليد بنجاح');
            case 'failed':
                return _t('فشل التوليد');
            case 'pending':
                return _t('قيد الانتظار');
            case 'cancelled':
                return _t('ملغي');
            default:
                return this.state.token.status;
        }
    }

    get formattedTokenNumber() {
        if (!this.state.token || !this.state.token.token_number) return '';
        const token = this.state.token.mask_display || this.state.token.token_number;
        const clean = token.replace(/\s/g, '');
        const groups = clean.match(/.{1,5}/g);
        return groups ? groups.join(' ') : clean;
    }

    get displayKwh() {
        if (!this.state.token) return '0';
        return parseFloat(this.state.token.kwh || 0).toFixed(3);
    }

    get displayAmount() {
        if (!this.state.token) return '0';
        return parseFloat(this.state.token.amount || 0).toFixed(2);
    }

    get secondsSinceCheck() {
        if (!this.state.lastChecked) return 0;
        return Math.floor((Date.now() - this.state.lastChecked.getTime()) / 1000);
    }
}
