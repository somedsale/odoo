/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = "wt_sales_dashboard_filters_v2";

class SalesDashboard extends Component {
    static template = "wt_sales_dashboard.SalesDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const today = new Date();
        const toISO = (d) => this._toISODateLocal(d);

        this.state = useState({
            kpis: {
                total_sales: 0,
                avg_order_value: 0,
                order_count: 0,
                category_count: 0,
                total_quotations: 0,
                quotation_count: 0,
                close_rate_value: 0.0,
                close_rate_count: 0.0,
            },
            charts: {
                sales_trend: { labels: [], data: [] },
                top_products: { labels: [], data: [], uoms: [], ids: [] },
                sale_categories: { labels: [], data: [], colors: [], ids: [] },
            },
            recent_orders: [],
            filters: {
                period_type: "custom", // custom | month | quarter | year
                customer_type: "", // "" | online | direct
                year: String(today.getFullYear()),
                month: String(today.getMonth() + 1).padStart(2, "0"),
                quarter: String(Math.floor(today.getMonth() / 3) + 1),
                date_from: toISO(new Date(today.getTime() - 29 * 24 * 3600 * 1000)),
                date_to: toISO(today),
            },
        });

        this._restoreFiltersFromStorage();
        this._syncDatesFromPreset(false);

        this.salesTrendChartRef = useRef("salesTrendChart");
        this.topProductsChartRef = useRef("topProductsChart");
        this.categoryChartRef = useRef("categoryChart");
        this._charts = { sales: null, top: null, cat: null };

        onWillStart(async () => {
            await this.fetchData();
        });
        onMounted(() => {
            this.renderCharts();
        });
    }

    // =========================
    // Utils date
    // =========================
    _toISODateLocal(date) {
        if (!(date instanceof Date) || isNaN(date.getTime())) return "";
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, "0");
        const d = String(date.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
    }

    _getPeriodRange(periodType, year, month, quarter) {
        const y = parseInt(year, 10) || new Date().getFullYear();
        let from;
        let to;

        if (periodType === "month") {
            const m = Math.min(Math.max(parseInt(month, 10) || 1, 1), 12);
            from = new Date(y, m - 1, 1);
            to = new Date(y, m, 0);
        } else if (periodType === "quarter") {
            const q = Math.min(Math.max(parseInt(quarter, 10) || 1, 1), 4);
            const startMonth = (q - 1) * 3;
            from = new Date(y, startMonth, 1);
            to = new Date(y, startMonth + 3, 0);
        } else if (periodType === "year") {
            from = new Date(y, 0, 1);
            to = new Date(y, 11, 31);
        } else {
            return null;
        }

        return {
            date_from: this._toISODateLocal(from),
            date_to: this._toISODateLocal(to),
        };
    }

    _syncDatesFromPreset(notify = false) {
        const { period_type, year, month, quarter } = this.state.filters;
        if (period_type === "custom") {
            return;
        }
        const range = this._getPeriodRange(period_type, year, month, quarter);
        if (range) {
            this.state.filters.date_from = range.date_from;
            this.state.filters.date_to = range.date_to;
            if (notify) {
                this.notification.add(_t("Đã cập nhật khoảng ngày theo bộ lọc thời gian."), {
                    type: "info",
                });
            }
        }
    }

    get yearOptions() {
        const current = new Date().getFullYear();
        const years = [];
        for (let y = current + 1; y >= current - 5; y--) {
            years.push(String(y));
        }
        return years;
    }

    get monthOptions() {
        return [
            { value: "01", label: _t("Tháng 1") },
            { value: "02", label: _t("Tháng 2") },
            { value: "03", label: _t("Tháng 3") },
            { value: "04", label: _t("Tháng 4") },
            { value: "05", label: _t("Tháng 5") },
            { value: "06", label: _t("Tháng 6") },
            { value: "07", label: _t("Tháng 7") },
            { value: "08", label: _t("Tháng 8") },
            { value: "09", label: _t("Tháng 9") },
            { value: "10", label: _t("Tháng 10") },
            { value: "11", label: _t("Tháng 11") },
            { value: "12", label: _t("Tháng 12") },
        ];
    }

    get quarterOptions() {
        return [
            { value: "1", label: _t("Quý 1") },
            { value: "2", label: _t("Quý 2") },
            { value: "3", label: _t("Quý 3") },
            { value: "4", label: _t("Quý 4") },
        ];
    }

    // =========================
    // Persist filters
    // =========================
    _restoreFiltersFromStorage() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;
            const saved = JSON.parse(raw);
            if (!saved) return;

            this.state.filters.period_type = saved.period_type || this.state.filters.period_type;
            this.state.filters.customer_type = saved.customer_type || this.state.filters.customer_type;
            this.state.filters.year = saved.year || this.state.filters.year;
            this.state.filters.month = saved.month || this.state.filters.month;
            this.state.filters.quarter = saved.quarter || this.state.filters.quarter;
            this.state.filters.date_from = saved.date_from || this.state.filters.date_from;
            this.state.filters.date_to = saved.date_to || this.state.filters.date_to;
        } catch (_) { }
    }

    _saveFiltersToStorage() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...this.state.filters }));
        } catch (_) { }
    }

    get periodLabel() {
        const { date_from, date_to } = this.state.filters;
        if (!date_from || !date_to) return _t("Không xác định");
        const fmt = (s) => {
            const [y, m, d] = String(s).split("-");
            return `${d}/${m}/${y}`;
        };
        return `${fmt(date_from)} → ${fmt(date_to)}`;
    }

    // =========================
    // Events filter
    // =========================
    onCustomerTypeChange(ev) {
        this.state.filters.customer_type = ev.target.value;
    }

    onPeriodTypeChange(ev) {
        this.state.filters.period_type = ev.target.value;
        this._syncDatesFromPreset();
    }

    onYearChange(ev) {
        this.state.filters.year = ev.target.value;
        this._syncDatesFromPreset();
    }

    onMonthChange(ev) {
        this.state.filters.month = ev.target.value;
        this._syncDatesFromPreset();
    }

    onQuarterChange(ev) {
        this.state.filters.quarter = ev.target.value;
        this._syncDatesFromPreset();
    }

    onDateFromChange(ev) {
        this.state.filters.date_from = ev.target.value;
        this.state.filters.period_type = "custom";
    }

    onDateToChange(ev) {
        this.state.filters.date_to = ev.target.value;
        this.state.filters.period_type = "custom";
    }

    // =========================
    // Data
    // =========================
    async fetchData() {
        const { date_from, date_to, customer_type } = this.state.filters;

        try {
            const data = await this.orm.call("wt.sales.dashboard", "get_dashboard_data", [], {
                date_from,
                date_to,
                customer_type,
            });

            this.state.kpis = data.kpis || this.state.kpis;
            this.state.charts = data.charts || this.state.charts;
            this.state.recent_orders = data.recent_orders || [];

            this.renderCharts();
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Không thể tải dữ liệu bảng điều khiển."), {
                type: "danger",
            });
        }
    }

    applyFilter() {
        const { date_from, date_to } = this.state.filters;
        if (date_from && date_to && date_from > date_to) {
            this.notification.add(_t("Ngày bắt đầu phải ≤ ngày kết thúc."), {
                type: "warning",
            });
            return;
        }
        this._saveFiltersToStorage();
        this.fetchData();
    }

    // =========================
    // Charts
    // =========================
    _destroyCharts() {
        if (this._charts.sales) {
            this._charts.sales.destroy();
            this._charts.sales = null;
        }
        if (this._charts.top) {
            this._charts.top.destroy();
            this._charts.top = null;
        }
        if (this._charts.cat) {
            this._charts.cat.destroy();
            this._charts.cat = null;
        }
    }
    _getCustomerTypeDomain() {
        const customerType = this.state.filters.customer_type;
        return customerType ? [["customer_type", "=", customerType]] : [];
    }

    _getDateDomain(fieldName = "date_order") {
        const { date_from, date_to } = this.state.filters;
        return [
            [fieldName, ">=", date_from],
            [fieldName, "<=", date_to],
        ];
    }
    renderCharts() {
        this._destroyCharts();
        const { date_from, date_to } = this.state.filters;

        const fmtVN = (s) => {
            if (!s) return "";
            const [y, m, d] = String(s).split("-");
            return `${d}/${m}/${y}`;
        };

        if (this.salesTrendChartRef.el) {
            this._charts.sales = new Chart(this.salesTrendChartRef.el, {
                type: "line",
                data: {
                    labels: this.state.charts.sales_trend.labels,
                    datasets: [{
                        label: _t("Doanh thu"),
                        data: this.state.charts.sales_trend.data,
                        borderColor: "#4F46E5",
                        backgroundColor: "rgba(79, 70, 229, 0.1)",
                        fill: true,
                        tension: 0.3,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            ticks: {
                                callback: (val, idx) => fmtVN(this.state.charts.sales_trend.labels[idx]),
                            },
                        },
                    },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                title: (items) => {
                                    const idx = items?.[0]?.dataIndex ?? 0;
                                    return fmtVN(this.state.charts.sales_trend.labels[idx]);
                                },
                            },
                        },
                    },
                    onClick: (evt, elements) => {
                        if (!elements?.length) return;
                        const idx = elements[0].index;
                        const day = this.state.charts.sales_trend.labels[idx];
                        this.action.doAction({
                            type: "ir.actions.act_window",
                            name: _t("Đơn bán ngày ") + fmtVN(day),
                            res_model: "sale.order",
                            views: [[false, "list"], [false, "form"]],
                            domain: [
                                ["date_order", ">=", day + " 00:00:00"],
                                ["date_order", "<=", day + " 23:59:59"],
                                ["state", "in", ["sale", "done"]],
                            ],
                            target: "current",
                        });
                    },
                },
            });
        }

        if (this.topProductsChartRef.el) {
            const tp = this.state.charts.top_products || {};
            const labels = tp.labels || [];
            const data = tp.data || [];
            const uoms = tp.uoms || [];
            const ids = tp.ids || [];

            this._charts.top = new Chart(this.topProductsChartRef.el, {
                type: "bar",
                data: {
                    labels,
                    datasets: [{
                        label: _t("Số lượng bán"),
                        data,
                        backgroundColor: ["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6"],
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: "y",
                    layout: { padding: { left: 20 } },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                title: (items) => labels[items[0].dataIndex],
                                label: (ctx) => {
                                    const idx = ctx.dataIndex;
                                    const val = ctx.parsed.x ?? 0;
                                    const unit = uoms[idx] || "";
                                    const n = new Intl.NumberFormat("vi-VN", {
                                        maximumFractionDigits: 2,
                                    }).format(val);
                                    return _t("Số lượng: ") + `${n} ${unit}`;
                                },
                            },
                        },
                    },
                    onClick: (evt, elements) => {
                        if (!elements?.length) return;
                        const idx = elements[0].index;
                        const productId = ids[idx];
                        if (!productId) return;

                        this.action.doAction({
                            type: "ir.actions.act_window",
                            name: _t("Đơn chứa sản phẩm: ") + labels[idx],
                            res_model: "sale.order",
                            views: [[false, "list"], [false, "form"]],
                            domain: [
                                ["date_order", ">=", date_from],
                                ["date_order", "<=", date_to],
                                ["state", "in", ["sale", "done"]],
                                ["order_line.product_id", "=", productId],
                            ],
                            target: "current",
                        });
                    },
                },
            });
        }

        if (this.categoryChartRef.el) {
            const sc = this.state.charts.sale_categories || {
                labels: [],
                data: [],
                colors: [],
                ids: [],
            };
            const labels = sc.labels || [];
            const data = sc.data || [];
            const colors = sc.colors?.length
                ? sc.colors
                : ["#6366F1", "#3B82F6", "#06B6D4", "#10B981", "#84CC16", "#F59E0B", "#EF4444", "#8B5CF6"];
            const ids = sc.ids || [];

            this._charts.cat = new Chart(this.categoryChartRef.el, {
                type: "doughnut",
                data: {
                    labels,
                    datasets: [{
                        label: _t("Số đơn theo hạng mục"),
                        data,
                        backgroundColor: colors,
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "55%",
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: (ctx) => {
                                    const total = ctx.dataset.data.reduce((a, b) => a + b, 0) || 1;
                                    const val = ctx.parsed || 0;
                                    const pct = ((val / total) * 100).toFixed(1);
                                    const n = new Intl.NumberFormat("vi-VN").format(val);
                                    return `${ctx.label}: ${n} (${pct}%)`;
                                },
                            },
                        },
                        legend: {
                            position: "right",
                            labels: { usePointStyle: true },
                        },
                    },
                    onClick: (evt, elements) => {
                        if (!elements?.length) return;
                        const idx = elements[0].index;
                        const catId = ids[idx];
                        if (!catId) return;

                        this.action.doAction({
                            type: "ir.actions.act_window",
                            name: _t("Đơn theo hạng mục: ") + labels[idx],
                            res_model: "sale.order",
                            views: [[false, "list"], [false, "form"]],
                            domain: [
                                ["date_order", ">=", date_from],
                                ["date_order", "<=", date_to],
                                ["state", "in", ["draft", "sent", "sale", "done"]],
                                ["sales_category_ids", "in", [catId]],
                            ],
                            target: "current",
                        });
                    },
                },
            });
        }
    }

    // =========================
    // Actions
    // =========================
    openSaleOrder(orderId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            res_id: orderId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTotalSales() {
        const domain = [
            ...this._getDateDomain("date_order"),
            ["state", "in", ["sale", "done"]],
            ...this._getCustomerTypeDomain(),
        ];

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Đơn bán theo khoảng ngày"),
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openTotalOrders() {
        this.openTotalSales();
    }

    openTotalAmountQuotations() {
        const domain = [
            ...this._getDateDomain("date_order"),
            ["state", "in", ["draft", "sent"]],
            ...this._getCustomerTypeDomain(),
        ];

        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Báo giá theo khoảng ngày"),
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openTotalQuotations() {
        this.openTotalAmountQuotations();
    }

    openCategories() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Hạng mục bán hàng"),
            res_model: "sale.order.category",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openContracts() {
        const { date_from, date_to } = this.state.filters;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Hợp đồng theo khoảng ngày"),
            res_model: "contract.management",
            views: [[false, "list"], [false, "form"]],
            domain: [
                ["signature_date", ">=", date_from],
                ["signature_date", "<=", date_to],
            ],
            target: "current",
        });
    }
}

registry.category("actions").add("wt_sales_dashboard.dashboard", SalesDashboard);