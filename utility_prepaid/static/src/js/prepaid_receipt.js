/** @odoo-module **/

import { patch } from '@web/core/utils/patch';
import { OrderReceipt } from '@point_of_sale/app/screens/receipt_screen/receipt_screen';
import { _t } from '@web/core/l10n/translation';

patch(OrderReceipt.prototype, {
    get formattedVendingToken() {
        const order = this.props.order;
        if (!order || !order.is_prepaid_vending) {
            return null;
        }
        const token = order.token_number || order.utility_vending_quote?.token_number;
        if (!token) return null;
        const clean = token.replace(/\s/g, '');
        const groups = clean.match(/.{1,5}/g);
        return groups ? groups.join(' ') : clean;
    },

    get showPrepaidInfo() {
        const order = this.props.order;
        return order && order.is_prepaid_vending;
    },

    get vendingAccountNumber() {
        const order = this.props.order;
        if (!order) return '';
        if (order.utility_vending_quote && order.utility_vending_quote.account_number) {
            return order.utility_vending_quote.account_number;
        }
        if (order.utility_account_id) {
            const accounts = this.env.pos.utilityAccounts || [];
            const account = accounts.find((a) => a.id === order.utility_account_id);
            return account ? account.customer_number : '';
        }
        return '';
    },

    get vendingMeterNumber() {
        const order = this.props.order;
        if (!order) return '';
        if (order.utility_vending_quote && order.utility_vending_quote.meter_number) {
            return order.utility_vending_quote.meter_number;
        }
        if (order.utility_meter_id) {
            const meters = this.env.pos.utilityMeters || [];
            const meter = meters.find((m) => m.id === order.utility_meter_id);
            return meter ? meter.meter_number : '';
        }
        return '';
    },

    get vendingKwh() {
        const order = this.props.order;
        if (!order) return 0;
        return order.utility_vending_quote
            ? parseFloat(order.utility_vending_quote.kwh_purchased || 0).toFixed(3)
            : parseFloat(order.utility_kwh || 0).toFixed(3);
    },

    get vendingGrossAmount() {
        const order = this.props.order;
        if (!order) return 0;
        return order.utility_vending_quote
            ? parseFloat(order.utility_vending_quote.gross_amount || 0).toFixed(2)
            : parseFloat(order.utility_amount || 0).toFixed(2);
    },

    get vendingEnergyAmount() {
        const order = this.props.order;
        if (!order || !order.utility_vending_quote) return 0;
        return parseFloat(order.utility_vending_quote.energy_amount || 0).toFixed(2);
    },

    get vendingServiceCharge() {
        const order = this.props.order;
        if (!order || !order.utility_vending_quote) return 0;
        return parseFloat(order.utility_vending_quote.service_charge || 0).toFixed(2);
    },

    get vendingTaxAmount() {
        const order = this.props.order;
        if (!order || !order.utility_vending_quote) return 0;
        return parseFloat(order.utility_vending_quote.tax_amount || 0).toFixed(2);
    },

    get vendingDebtRecovery() {
        const order = this.props.order;
        if (!order || !order.utility_vending_quote) return 0;
        return parseFloat(order.utility_vending_quote.debt_recovery_amount || 0).toFixed(2);
    },
});
