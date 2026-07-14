/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, onMounted, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

class UtilityDashboard extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            selectedRegionId: false,
            regions: [],
            kpi: {
                today_prepaid: 0,
                today_postpaid: 0,
                total_debt: 0,
                active_customers: 0,
                chart_labels: [],
                chart_invoices: [],
                chart_collections: [],
                region_rows: [],
                region_chart_labels: [],
                region_chart_customers: [],
                region_chart_debt: [],
            },
        });
        this.chartCanvasRef = useRef("chartCanvas");
        this.regionChartCanvasRef = useRef("regionChartCanvas");
        this.chart = null;
        this.regionChart = null;

        onWillStart(async () => {
            const regions = await this.orm.searchRead("utility.region", [["type", "=", "region"]], ["id", "name"], { order: "name" });
            this.state.regions = regions;
            await this.loadKPI(false);
            await loadJS("/web/static/lib/Chart/Chart.js");
        });

        onMounted(() => {
            this.renderChart();
            this.renderRegionChart();
        });
    }

    async loadKPI(regionId) {
        this.state.kpi = await this.rpc("/utility/dashboard/kpi", { region_id: regionId || false });
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
        if (this.regionChart) {
            this.regionChart.destroy();
            this.regionChart = null;
        }
        setTimeout(() => {
            this.renderChart();
            this.renderRegionChart();
        }, 100);
    }

    async onRegionChange(ev) {
        const regionId = ev.target.value ? parseInt(ev.target.value) : false;
        this.state.selectedRegionId = regionId;
        await this.loadKPI(regionId);
    }

    renderChart() {
        if (!this.chartCanvasRef.el) return;
        const ctx = this.chartCanvasRef.el.getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: this.state.kpi.chart_labels,
                datasets: [
                    {
                        label: '\u0627\u0644\u0641\u0648\u0627\u062a\u064a\u0631 \u0627\u0644\u0645\u0635\u062f\u0631\u0629',
                        data: this.state.kpi.chart_invoices,
                        backgroundColor: '#ff4d4d',
                    },
                    {
                        label: '\u0627\u0644\u062a\u062d\u0635\u064a\u0644\u0627\u062a',
                        data: this.state.kpi.chart_collections,
                        backgroundColor: '#28a745',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    yAxes: [{
                        ticks: { beginAtZero: true }
                    }]
                }
            }
        });
    }

    renderRegionChart() {
        if (!this.regionChartCanvasRef.el) return;
        const ctx = this.regionChartCanvasRef.el.getContext('2d');
        this.regionChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: this.state.kpi.region_chart_labels,
                datasets: [
                    {
                        label: '\u0627\u0644\u0645\u0634\u062a\u0631\u0643\u0648\u0646 \u0627\u0644\u0646\u0634\u0637\u0648\u0646',
                        data: this.state.kpi.region_chart_customers,
                        backgroundColor: '#007bff',
                    },
                    {
                        label: '\u0627\u0644\u0645\u062f\u064a\u0648\u0646\u064a\u0629 \u0627\u0644\u0645\u0641\u062a\u0648\u062d\u0629',
                        data: this.state.kpi.region_chart_debt,
                        backgroundColor: '#dc3545',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    yAxes: [{
                        ticks: { beginAtZero: true },
                    }],
                },
            },
        });
    }

    _regionDomain(regionId) {
        return regionId ? [['region_id', '=', regionId]] : [['region_id', '=', false]];
    }

    openCustomers(regionId = null) {
        const domain = [['state', '=', 'active']];
        if (regionId !== null) {
            domain.push(...this._regionDomain(regionId));
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: regionId === null ? '\u0627\u0644\u0639\u0645\u0644\u0627\u0621 \u0627\u0644\u0646\u0634\u0637\u064a\u0646' : '\u0645\u0634\u062a\u0631\u0643\u0648 \u0627\u0644\u0645\u0646\u0637\u0642\u0629',
            res_model: 'utility.customer',
            views: [[false, 'tree'], [false, 'form']],
            view_mode: 'tree,form',
            domain: domain,
            context: {'group_by': 'region_id'},
        });
    }

    openUnpaidInvoices(regionId = null) {
        const domain = [['move_type', '=', 'out_invoice'], ['state', '=', 'posted'], ['payment_state', 'in', ['not_paid', 'partial']]];
        if (regionId !== null) {
            const row = this.state.kpi.region_rows.find((item) => item.region_id === regionId);
            domain.push(['partner_id', 'in', row ? row.partner_ids : []]);
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: regionId === null ? '\u0627\u0644\u0641\u0648\u0627\u062a\u064a\u0631 \u0627\u0644\u0645\u0641\u062a\u0648\u062d\u0629' : '\u0641\u0648\u0627\u062a\u064a\u0631 \u0627\u0644\u0645\u0646\u0637\u0642\u0629 \u0627\u0644\u0645\u0641\u062a\u0648\u062d\u0629',
            res_model: 'account.move',
            views: [[false, 'tree'], [false, 'form']],
            view_mode: 'tree,form',
            domain: domain,
        });
    }
}

UtilityDashboard.template = "utility_dashboard.UtilityDashboard";
registry.category("actions").add("utility_dashboard_action", UtilityDashboard);
