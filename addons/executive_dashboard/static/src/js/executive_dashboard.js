/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = "executive_dashboard_filters_v1";
const fmtNum = (n) => Number(n || 0).toLocaleString("vi-VN");

class ExecutiveDashboard extends Component {
    static template = "executive_dashboard.Template";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        const today = new Date();
        this.state = useState({
            filters: {
                date_from: "",
                date_to: "",
                year: today.getFullYear(),
                quarter: "",
            },
            data: null,
            loading: false,
            showFilters: false,
        });

        this.filterPanelRef = useRef("filterPanel");
        this.productChartRef = useRef("productChart");
        this.projectExpenseChartRef = useRef("projectExpenseChart");
        this._charts = { product: null, project_expense: null };
        this._rendering = false;

        this.years = Array.from({ length: 10 }, (_, i) => 2022 + i);

        this._restoreFiltersFromStorage();

        onWillStart(async () => await this.fetchData());

        // ✅ Mount chart + register click outside listener
        onMounted(() => {
            this._onClickOutside = this.onClickOutside.bind(this);
            document.addEventListener("click", this._onClickOutside);
            this.renderCharts();
        });

        // ✅ Cleanup khi unmount
        onWillUnmount(() => {
            document.removeEventListener("click", this._onClickOutside);
            this._destroyCharts();
        });
    }

    // -----------------------------
    // LocalStorage helpers
    // -----------------------------
    _restoreFiltersFromStorage() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
            if (saved) Object.assign(this.state.filters, saved);
        } catch (_) { }
    }

    _saveFiltersToStorage() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state.filters));
    }

    // -----------------------------
    // Fetch data
    // -----------------------------
    async fetchData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "wt.executive.dashboard",
                "get_dashboard_data",
                [this.state.filters]
            );
            this.state.data = data;
            this._saveFiltersToStorage();
            this.renderCharts();
        } catch (err) {
            console.error("Dashboard Error:", err);
            this.notification.add(_t("Không thể tải dữ liệu Dashboard."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // -----------------------------
    // Chart Handling
    // -----------------------------
    _destroyCharts() {
        Object.values(this._charts).forEach((ch) => ch?.destroy());
        this._charts = {};
    }

    renderCharts() {
        if (this._rendering) return;
        this._rendering = true;
        this._destroyCharts();

        const products = this.state.data?.top_products || [];
        if (window.Chart && this.productChartRef.el && products.length) {
            const labels = products.map((p) => p.name);
            const quotations = products.map((p) => p.quotation_qty);
            const orders = products.map((p) => p.order_qty);

            this._charts.product = new Chart(this.productChartRef.el, {
                type: "bar",
                data: {
                    labels,
                    datasets: [
                        {
                            label: _t("Báo giá"),
                            data: quotations,
                            backgroundColor: "rgba(37, 99, 235, 0.7)",
                            borderRadius: 8,
                        },
                        {
                            label: _t("Đã bán"),
                            data: orders,
                            backgroundColor: "rgba(16, 185, 129, 0.7)",
                            borderRadius: 8,
                        },
                    ],
                },
                options: {
                    indexAxis: "y", // ✅ Thanh ngang
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom" },
                    },
                    scales: {
                        x: { beginAtZero: true, grid: { color: "#f1f5f9" } },
                        y: { grid: { display: false } },
                    },
                },
            });

        }
        const expenses = this.state.data?.project_expense || [];
        if (window.Chart && this.projectExpenseChartRef?.el && expenses.length) {
            const labels = expenses.map((e) => e.name);
            const spent = expenses.map((e) => e.spent);
            const notSpent = expenses.map((e) => e.not_spent);
            const total = expenses.map((e) => e.total);

            this._charts.projectExpense = new Chart(this.projectExpenseChartRef.el, {
                type: "bar",
                data: {
                    labels,
                    datasets: [
                        {
                            label: _t("Đã chi"),
                            data: spent,
                            backgroundColor: "rgba(37, 99, 235, 0.8)",
                            stack: "cost",
                            borderRadius: 6,
                        },
                        {
                            label: _t("Chưa chi"),
                            data: notSpent,
                            backgroundColor: "rgba(234, 179, 8, 0.8)",
                            stack: "cost",
                            borderRadius: 6,
                        },
                        {
                            label: _t("Tổng"),
                            data: total,
                            backgroundColor: "rgba(70, 177, 116, 0.8)",
                            stack: "total", // tách stack để hiển thị riêng
                            borderRadius: 6,
                        },
                    ],
                },
                options: {
                    indexAxis: "y", // ✅ đây chính là phần khiến biểu đồ nằm ngang
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom" },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.dataset.label}: ${fmtNum(ctx.parsed.x)} ₫`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            ticks: { callback: (v) => fmtNum(v) + " ₫" },
                            title: { display: true, text: _t("Chi phí (VND)") },
                            grid: { color: "#f1f5f9" },
                        },
                        y: {
                            grid: { display: false },
                            ticks: {
                                font: { size: 12 },
                                autoSkip: false,        // Không bỏ qua label nào
                                maxRotation: 0,         // Giữ ngang
                                minRotation: 0,
                                padding: 6,             // Tăng khoảng cách giữa các dòng
                            },
                        },
                    },
                },
            });
        }

        this._rendering = false;
    }

    // -----------------------------
    // Filter Handlers
    // -----------------------------
    onChangeDate() {
        this.state.filters.year = "";
        this.state.filters.quarter = "";
    }

    onChangeYear() {
        this.state.filters.date_from = "";
        this.state.filters.date_to = "";
        this.state.filters.quarter = "";
    }

    onChangeQuarter() {
        this.state.filters.date_from = "";
        this.state.filters.date_to = "";
    }

    applyFilters() {
        const { date_from, date_to } = this.state.filters;
        if (date_from && date_to && date_from > date_to) {
            this.notification.add(_t("Ngày bắt đầu phải ≤ ngày kết thúc."), { type: "warning" });
            return;
        }
        this.fetchData();
        this.toggleFilters();
    }

    resetFilters() {
        const today = new Date();
        this.state.filters = {
            date_from: "",
            date_to: "",
            year: today.getFullYear(),
            quarter: "",
        };
        this.fetchData();
    }

    toggleFilters() {
        this.state.showFilters = !this.state.showFilters;
    }

    // -----------------------------
    // Click outside handler
    // -----------------------------
    onClickOutside(ev) {
        const panel = this.filterPanelRef.el;
        const button = document.querySelector(".ed-filter-fab");
        if (
            this.state.showFilters &&
            panel &&
            !panel.contains(ev.target) &&
            (!button || !button.contains(ev.target))
        ) {
            this.state.showFilters = false;
        }
    }
}

registry.category("actions").add("executive_dashboard", ExecutiveDashboard);
export default ExecutiveDashboard;
