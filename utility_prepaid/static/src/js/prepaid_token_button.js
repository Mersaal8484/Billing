/** @odoo-module **/

import { useService } from '@web/core/utils/hooks';
import { Component, useState } from '@odoo/owl';
import { patch } from '@web/core/utils/patch';
import { ProductScreen } from '@point_of_sale/app/screens/product_screen/product_screen';
import { PrepaidTokenPopup } from '@utility_prepaid/js/prepaid_token_popup';

export class PrepaidTokenButton extends Component {
    static template = 'utility_prepaid.PrepaidTokenButton';

    setup() {
        super.setup(...arguments);
        this.popup = useService('popup');
        this.pos = this.env.pos;
    }

    get currentOrder() {
        return this.pos.get_order();
    }

    get hasExistingLines() {
        return this.currentOrder && this.currentOrder.get_orderlines().length > 0;
    }

    async onClick() {
        const order = this.currentOrder;
        if (!order) {
            await this.popup.add('ErrorPopup', {
                title: _t('لا يوجد طلب'),
                body: _t('يرجى إنشاء طلب جديد أولاً.'),
            });
            return;
        }

        if (this.hasExistingLines) {
            await this.popup.add('ErrorPopup', {
                title: _t('طلب موجود'),
                body: _t('يوجد طلب حالي. أكمل الطلب الحالي أو ألغه قبل بدء شحن جديد.'),
            });
            return;
        }

        if (order.is_prepaid_vending) {
            await this.popup.add('ErrorPopup', {
                title: _t('شحن نشط'),
                body: _t('يوجد شحن مسبق الدفع قيد التنفيذ. أكمل الطلب الحالي أولاً.'),
            });
            return;
        }

        const partner = order.get_partner();
        if (!partner) {
            await this.popup.add('ErrorPopup', {
                title: _t('حدد العميل أولاً'),
                body: _t('يرجى اختيار العميل الذي تريد شحن عداده قبل بيع التوكن.'),
            });
            return;
        }

        const accounts = this.pos.find_account_by_partner(partner.id);
        if (!accounts.length) {
            await this.popup.add('ErrorPopup', {
                title: _t('لا يوجد حساب مسبق الدفع'),
                body: _t('العميل المحدد ليس لديه أي حسابات بعدادات مسبقة الدفع.'),
            });
            return;
        }

        const { confirmed, payload } = await this.popup.add(PrepaidTokenPopup, {
            accounts: accounts,
            partner: partner,
        });

        if (confirmed && payload) {
            await this._processVending(order, payload);
        }
    }

    async _processVending(order, payload) {
        const { accountId, meterId, amount, kwh, templateId, quote } = payload;

        if (!amount || amount <= 0) {
            await this.popup.add('ErrorPopup', {
                title: _t('مبلغ غير صحيح'),
                body: _t('يرجى إدخال مبلغ شحن صحيح أكبر من صفر.'),
            });
            return;
        }

        const product = this.pos.get_vending_product();
        if (!product) {
            await this.popup.add('ErrorPopup', {
                title: _t('لا يوجد منتج للتوكن'),
                body: _t('يرجى تعريف منتج (شحن رصيد أو STS_TOKEN) في النظام لبيع التوكن.'),
            });
            return;
        }

        const minAmount = this.pos.get_prepaid_config().minimum_vending_amount || 1;
        const maxAmount = this.pos.get_prepaid_config().maximum_vending_amount || 100000;
        if (amount < minAmount) {
            await this.popup.add('ErrorPopup', {
                title: _t('المبلغ أقل من الحد الأدنى'),
                body: _t('الحد الأدنى للشحن هو %s.', [minAmount]),
            });
            return;
        }
        if (amount > maxAmount) {
            await this.popup.add('ErrorPopup', {
                title: _t('المبلغ أعلى من الحد الأقصى'),
                body: _t('الحد الأقصى للشحن هو %s.', [maxAmount]),
            });
            return;
        }

        order.set_prepaid_metadata(accountId, meterId, amount, kwh, templateId, quote);

        order.add_product(product, {
            price: amount,
            quantity: 1,
        });

        const currentLine = order.get_selected_orderline();
        if (currentLine) {
            currentLine.is_prepaid_line = true;
            const acc = accounts.find((a) => a.id === accountId);
            const note = _t('شحن حساب: %s - %s ريال - %s kWh', [
                acc ? acc.customer_number : '',
                amount,
                kwh,
            ]);
            currentLine.set_customer_note(note);
        }
    }
}

ProductScreen.addControlButtons?.([{
    component: PrepaidTokenButton,
    condition: (comp) => {
        return true;
    },
}]);
