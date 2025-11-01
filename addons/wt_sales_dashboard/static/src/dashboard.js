/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

class SalesDashboard extends Component {
    static template = "wt_sales_dashboard.SalesDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const today = new Date();
        const toISO = (d) => d.toISOString().slice(0, 10);

        this.state = useState({
            kpis: { total_sales: 0, avg_order_value: 0, order_count: 0, low_stock_products: 0 },
            charts: { sales_trend: { labels: [], data: [] }, top_products: { labels: [], data: [], uoms: [] } },
            recent_orders: [],
            filters: {
                date_from: toISO(new Date(today.getTime() - 29 * 24 * 3600 * 1000)), // mặc định 30 ngày
                date_to: toISO(today),
            },
        });

        this.salesTrendChartRef = useRef("salesTrendChart");
        this.topProductsChartRef = useRef("topProductsChart");
        this._charts = { sales: null, top: null };

        onWillStart(async () => { await this.fetchData(); });
        onMounted(() => { this.renderCharts(); });
    }

    get periodLabel() {
        const { date_from, date_to } = this.state.filters;
        if (!date_from || !date_to) return _t("Không xác định");
        const fmt = (s) => new Date(s).toLocaleDateString("vi-VN");
        return `${fmt(date_from)} → ${fmt(date_to)}`;
    }

    async fetchData() {
        const { date_from, date_to } = this.state.filters;
        try {
            const data = await this.orm.call("wt.sales.dashboard", "get_dashboard_data", [], { date_from, date_to });
            // gán trực tiếp vào reactive state
            this.state.kpis = data.kpis || this.state.kpis;
            this.state.charts = data.charts || this.state.charts;
            this.state.recent_orders = data.recent_orders || [];
            this.renderCharts(); // vẽ lại chart
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Không thể tải dữ liệu bảng điều khiển."), { type: "danger" });
        }
    }

    applyFilter() {
        const { date_from, date_to } = this.state.filters;
        if (date_from && date_to && date_from > date_to) {
            this.notification.add(_t("Ngày bắt đầu phải ≤ ngày kết thúc."), { type: "warning" });
            return;
        }
        this.fetchData();
    }

    _destroyCharts() {
        if (this._charts.sales) { this._charts.sales.destroy(); this._charts.sales = null; }
        if (this._charts.top) { this._charts.top.destroy(); this._charts.top = null; }
    }

    renderCharts() {
        this._destroyCharts();

        // Sales trend
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
                options: { responsive: true, maintainAspectRatio: false },
            });
        }

        // Top products
        if (this.topProductsChartRef.el) {
            const labels = this.state.charts.top_products.labels || [];
            const data = this.state.charts.top_products.data || [];
            const uoms = this.state.charts.top_products.uoms || [];
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
                                    const n = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(val);
                                    return _t("Số lượng: ") + `${n} ${unit}`;
                                },
                            },
                        },
                    },
                },
            });
        }
    }

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
        const { date_from, date_to } = this.state.filters;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Đơn bán theo khoảng ngày"),
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [
                ["date_order", ">=", date_from],
                ["date_order", "<=", date_to],
                ["state", "in", ["sale", "done"]],
            ],
            target: "current",
        });
    }

    openTotalOrders() { this.openTotalSales(); }

    openLowStockProducts() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Sản phẩm sắp hết hàng"),
            res_model: "product.product",
            views: [[false, "list"], [false, "form"]],
            domain: [["type", "in", ["product", "consu"]], ["qty_available", "<=", 10]],
            target: "current",
        });
    }
}

registry.category("actions").add("wt_sales_dashboard.dashboard", SalesDashboard);
