/** @odoo-module **/

import { AbstractAwaitablePopup } from '@point_of_sale/app/store/abstract_awittable_popup';
import { useState, onWillStart } from '@odoo/owl';
import { _t } from '@web/core/l10n/translation';

export class PrepaidTokenPopup extends AbstractAwaitablePopup {
    static template = 'utility_prepaid.PrepaidTokenPopup';
    static defaultProps = {
        confirmText: _t('تأكيد الشحن'),
        cancelText: _t('إلغاء'),
        title: _t('شحن توكن مسبق الدفع'),
        accounts: [],
        partner: null,
    };

    setup() {
        super.setup(...arguments);
        this.state = useState({
            step: 1,
            searchQuery: '',
            searchResults: [],
            searching: false,
            selectedAccount: null,
            selectedMeter: null,
            meters: [],
            amount: '',
            quote: null,
            calculating: false,
            error: null,
        });

        this._searchTimeout = null;

        onWillStart(async () => {
            if (this.props.accounts.length > 0) {
                this.state.selectedAccount = this.props.accounts[0];
                this.state.step = 2;
                await this._loadMeters(this.state.selectedAccount.id);
            }
        });
    }

    get hasValidSelection() {
        switch (this.state.step) {
            case 1:
                return this.state.searchResults.length > 0;
            case 2:
                return this.state.selectedAccount && this.state.selectedMeter;
            case 3:
                const amount = parseFloat(this.state.amount);
                return amount > 0;
            case 4:
                return this.state.quote !== null;
            default:
                return false;
        }
    }

    async onSearchInput(ev) {
        const query = ev.target.value;
        this.state.searchQuery = query;
        this.state.error = null;

        if (this._searchTimeout) {
            clearTimeout(this._searchTimeout);
        }

        if (!query || query.length < 2) {
            this.state.searchResults = [];
            return;
        }

        this.state.searching = true;
        this._searchTimeout = setTimeout(async () => {
            try {
                const results = await this.env.pos.search_accounts(query);
                this.state.searchResults = results;
            } catch (error) {
                this.state.error = _t('فشل البحث عن الحسابات');
            } finally {
                this.state.searching = false;
            }
        }, 300);
    }

    async selectAccountFromSearch(account) {
        this.state.selectedAccount = account;
        this.state.step = 2;
        this.state.error = null;
        await this._loadMeters(account.id);
    }

    async _loadMeters(accountId) {
        try {
            const meters = await this.env.pos.search_meters_by_account(accountId);
            this.state.meters = meters;
            if (meters.length === 1) {
                this.state.selectedMeter = meters[0];
                this.state.step = 3;
            } else if (meters.length > 1) {
                this.state.selectedMeter = null;
            }
        } catch (error) {
            this.state.error = _t('فشل تحميل العدادات');
        }
    }

    selectMeter(meter) {
        this.state.selectedMeter = meter;
        this.state.step = 3;
        this.state.error = null;
    }

    onAmountInput(ev) {
        this.state.amount = ev.target.value;
        this.state.error = null;
    }

    onAmountNumpad(ev) {
        const value = ev.detail.value;
        this.state.amount = (this.state.amount || '') + value;
        this.state.error = null;
    }

    async calculateQuote() {
        const amount = parseFloat(this.state.amount);
        if (!amount || amount <= 0) {
            this.state.error = _t('يرجى إدخال مبلغ صحيح');
            return;
        }

        const config = this.env.pos.get_prepaid_config();
        const minAmount = config.minimum_vending_amount || 1;
        const maxAmount = config.maximum_vending_amount || 100000;
        if (amount < minAmount) {
            this.state.error = _t('الحد الأدنى للشحن هو %s', [minAmount]);
            return;
        }
        if (amount > maxAmount) {
            this.state.error = _t('الحد الأقصى للشحن هو %s', [maxAmount]);
            return;
        }

        this.state.calculating = true;
        this.state.error = null;

        try {
            const quote = await this.env.pos.calculate_vending_quote(
                this.state.selectedAccount.id,
                this.state.selectedMeter.id,
                amount
            );
            this.state.quote = quote;
            this.state.step = 4;
        } catch (error) {
            this.state.error = error.message || _t('فشل حساب عرض السعر');
        } finally {
            this.state.calculating = false;
        }
    }

    goBack() {
        if (this.state.step > 1) {
            this.state.step--;
            this.state.error = null;
        }
    }

    confirm() {
        if (this.state.step === 4 && this.state.quote) {
            const payload = {
                accountId: this.state.selectedAccount.id,
                meterId: this.state.selectedMeter.id,
                amount: this.state.quote.gross_amount || parseFloat(this.state.amount),
                kwh: this.state.quote.kwh_purchased || 0,
                templateId: this.state.selectedAccount.contract_template_id
                    ? this.state.selectedAccount.contract_template_id[0]
                    : false,
                quote: this.state.quote,
            };
            super.confirm(payload);
        }
    }

    formatTokenNumber(token) {
        if (!token) return '';
        const clean = token.replace(/\s/g, '');
        const groups = clean.match(/.{1,5}/g);
        return groups ? groups.join(' ') : clean;
    }

    formatNumber(num, decimals = 2) {
        if (num === null || num === undefined) return '0';
        return parseFloat(num).toFixed(decimals);
    }
}
