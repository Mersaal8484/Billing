/** @odoo-module **/

if (!odoo.__loaded_modules__) {
    odoo.__loaded_modules__ = {};
}
if (!odoo.__loaded_modules__["web_session_auto_close.session_monitor_v2"]) {
    odoo.__loaded_modules__["web_session_auto_close.session_monitor_v2"] = true;

    odoo.define("web_session_auto_close.session_monitor_v2", function (require) {
        "use strict";

        const rpc = require("web.rpc");
        const session = require("web.session");

        const SESSION_TIMEOUT_DEFAULT = 600 * 1000; // 10 دقائق

        let SESSION_TIMEOUT = SESSION_TIMEOUT_DEFAULT;
        let interval = null;

        async function initSessionAutoClose() {
            if (!session.uid) return;

            console.log("⏱️ بدء مراقبة الجلسة SessionAutoClose");

            try {
                const timeout = await rpc.query({
                    route: "/web/session/get_timeout",
                    params: {},
                });
                SESSION_TIMEOUT = parseInt(timeout, 10) || SESSION_TIMEOUT;
            } catch (error) {
                console.warn("❗فشل جلب إعداد الجلسة، سيتم استخدام القيمة الافتراضية", error);
            }

            updateActivityTime();
            window.addEventListener("mousemove", updateActivityTime);
            window.addEventListener("keydown", updateActivityTime);

            interval = setInterval(() => {
                checkInactivity();
            }, SESSION_TIMEOUT / 2);
        }

        function updateActivityTime() {
            localStorage.setItem("lastActivityTime", Date.now());
        }

        function getLastActivityTime() {
            return parseInt(localStorage.getItem("lastActivityTime"), 10) || Date.now();
        }

        async function logoutSession() {
            console.log("🔒 يتم تسجيل الخروج تلقائيًا بسبب عدم النشاط");
            try {
                await rpc.query({
                    route: "/web/session/destroy",
                    params: {},
                });
            } catch (e) {
                console.warn("خطأ في تسجيل الخروج:", e);
            } finally {
                localStorage.removeItem("lastActivityTime");
                window.location.href = "/web/login";
            }
        }

        function checkInactivity() {
            const now = Date.now();
            const last = getLastActivityTime();
          //  console.log("👀 آخر نشاط:", new Date(last).toISOString());

            if (now - last >= SESSION_TIMEOUT) {
                logoutSession();
            }
        }

        // بدء التشغيل
        initSessionAutoClose();
    });
}
