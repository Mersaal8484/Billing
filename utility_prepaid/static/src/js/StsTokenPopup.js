/** @odoo-module **/

import AbstractAwaitablePopup from 'point_of_sale.AbstractAwaitablePopup';
import Registries from 'point_of_sale.Registries';
import { useState } from "@odoo/owl";

export class StsTokenPopup extends AbstractAwaitablePopup {
    setup() {
        super.setup();
        this.state = useState({
            selectedAccountId: this.props.accounts.length > 0 ? this.props.accounts[0].id : null,
            amount: 0,
            kwh: 0,
        });
    }

    get selectedAccount() {
        if (!this.state.selectedAccountId) return null;
        return this.props.accounts.find(a => a.id === parseInt(this.state.selectedAccountId));
    }

    getPayload() {
        const account = this.selectedAccount;
        return {
            accountId: account ? account.id : null,
            meterId: account && account.meter_id ? account.meter_id[0] : null,
            amount: parseFloat(this.state.amount),
            kwh: parseFloat(this.state.kwh),
        };
    }
}

StsTokenPopup.template = 'utility_prepaid.StsTokenPopup';
StsTokenPopup.defaultProps = {
    confirmText: 'إضافة',
    cancelText: 'إلغاء',
    title: 'بيع توكن جديد',
    accounts: [],
};

Registries.Component.add(StsTokenPopup);
