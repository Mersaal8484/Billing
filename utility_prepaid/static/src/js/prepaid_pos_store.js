/** @odoo-module **/

import { PosStore } from '@point_of_sale/app/store/pos_store';
import { patch } from '@web/core/utils/patch';
import { _t } from '@web/core/l10n/translation';

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.prepaidConfig = {};
        this.utilityAccounts = [];
        this.utilityMeters = [];
        this.prepaidVendingProduct = null;
    },

    async load_prepaid_data() {
        try {
            const [accounts, meters, products, config] = await Promise.all([
                this.orm.searchRead('utility.customer', [
                    ['payment_type', '=', 'prepaid'],
                    ['state', '=', 'active'],
                    ['company_id', '=', this.company.id],
                ], [
                    'id', 'customer_number', 'account_number', 'state',
                    'partner_id', 'meter_id', 'contract_template_id',
                    'payment_type', 'price_per_kwh', 'service_charge',
                    'accounting_balance',
                ], { limit: 10000 }),
                this.orm.searchRead('utility.meter', [
                    ['payment_type', '=', 'prepaid'],
                    ['company_id', '=', this.company.id],
                ], [
                    'id', 'meter_number', 'customer_id', 'payment_type',
                    'tariff_id', 'contract_template_id',
                ], { limit: 10000 }),
                this.orm.searchRead('product.product', [
                    ['default_code', '=', 'STS_TOKEN'],
                    ['available_in_pos', '=', true],
                    '|',
                    ['company_id', '=', this.company.id],
                    ['company_id', '=', false],
                ], [
                    'id', 'name', 'default_code', 'list_price', 'type',
                    'available_in_pos',
                ], { limit: 10 }),
                this.orm.call('utility.vending.policy', 'get_pos_config', []),
            ]);

            this.utilityAccounts = accounts;
            this.utilityMeters = meters;
            this.prepaidVendingProduct = products.length > 0 ? products[0] : null;
            this.prepaidConfig = config || {};

            return true;
        } catch (error) {
            console.error('Failed to load prepaid data:', error);
            return false;
        }
    },

    async search_accounts(query) {
        if (!query || query.length < 2) {
            return [];
        }
        try {
            const domain = [
                ['payment_type', '=', 'prepaid'],
                ['state', '=', 'active'],
                ['company_id', '=', this.company.id],
                '|', '|', '|',
                ['customer_number', 'ilike', query],
                ['partner_id.name', 'ilike', query],
                ['partner_id.phone', 'ilike', query],
                ['partner_id.mobile', 'ilike', query],
            ];
            const accounts = await this.orm.searchRead('utility.customer', domain, [
                'id', 'customer_number', 'account_number', 'state',
                'partner_id', 'meter_id', 'contract_template_id',
                'payment_type', 'price_per_kwh', 'service_charge',
                'accounting_balance',
            ], { limit: 50 });
            return accounts;
        } catch (error) {
            console.error('Account search failed:', error);
            return [];
        }
    },

    async search_meters_by_account(accountId) {
        if (!accountId) {
            return [];
        }
        try {
            const meters = await this.orm.searchRead('utility.meter', [
                ['customer_id', '=', accountId],
                ['payment_type', '=', 'prepaid'],
                ['company_id', '=', this.company.id],
            ], [
                'id', 'meter_number', 'customer_id', 'payment_type',
                'tariff_id', 'contract_template_id',
            ], { limit: 20 });
            return meters;
        } catch (error) {
            console.error('Meter search failed:', error);
            return [];
        }
    },

    async calculate_vending_quote(accountId, meterId, amount) {
        if (!accountId || !meterId || !amount || amount <= 0) {
            throw new Error(_t('بيانات الشحن غير مكتملة'));
        }
        try {
            const result = await this.orm.call('utility.vending.policy', 'calculate_quote_by_ids', [], {
                account_id: accountId,
                meter_id: meterId,
                gross_amount: amount,
            });
            return result;
        } catch (error) {
            console.error('Quote calculation failed:', error);
            throw error;
        }
    },

    async get_token_status(posOrderId) {
        if (!posOrderId) {
            return null;
        }
        try {
            const result = await this.orm.searchRead('utility.token', [
                ['pos_order_id', '=', posOrderId],
            ], [
                'id', 'token_number', 'status', 'kwh', 'amount',
                'response_message', 'delivery_state', 'mask_display',
            ], { limit: 1 });
            return result.length > 0 ? result[0] : null;
        } catch (error) {
            console.error('Token status fetch failed:', error);
            return null;
        }
    },

    async retry_token_generation(posOrderId) {
        if (!posOrderId) {
            return false;
        }
        try {
            await this.orm.call('pos.order', 'action_retry_token', [posOrderId]);
            return true;
        } catch (error) {
            console.error('Token retry failed:', error);
            return false;
        }
    },

    async resend_token_sms(tokenId) {
        if (!tokenId) {
            return false;
        }
        try {
            await this.orm.call('utility.token', 'action_resend_sms', [tokenId]);
            return true;
        } catch (error) {
            console.error('SMS resend failed:', error);
            return false;
        }
    },

    find_account_by_partner(partnerId) {
        if (!partnerId) {
            return [];
        }
        return this.utilityAccounts.filter(
            (acc) => acc.partner_id && acc.partner_id[0] === partnerId && acc.payment_type === 'prepaid'
        );
    },

    get_vending_product() {
        if (this.prepaidVendingProduct) {
            return this.prepaidVendingProduct;
        }
        const product = this.products.find(
            (p) => p.default_code === 'STS_TOKEN' || p.name.includes('شحن')
        );
        return product || null;
    },

    get_prepaid_config() {
        return this.prepaidConfig || {};
    },
});
