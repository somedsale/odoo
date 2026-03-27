/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = "executive_dashboard_filters_v3";

const fmtNum = (n) => Number(n || 0).toLocaleString("vi-VN");
const fmtMoney = (n) => `${fmtNum(n)} ₫`;

export class ExecutiveDashboard extends Component {
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
        this.customerChartRef = useRef("customerChart");
        this.projectExpenseChartRef = useRef("projectExpenseChart");
        this.invoiceChartRef = useRef("invoiceChart");

        this._charts = {
            product: null,
            customer: null,
            projectExpense: null,
            invoice: null,
        };

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
    // Helpers
    // =========================
    _buildFilterLabel(data) {
        if (!data) return "";
        const { date_from, date_to, year, quarter } = data;

        const fmtDate = (s) => {
            if (!s) return "";
            const [y, m, d] = s.split("-");
            return `${d}/${m}/${y}`;
        };

        if (quarter && year) {
            return `Kỳ báo cáo: Quý ${quarter.replace("Q", "")} / ${year}`;
        }
        if (year && !(date_from && date_to)) {
            return `Kỳ báo cáo: Năm ${year}`;
        }
        if (date_from && date_to) {
            return `Kỳ báo cáo: ${fmtDate(date_from)} → ${fmtDate(date_to)}`;
        }
        return "Kỳ báo cáo: Toàn bộ dữ liệu";
    }

    _restoreFiltersFromStorage() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
            if (saved) {
                Object.assign(this.state.filters, saved);
            }
        } catch (_) { }
    }

    _saveFiltersToStorage() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state.filters));
    }

    _destroyCharts() {
        for (const key of Object.keys(this._charts)) {
            if (this._charts[key]) {
                this._charts[key].destroy();
                this._charts[key] = null;
            }
        }
    }

    _truncateLabel(text, max = 26) {
        const val = text || "";
        return val.length > max ? `${val.slice(0, max - 1)}…` : val;
    }

    async fetchData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "wt.executive.dashboard",
                "get_dashboard_data",
                [this.state.filters]
            );
            this.state.data = data;
            this.state.filter_label = this._buildFilterLabel(data || this.state.filters);
            this._saveFiltersToStorage();

            setTimeout(() => this.renderCharts(), 0);
        } catch (err) {
            console.error("Executive Dashboard Error:", err);
            this.notification.add(_t("Không thể tải dữ liệu bảng điều hành."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    // =========================
    // Actions
    // =========================
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
            views: [[false, "tree"], [false, "form"]],
            target: "current",
            domain: [["id", "in", orderIds]],
        });
    }

    openProject(projectId) {
        if (!projectId) {
            this.notification.add(_t("Không tìm thấy dự án liên quan."), {
                type: "warning",
            });
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Dự án"),
            res_model: "project.project",
            res_id: projectId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTopOrder() {
        const topOrder = this.state.data?.top_order;
        if (!topOrder?.id) {
            this.notification.add(_t("Không có đơn hàng nổi bật trong kỳ này."), {
                type: "warning",
            });
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Đơn hàng lớn nhất"),
            res_model: "sale.order",
            res_id: topOrder.id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    _getDateDomain(fieldName) {
        const { date_from, date_to, year, quarter } = this.state.filters;
        const domain = [];

        let from = date_from;
        let to = date_to;

        if (!from && !to && year) {
            const y = parseInt(year, 10);
            let startMonth = 1;
            let endMonth = 12;

            if (quarter === "Q1") {
                startMonth = 1;
                endMonth = 3;
            } else if (quarter === "Q2") {
                startMonth = 4;
                endMonth = 6;
            } else if (quarter === "Q3") {
                startMonth = 7;
                endMonth = 9;
            } else if (quarter === "Q4") {
                startMonth = 10;
                endMonth = 12;
            }

            const pad = (n) => String(n).padStart(2, "0");
            const lastDay = new Date(y, endMonth, 0).getDate();

            from = `${y}-${pad(startMonth)}-01`;
            to = `${y}-${pad(endMonth)}-${pad(lastDay)}`;
        }

        if (from) domain.push([fieldName, ">=", from]);
        if (to) domain.push([fieldName, "<=", to]);

        return domain;
    }

    openQuotations() {
        const domain = this._getDateDomain("create_date");
        domain.push(["state", "in", ["draft", "sent"]]);

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Báo giá"),
            res_model: "sale.order",
            view_mode: "tree,form",
            views: [[false, "tree"], [false, "form"]],
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
            views: [[false, "tree"], [false, "form"]],
            target: "current",
            domain,
        });
    }

    openCashIn() {
        const domain = this._getDateDomain("date");
        domain.push(["state", "=", "posted"]);

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Phiếu thu"),
            res_model: "account.receipt",
            view_mode: "tree,form",
            views: [[false, "tree"], [false, "form"]],
            target: "current",
            domain,
        });
    }

    openCashOut() {
        const domain = this._getDateDomain("date_payment");
        domain.push(["status_expense", "=", "paid"]);

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Phiếu chi"),
            res_model: "account.payment.request",
            view_mode: "tree,form",
            views: [[false, "tree"], [false, "form"]],
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
            views: [[false, "tree"], [false, "form"]],
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
            views: [[false, "tree"], [false, "form"]],
            target: "current",
            domain,
        });
    }

    // =========================
    // Filters
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

    async applyFilters() {
        const { date_from, date_to } = this.state.filters;
        if (date_from && date_to && date_from > date_to) {
            this.notification.add(_t("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc."), {
                type: "warning",
            });
            return;
        }
        await this.fetchData();
        this.toggleFilters();
    }

    async resetFilters() {
        const today = new Date();
        Object.assign(this.state.filters, {
            date_from: "",
            date_to: "",
            year: today.getFullYear(),
            quarter: "",
        });
        await this.fetchData();
    }

    toggleFilters() {
        this.state.showFilters = !this.state.showFilters;
    }

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
    // Charts
    // =========================
    renderCharts() {
        if (!this.state.data || !window.Chart) {
            return;
        }

        this._destroyCharts();

        // ===== 1. Top khách hàng =====
        const customers = this.state.data.top_customers || [];
        if (this.customerChartRef.el && customers.length) {
            this._charts.customer = new Chart(this.customerChartRef.el, {
                type: "bar",
                data: {
                    labels: customers.map((c) => this._truncateLabel(c.name, 24)),
                    datasets: [
                        {
                            label: _t("Báo giá"),
                            data: customers.map((c) => c.quotation_amount || 0),
                            backgroundColor: "#cbd5e1",
                            borderColor: "#111827",
                            borderWidth: 2,
                            borderRadius: 0,
                        },
                        {
                            label: _t("Đơn hàng"),
                            data: customers.map((c) => c.order_amount || 0),
                            backgroundColor: "#2563eb",
                            borderColor: "#111827",
                            borderWidth: 2,
                            borderRadius: 0,
                        },
                    ],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                color: "#111827",
                                font: { size: 12, weight: "700" },
                            },
                        },
                        tooltip: {
                            callbacks: {
                                title: (items) => customers[items[0].dataIndex]?.name || "",
                                afterBody: (items) => {
                                    const item = customers[items[0].dataIndex];
                                    return [
                                        `${_t("Tổng chứng từ")}: ${fmtNum(item.total_docs)}`,
                                        `${_t("Tổng giá trị")}: ${fmtMoney(item.total_amount)}`,
                                    ];
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            ticks: {
                                callback: (v) => fmtNum(v),
                                color: "#111827",
                            },
                            grid: { color: "#d1d5db" },
                            border: { color: "#111827", width: 2 },
                        },
                        y: {
                            ticks: { color: "#111827", font: { size: 12, weight: "700" } },
                            grid: { display: false },
                            border: { color: "#111827", width: 2 },
                        },
                    },
                    onClick: (evt, elements) => {
                        if (!elements?.length) return;
                        const item = customers[elements[0].index];
                        this.openOrdersByIds(item.order_ids || []);
                    },
                },
            });
        }

        // ===== 2. Top sản phẩm =====
        const products = this.state.data.top_products || [];
        if (this.productChartRef.el && products.length) {
            this._charts.product = new Chart(this.productChartRef.el, {
                type: "bar",
                data: {
                    labels: products.map((p) => this._truncateLabel(p.name, 24)),
                    datasets: [{
                        label: _t("Giá trị"),
                        data: products.map((p) => p.total_amount || 0),
                        backgroundColor: "#facc15",
                        borderColor: "#111827",
                        borderWidth: 2,
                        borderRadius: 0,
                        maxBarThickness: 34,
                    }],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false,
                        },
                        tooltip: {
                            callbacks: {
                                title: (items) => products[items[0].dataIndex]?.name || "",
                                label: (ctx) => {
                                    const item = products[ctx.dataIndex];
                                    return [
                                        `${_t("Giá trị")}: ${fmtMoney(item.total_amount)}`,
                                        `${_t("Số chứng từ")}: ${fmtNum(item.doc_count)}`,
                                        `${_t("Số lượng")}: ${fmtNum(item.total_qty)}`,
                                    ];
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            ticks: {
                                callback: (v) => fmtNum(v),
                                color: "#111827",
                            },
                            grid: { color: "#d1d5db" },
                            border: { color: "#111827", width: 2 },
                        },
                        y: {
                            ticks: { color: "#111827", font: { size: 12, weight: "700" } },
                            grid: { display: false },
                            border: { color: "#111827", width: 2 },
                        },
                    },
                    onClick: (evt, elements) => {
                        if (!elements?.length) return;
                        const item = products[elements[0].index];
                        this.openOrdersByIds(item.order_ids || []);
                    },
                },
            });
        }

        // ===== 3. Chi phí dự án =====
        const expenses = this.state.data.project_expense || [];
        if (this.projectExpenseChartRef.el && expenses.length) {
            this._charts.projectExpense = new Chart(this.projectExpenseChartRef.el, {
                type: "bar",
                data: {
                    labels: expenses.map((e) => this._truncateLabel(e.name, 18)),
                    datasets: [
                        {
                            label: _t("Đã chi"),
                            data: expenses.map((e) => e.spent || 0),
                            backgroundColor: "#2563eb",
                            borderColor: "#111827",
                            borderWidth: 2,
                            borderRadius: 0,
                        },
                        {
                            label: _t("Chưa chi"),
                            data: expenses.map((e) => e.not_spent || 0),
                            backgroundColor: "#f59e0b",
                            borderColor: "#111827",
                            borderWidth: 2,
                            borderRadius: 0,
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
                                color: "#111827",
                                font: { size: 12, weight: "700" },
                            },
                        },
                        tooltip: {
                            callbacks: {
                                title: (items) => expenses[items[0].dataIndex]?.name || "",
                                afterBody: (items) => {
                                    const item = expenses[items[0].dataIndex];
                                    return [
                                        `${_t("Tổng dự toán")}: ${fmtMoney(item.total)}`,
                                    ];
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            stacked: false,
                            ticks: {
                                color: "#111827",
                                font: { size: 11, weight: "700" },
                                maxRotation: 0,
                                minRotation: 0,
                            },
                            grid: { display: false },
                            border: { color: "#111827", width: 2 },
                        },
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: (v) => fmtNum(v),
                                color: "#111827",
                            },
                            grid: { color: "#d1d5db" },
                            border: { color: "#111827", width: 2 },
                        },
                    },
                    onClick: (evt, elements) => {
                        if (!elements?.length) return;
                        const item = expenses[elements[0].index];
                        this.openProject(item.project_id);
                    },
                },
            });
        }

        // ===== 4. Hóa đơn =====
        const invoice = this.state.data.invoice_overview;
        if (this.invoiceChartRef.el && invoice) {
            this._charts.invoice = new Chart(this.invoiceChartRef.el, {
                type: "doughnut",
                data: {
                    labels: [_t("Đầu vào"), _t("Đầu ra")],
                    datasets: [{
                        data: [invoice.supplier_total || 0, invoice.customer_total || 0],
                        backgroundColor: ["#ef4444", "#22c55e"],
                        borderColor: "#111827",
                        borderWidth: 2,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "58%",
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                color: "#111827",
                                font: { size: 12, weight: "700" },
                            },
                        },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const amount = idx === 0 ? invoice.supplier_total : invoice.customer_total;
                                    const count = idx === 0 ? invoice.supplier_count : invoice.customer_count;
                                    return [
                                        `${ctx.label}: ${fmtMoney(amount)}`,
                                        `${_t("Số hóa đơn")}: ${fmtNum(count)}`,
                                    ];
                                },
                            },
                        },
                    },
                    onClick: (evt, elements) => {
                        if (!elements?.length) return;
                        if (elements[0].index === 0) {
                            this.openSupplierInvoices();
                        } else {
                            this.openCustomerInvoices();
                        }
                    },
                },
            });
        }
    }
}

registry.category("actions").add("executive_dashboard", ExecutiveDashboard);
export default ExecutiveDashboard;