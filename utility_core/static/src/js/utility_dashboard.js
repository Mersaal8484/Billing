/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, onMounted, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

class UtilityDashboard extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            kpi: {
                today_prepaid: 0,
                today_postpaid: 0,
                total_debt: 0,
                active_customers: 0,
                chart_labels: [],
                chart_invoices: [],
                chart_collections: [],
            },
        });
        this.chartCanvasRef = useRef("chartCanvas");

        onWillStart(async () => {
            // Fetch Dashboard KPIs
            this.state.kpi = await this.rpc("/utility/dashboard/kpi", {});
            // Load Chart.js if not already loaded (Odoo 16 usually has it globally, but we load it to be safe)
            await loadJS("/web/static/lib/Chart/Chart.js");
        });

        onMounted(() => {
            this.renderChart();
        });
    }

    renderChart() {
        if (!this.chartCanvasRef.el) return;
        const ctx = this.chartCanvasRef.el.getContext('2d');
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: this.state.kpi.chart_labels,
                datasets: [
                    {
                        label: 'الفواتير المصدرة',
                        data: this.state.kpi.chart_invoices,
                        backgroundColor: '#ff4d4d', // Red
                    },
                    {
                        label: 'التحصيلات',
                        data: this.state.kpi.chart_collections,
                        backgroundColor: '#28a745', // Green
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    yAxes: [{
                        ticks: {
                            beginAtZero: true
                        }
                    }]
                }
            }
        });
    }

    // Action Helpers
    openCustomers() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'العملاء النشطين',
            res_model: 'utility.customer',
            view_mode: 'tree,form',
            domain: [['state', '=', 'active']],
        });
    }

    openUnpaidInvoices() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'الفواتير المفتوحة',
            res_model: 'account.move',
            view_mode: 'tree,form',
            domain: [['move_type', '=', 'out_invoice'], ['state', '=', 'posted'], ['payment_state', 'in', ['not_paid', 'partial']]],
        });
    }
}

UtilityDashboard.template = "utility_dashboard.UtilityDashboard";
registry.category("actions").add("utility_dashboard_action", UtilityDashboard);
