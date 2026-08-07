/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class ReadingRejectionDialog extends Component {
    setup() {
        this.state = useState({
            reason: "الصورة غير واضحة / معتمة",
            customNotes: "",
        });
        this.rejectionReasons = [
            { id: "not_clear", label: _t("الصورة غير واضحة / معتمة") },
            { id: "not_same", label: _t("الصورة لا تطابق العداد المسجل") },
            { id: "incorrect_reading", label: _t("قيمة القراءة خاطئة / غير متسقة") },
            { id: "obstruction", label: _t("وجود عائق / انعكاس ضوئي على الشاشة") },
            { id: "duplicate", label: _t("صورة مكررة من قراءة سابقة") },
            { id: "suspected_tampering", label: _t("شبهة تلاعب / تعدي على العداد") },
            { id: "other", label: _t("سبب آخر (موضح بالملاحظات)") },
        ];
    }

    onConfirm() {
        this.props.onConfirm({
            reason: this.state.reason,
            notes: this.state.customNotes,
        });
    }

    onCancel() {
        this.props.onCancel();
    }
}
ReadingRejectionDialog.template = "utility_billing.ReadingRejectionDialog";
ReadingRejectionDialog.props = {
    reading: Object,
    onConfirm: Function,
    onCancel: Function,
};
