/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = "executive_dashboard_filters_sidebar_v1";

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
            selectedDept: "overview",
        });

        this.departments = [
            { key: "overview", label: _t("Tổng quan"), icon: "fa fa-th-large" },
            { key: "sales", label: _t("Phòng Kinh doanh"), icon: "fa fa-line-chart" },
            { key: "finance", label: _t("Phòng Kế Toán"), icon: "fa fa-money" },
            { key: "project", label: _t("Phòng KH-KT"), icon: "fa fa-briefcase" },
            { key: "approval", label: _t("Duyệt phiếu"), icon: "fa fa-check-square-o" },
        ];

        this.filterPanelRef = useRef("filterPanel");

        this.customerChartRef = useRef("customerChart");
        this.productChartRef = useRef("productChart");
        this.projectExpenseChartRef = useRef("projectExpenseChart");
        this.invoiceChartRef = useRef("invoiceChart");

        this.salesCustomerChartRef = useRef("salesCustomerChart");
        this.salesProductChartRef = useRef("salesProductChart");
        this.financeInvoiceChartRef = useRef("financeInvoiceChart");
        this.projectOnlyChartRef = useRef("projectOnlyChart");

        this._charts = {};

        this.years = Array.from({ length: 10 }, (_, i) => 2022 + i);

        this._restoreStateFromStorage();

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

    _restoreStateFromStorage() {
        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
            if (saved?.filters) {
                Object.assign(this.state.filters, saved.filters);
            }
            if (saved?.selectedDept) {
                this.state.selectedDept = saved.selectedDept;
            }
        } catch (_) { }
    }

    _saveStateToStorage() {
        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({
                filters: this.state.filters,
                selectedDept: this.state.selectedDept,
            })
        );
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

    get currentData() {
        return this.state.data || {};
    }

    get kpis() {
        return this.currentData.kpis || {};
    }

    get quotationKpi() {
        return this.kpis.quotation || { count: 0, total_amount: 0 };
    }

    get orderKpi() {
        return this.kpis.order || { count: 0, total_amount: 0 };
    }

    get conversionRate() {
        return this.currentData.conversion_rate || 0;
    }

    get cashIn() {
        return this.kpis.cash_in || 0;
    }

    get cashOut() {
        return this.kpis.cash_out || 0;
    }

    get netCash() {
        return this.kpis.net_cash || 0;
    }

    get topOrder() {
        return this.currentData.top_order || null;
    }

    get topCustomers() {
        return this.currentData.top_customers || [];
    }

    get topProducts() {
        return this.currentData.top_products || [];
    }

    get projectExpense() {
        return this.currentData.project_expense || [];
    }

    get invoiceOverview() {
        return this.currentData.invoice_overview || {
            supplier_total: 0,
            customer_total: 0,
            net_invoice: 0,
        };
    }
    get projectSummary() {
        return {
            total_projects: this.currentData.project_total || 0,
            done_projects: this.currentData.project_done_count || 0,
            in_progress_projects: this.currentData.project_in_progress_count || 0,
            total_budget: this.currentData.khkt_total_budget || 0,
            total_spent: this.currentData.khkt_total_spent || 0,
            total_remaining: this.currentData.khkt_total_remaining || 0,
        };
    }

    get hrSummary() {
        return {
            total_employees: this.currentData.hr_total_employees || 0,
            active_employees: this.currentData.hr_active_employees || 0,
            departments: this.currentData.hr_departments || 0,
            absent_today: this.currentData.hr_absent_today || 0,
        };
    }
    get approvalSummary() {
        const s = this.currentData.approval_summary || {};
        return {
            proposal_count: s.proposal_pending_count || 0,
            payment_count: s.payment_pending_count || 0,
            pending_count: s.pending_count || 0,
            pending_amount: s.pending_amount || 0,
            proposal_pending_amount: s.proposal_pending_amount || 0,
            payment_pending_amount: s.payment_pending_amount || 0,
        };
    }

    get approvalItems() {
        return this.currentData.approval_pending_items || [];
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
            this._saveStateToStorage();
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

    selectDept(deptKey) {
        this.state.selectedDept = deptKey;
        this._saveStateToStorage();
        setTimeout(() => this.renderCharts(), 0);
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
        const topOrder = this.topOrder;
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

        this._renderCustomerChart(this.customerChartRef.el, this.topCustomers, "customer_main");
        this._renderProductChart(this.productChartRef.el, this.topProducts, "product_main");
        this._renderProjectExpenseChart(this.projectExpenseChartRef.el, this.projectExpense, "project_main");
        this._renderInvoiceChart(this.invoiceChartRef.el, this.invoiceOverview, "invoice_main");

        this._renderCustomerChart(this.salesCustomerChartRef.el, this.topCustomers, "customer_sales");
        this._renderProductChart(this.salesProductChartRef.el, this.topProducts, "product_sales");
        this._renderInvoiceChart(this.financeInvoiceChartRef.el, this.invoiceOverview, "invoice_finance");
        this._renderProjectExpenseChart(this.projectOnlyChartRef.el, this.projectExpense, "project_only");
    }

    _renderCustomerChart(el, customers, chartKey) {
        if (!el || !customers?.length) return;

        this._charts[chartKey] = new Chart(el, {
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

    _renderProductChart(el, products, chartKey) {
        if (!el || !products?.length) return;

        this._charts[chartKey] = new Chart(el, {
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
                    legend: { display: false },
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

    _renderProjectExpenseChart(el, expenses, chartKey) {
        if (!el || !expenses?.length) return;

        this._charts[chartKey] = new Chart(el, {
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
                        backgroundColor: "#cbd5e1",
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
                                return [`${_t("Tổng chi phí")}: ${fmtMoney(item.total)}`];
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: { color: "#111827", font: { size: 12, weight: "700" } },
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
                    this.openProject(item.project_id || false);
                },
            },
        });
    }

    _renderInvoiceChart(el, invoiceOverview, chartKey) {
        if (!el) return;

        this._charts[chartKey] = new Chart(el, {
            type: "doughnut",
            data: {
                labels: [_t("Đầu vào"), _t("Đầu ra")],
                datasets: [{
                    data: [
                        invoiceOverview.supplier_total || 0,
                        invoiceOverview.customer_total || 0,
                    ],
                    backgroundColor: ["#cbd5e1", "#2563eb"],
                    borderColor: "#ffffff",
                    borderWidth: 2,
                }],
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
                            label: (ctx) => `${ctx.label}: ${fmtMoney(ctx.raw)}`,
                        },
                    },
                },
            },
        });
    }
}

registry.category("actions").add("executive_dashboard", ExecutiveDashboard);