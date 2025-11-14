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
            filter_label: "",
        });

        this.filterPanelRef = useRef("filterPanel");
        this.productChartRef = useRef("productChart");
        this.projectExpenseChartRef = useRef("projectExpenseChart");
        this.customerChartRef = useRef("customerChart");
        // đặt key đồng nhất: product & projectExpense
        this._charts = {
            product: null,
            projectExpense: null,
            customer: null,
        };
        this._rendering = false;

        this.years = Array.from({ length: 10 }, (_, i) => 2022 + i);

        this._restoreFiltersFromStorage();

        onWillStart(async () => {
            await this.fetchData();
        });

        onMounted(() => {
            this._onClickOutside = this.onClickOutside.bind(this);
            document.addEventListener("click", this._onClickOutside);
            this.renderCharts();
        });

        onWillUnmount(() => {
            document.removeEventListener("click", this._onClickOutside);
            this._destroyCharts();
        });
    }
    _buildFilterLabel(data) {
        if (!data) {
            return "";
        }
        const { date_from, date_to, year, quarter } = data;

        const fmtDate = (s) => {
            if (!s) return "";
            const [y, m, d] = s.split("-");
            return `${d}/${m}/${y}`;
        };

        // 1️⃣ Nếu có quý + năm => ưu tiên hiển thị quý
        if (quarter && year) {
            return `Quý ${quarter.replace("Q", "")} / ${year}`;
        }

        // 2️⃣ Nếu chỉ có năm (không chọn quý) => hiển thị năm
        if (year && !(date_from && date_to)) {
            return `Năm ${year}`;
        }

        // 3️⃣ Nếu filter bằng khoảng ngày cụ thể
        if (date_from && date_to) {
            return `${fmtDate(date_from)} → ${fmtDate(date_to)}`;
        }

        return "Toàn bộ dữ liệu";
    }

    // -----------------------------
    // LocalStorage helpers
    // -----------------------------
    _restoreFiltersFromStorage() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
            if (saved) {
                Object.assign(this.state.filters, saved);
            }
        } catch (_) {
            // ignore
        }
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
            this.state.filter_label = this._buildFilterLabel(this.state.filters);
            this._saveFiltersToStorage();
            this.renderCharts();
        } catch (err) {
            console.error("Dashboard Error:", err);
            this.notification.add(
                _t("Không thể tải dữ liệu Dashboard."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    // -----------------------------
    // Chart Handling
    // -----------------------------
    _destroyCharts() {
        Object.keys(this._charts).forEach((k) => {
            if (this._charts[k]) {
                this._charts[k].destroy();
                this._charts[k] = null;
            }
        });
    }

    renderCharts() {
        if (this._rendering) {
            return;
        }
        this._rendering = true;
        this._destroyCharts();

        // ===== 1️⃣ Chart Top Sản phẩm (gộp báo giá + đơn hàng) =====
        const products = this.state.data?.top_products || [];
        if (window.Chart && this.productChartRef.el && products.length) {
            const labels = products.map((p) => p.name);
            const quantities = products.map((p) => p.doc_count || 0); // 🔁 dùng số đơn
            const values = products.map((p) => p.total_amount || 0);

            this._charts.product = new Chart(this.productChartRef.el, {
                type: "doughnut",
                data: {
                    labels,
                    datasets: [
                        {
                            label: _t("Giá trị"),
                            data: values,
                            backgroundColor: [
                                "rgba(37, 99, 235, 0.85)",
                                "rgba(16, 185, 129, 0.85)",
                                "rgba(234, 179, 8, 0.85)",
                                "rgba(239, 68, 68, 0.85)",
                                "rgba(139, 92, 246, 0.85)",
                            ],
                            borderWidth: 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "55%", // lỗ ở giữa cho nhẹ mắt
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                boxWidth: 12,
                                padding: 12,
                            },
                        },
                        tooltip: {
                            callbacks: {
                                // Tooltip: Giá trị + số lượng
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const amount = values[idx] || 0;
                                    const count = quantities[idx] || 0;
                                    const qty = quantities[idx] || 0;
                                    return [
                                        `${_t("Giá trị")}: ${fmtNum(amount)} ₫`,
                                        `${_t("Số đơn")}: ${fmtNum(count)}`,
                                    ];
                                },
                            },
                        },
                    },
                },
            });
        }
        // ===== 2️⃣ Chart Chi phí dự án =====
        const expenses = this.state.data?.project_expense || [];
        const MAX_LABEL_LEN = 40;

        if (window.Chart && this.projectExpenseChartRef?.el && expenses.length) {
            const fullLabels = expenses.map((e) => e.name || "");
            const labels = fullLabels.map((label) =>
                label.length > MAX_LABEL_LEN
                    ? label.slice(0, MAX_LABEL_LEN - 1) + "…"
                    : label
            );

            const spent = expenses.map((e) => e.spent || 0);
            const notSpent = expenses.map((e) => e.not_spent || 0);
            const total = expenses.map((e) => e.total || 0);

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
                            stack: "total",
                            borderRadius: 6,
                        },
                    ],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: {
                        padding: {
                            left: 16,
                            right: 16,
                            top: 8,
                            bottom: 16,
                        },
                    },
                    plugins: {
                        legend: { position: "bottom" },
                        tooltip: {
                            callbacks: {
                                title: (items) => {
                                    const idx = items[0].dataIndex;
                                    return fullLabels[idx] || "";
                                },
                                label: (ctx) =>
                                    `${ctx.dataset.label}: ${fmtNum(ctx.parsed.x)} ₫`,
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
                                autoSkip: false,
                                maxRotation: 0,
                                minRotation: 0,
                                padding: 6,
                            },
                        },
                    },
                },
            });
        }
        const customers = this.state.data?.top_customers || [];
        if (window.Chart && this.customerChartRef?.el && customers.length) {
            const labels = customers.map((c) => c.name);
            const quotationAmounts = customers.map((c) => c.quotation_amount || 0);
            const orderAmounts = customers.map((c) => c.order_amount || 0);
            const docCounts = customers.map((c) => c.total_docs || 0);

            this._charts.customer = new Chart(this.customerChartRef.el, {
                type: "bar",
                data: {
                    labels,
                    datasets: [
                        {
                            label: _t("Báo giá"),
                            data: quotationAmounts,
                            backgroundColor: "rgba(59, 130, 246, 0.85)",
                            stack: "amount",
                            borderRadius: 6,
                        },
                        {
                            label: _t("Đơn hàng"),
                            data: orderAmounts,
                            backgroundColor: "rgba(16, 185, 129, 0.85)",
                            stack: "amount",
                            borderRadius: 6,
                        },
                    ],
                },
                options: {
                    indexAxis: "y", // bar ngang
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom" },
                        tooltip: {
                            callbacks: {
                                label: (ctx) =>
                                    `${ctx.dataset.label}: ${fmtNum(ctx.parsed.x)} ₫`,
                                afterBody: (items) => {
                                    const idx = items[0].dataIndex;
                                    const total =
                                        (quotationAmounts[idx] || 0) +
                                        (orderAmounts[idx] || 0);
                                    const docs = docCounts[idx] || 0;
                                    return [
                                        `${_t("Tổng giá trị")}: ${fmtNum(total)} ₫`,
                                        `${_t("Số chứng từ")}: ${fmtNum(docs)}`,
                                    ];
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            ticks: {
                                callback: (v) => fmtNum(v) + " ₫",
                            },
                            grid: { color: "#f1f5f9" },
                        },
                        y: {
                            grid: { display: false },
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
            this.notification.add(
                _t("Ngày bắt đầu phải ≤ ngày kết thúc."),
                { type: "warning" }
            );
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
