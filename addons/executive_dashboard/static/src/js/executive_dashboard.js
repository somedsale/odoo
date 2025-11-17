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
        this.action = useService("action");

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
        this.invoiceChartRef = useRef("invoiceChart");

        this._charts = {
            product: null,
            projectExpense: null,
            customer: null,
            invoice: null,
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

    // =========================
    // Filter label
    // =========================
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

        if (quarter && year) {
            return `Quý ${quarter.replace("Q", "")} / ${year}`;
        }
        if (year && !(date_from && date_to)) {
            return `Năm ${year}`;
        }
        if (date_from && date_to) {
            return `${fmtDate(date_from)} → ${fmtDate(date_to)}`;
        }
        return "Toàn bộ dữ liệu";
    }

    // =========================
    // LocalStorage helpers
    // =========================
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

    // =========================
    // Fetch data
    // =========================
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

    // =========================
    // Chart Handling
    // =========================
    _destroyCharts() {
        Object.keys(this._charts).forEach((k) => {
            if (this._charts[k]) {
                this._charts[k].destroy();
                this._charts[k] = null;
            }
        });
    }

    openOrdersByIds(orderIds) {
        if (!orderIds || !orderIds.length) {
            this.notification.add(_t("Không tìm thấy đơn hàng liên quan."), {
                type: "warning",
            });
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Đơn hàng liên quan"),
            res_model: "sale.order",
            view_mode: "tree,form",
            views: [
                [false, "tree"],
                [false, "form"],
            ],
            target: "current",
            domain: [["id", "in", orderIds]],
        });
    }

    renderCharts() {
        if (this._rendering || !this.state.data) {
            return;
        }
        this._rendering = true;
        this._destroyCharts();

        // ===== 1️⃣ Chart Top Sản phẩm (gộp báo giá + đơn hàng) =====
        const products = this.state.data.top_products || [];
        if (window.Chart && this.productChartRef.el && products.length) {
            const labels = products.map((p) => p.name);
            const quantities = products.map((p) => p.doc_count || 0);
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
                    cutout: "55%",
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
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const amount = values[idx] || 0;
                                    const count = quantities[idx] || 0;
                                    return [
                                        `${_t("Giá trị")}: ${fmtNum(amount)} ₫`,
                                        `${_t("Số đơn")}: ${fmtNum(count)}`,
                                    ];
                                },
                            },
                        },
                    },
                    // click vào slice => mở các đơn của sản phẩm đó
                    onClick: (evt, elements) => {
                        if (!elements || !elements.length) {
                            return;
                        }
                        const index = elements[0].index;
                        const product = products[index];
                        const orderIds = product.order_ids || [];
                        this.openOrdersByIds(orderIds);
                    },
                },
            });
        }

        // ===== 2️⃣ Chart Chi phí dự án =====
        const expenses = this.state.data.project_expense || [];
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

        // ===== 3️⃣ Chart Top khách hàng =====
        const customers = this.state.data.top_customers || [];
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
                    indexAxis: "y",
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
                    // click vào bar => mở các đơn của khách hàng đó
                    onClick: (evt, elements) => {
                        if (!elements || !elements.length) {
                            return;
                        }
                        const index = elements[0].index;
                        const customer = customers[index];
                        const orderIds = customer.order_ids || [];
                        this.openOrdersByIds(orderIds);
                    },
                },
            });
        }

        // ===== 4️⃣ Chart Hóa đơn vào / ra =====
        const invoice = this.state.data.invoice_overview;
        if (window.Chart && this.invoiceChartRef?.el && invoice) {
            const labels = [_t("Hóa đơn đầu vào"), _t("Hóa đơn đầu ra")];
            const amounts = [
                invoice.supplier_total || 0,
                invoice.customer_total || 0,
            ];
            const counts = [
                invoice.supplier_count || 0,
                invoice.customer_count || 0,
            ];

            this._charts.invoice = new Chart(this.invoiceChartRef.el, {
                type: "pie",
                data: {
                    labels,
                    datasets: [
                        {
                            data: amounts,
                            backgroundColor: [
                                "rgba(239, 68, 68, 0.9)",   // Đầu vào
                                "rgba(34, 197, 94, 0.9)",  // Đầu ra
                            ],
                            borderWidth: 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                boxWidth: 14,
                                padding: 12,
                            },
                        },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const amount = amounts[idx] || 0;
                                    const count = counts[idx] || 0;
                                    return [
                                        `${ctx.label}: ${fmtNum(amount)} ₫`,
                                        `${_t("Số hóa đơn")}: ${fmtNum(count)}`,
                                    ];
                                },
                            },
                        },
                    },
                    onClick: (evt, elements) => {
                        if (!elements || !elements.length) {
                            return;
                        }
                        const index = elements[0].index;
                        if (index === 0) {
                            this.openSupplierInvoices();
                        } else if (index === 1) {
                            this.openCustomerInvoices();
                        }
                    },
                },
            });
        }

        this._rendering = false;
    }

    // =========================
    // Filter Handlers
    // =========================
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

    // =========================
    // Click outside handler
    // =========================
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

    // =========================
    // Common date domain helper
    // =========================
    _getDateDomain(fieldName) {
        const { date_from, date_to, year, quarter } = this.state.filters;
        const domain = [];

        let from = date_from;
        let to = date_to;

        // Nếu chưa chọn khoảng ngày cụ thể nhưng có chọn Năm / Quý
        if (!from && !to && year) {
            const y = parseInt(year, 10);
            if (Number.isFinite(y)) {
                let startMonth = 1;
                let endMonth = 12;

                // Map Quý -> khoảng tháng
                if (quarter) {
                    switch (quarter) {
                        case "Q1":
                            startMonth = 1;
                            endMonth = 3;
                            break;
                        case "Q2":
                            startMonth = 4;
                            endMonth = 6;
                            break;
                        case "Q3":
                            startMonth = 7;
                            endMonth = 9;
                            break;
                        case "Q4":
                            startMonth = 10;
                            endMonth = 12;
                            break;
                    }
                }

                const pad = (n) => String(n).padStart(2, "0");
                // new Date(y, month, 0) -> ngày cuối cùng của tháng (month là 1–12)
                const lastDay = new Date(y, endMonth, 0).getDate();

                from = `${y}-${pad(startMonth)}-01`;
                to = `${y}-${pad(endMonth)}-${pad(lastDay)}`;
            }
        }

        if (from) {
            domain.push([fieldName, ">=", from]);
        }
        if (to) {
            domain.push([fieldName, "<=", to]);
        }

        return domain;
    }

    // =========================
    // KPI click actions
    // =========================
    openQuotations() {
        const domain = this._getDateDomain("create_date");
        domain.push(["state", "in", ["draft", "sent"]]);

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Báo giá"),
            res_model: "sale.order",
            view_mode: "tree,form",
            views: [
                [false, "tree"],
                [false, "form"],
            ],
            target: "current",
            domain,
        });
    }

    openOrders() {
        const domain = this._getDateDomain("create_date");
        domain.push(["state", "in", ["sale", "done"]]);

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Đơn hàng"),
            res_model: "sale.order",
            view_mode: "tree,form",
            views: [
                [false, "tree"],
                [false, "form"],
            ],
            target: "current",
            domain,
        });
    }

    openCashIn() {
        const domain = this._getDateDomain("date");
        domain.push(["state", "in", ["posted"]]);

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Phiếu thu"),
            res_model: "account.receipt",
            view_mode: "tree,form",
            views: [
                [false, "tree"],
                [false, "form"],
            ],
            target: "current",
            domain,
        });
    }

    openCashOut() {
        const domain = this._getDateDomain("date_payment");
        domain.push(["status_expense", "in", ["paid"]]);

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Phiếu chi / ĐNTT"),
            res_model: "account.payment.request",
            view_mode: "tree,form",
            views: [
                [false, "tree"],
                [false, "form"],
            ],
            target: "current",
            domain,
        });
    }

    openSupplierInvoices() {
        const domain = this._getDateDomain("date");

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Hóa đơn đầu vào"),
            res_model: "supplier.invoice",
            view_mode: "tree,form",
            views: [
                [false, "tree"],
                [false, "form"],
            ],
            target: "current",
            domain,
        });
    }

    openCustomerInvoices() {
        const domain = this._getDateDomain("date");

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Hóa đơn đầu ra"),
            res_model: "customer.invoice",
            view_mode: "tree,form",
            views: [
                [false, "tree"],
                [false, "form"],
            ],
            target: "current",
            domain,
        });
    }
}

registry.category("actions").add("executive_dashboard", ExecutiveDashboard);
export default ExecutiveDashboard;
