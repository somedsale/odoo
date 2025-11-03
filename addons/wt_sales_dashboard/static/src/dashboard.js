/** @odoo-module **/

import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = "wt_sales_dashboard_filters_v1"; // đổi version nếu schema khác

class SalesDashboard extends Component {
    static template = "wt_sales_dashboard.SalesDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const today = new Date();
        const toISO = (d) => d.toISOString().slice(0, 10);

        // 1) Khởi tạo state
        this.state = useState({
            kpis: { total_sales: 0, avg_order_value: 0, order_count: 0, category_count: 0 },
            charts: {
                sales_trend: { labels: [], data: [] },
                top_products: { labels: [], data: [], uoms: [] },
            },
            recent_orders: [],
            filters: {
                date_from: toISO(new Date(today.getTime() - 29 * 24 * 3600 * 1000)), // mặc định 30 ngày
                date_to: toISO(today),
            },
        });

        // 2) Thử phục hồi bộ lọc từ localStorage trước khi fetch
        this._restoreFiltersFromStorage();

        this.salesTrendChartRef = useRef("salesTrendChart");
        this.topProductsChartRef = useRef("topProductsChart");
        this.categoryChartRef = useRef("categoryChart");
        this._charts = { sales: null, top: null };

        onWillStart(async () => { await this.fetchData(); });
        onMounted(() => { this.renderCharts(); });
    }

    // ===== Persist filters =====
    _restoreFiltersFromStorage() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;
            const saved = JSON.parse(raw);
            if (saved && saved.date_from && saved.date_to) {
                // Optionally: validate format 'YYYY-MM-DD'
                this.state.filters.date_from = saved.date_from;
                this.state.filters.date_to = saved.date_to;
            }
        } catch (_) {
        }
    }
    _saveFiltersToStorage() {
        try {
            const { date_from, date_to } = this.state.filters;
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ date_from, date_to }));
        } catch (_) {
        }
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
            this.state.kpis = data.kpis || this.state.kpis;
            this.state.charts = data.charts || this.state.charts;
            this.state.recent_orders = data.recent_orders || [];
            this.renderCharts();
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
        this._saveFiltersToStorage();   // <-- LƯU trước khi gọi
        this.fetchData();
    }

    _destroyCharts() {
        if (this._charts.sales) { this._charts.sales.destroy(); this._charts.sales = null; }
        if (this._charts.top) { this._charts.top.destroy(); this._charts.top = null; }
        if (this._charts.cat) { this._charts.cat.destroy(); this._charts.cat = null; }
    }

    renderCharts() {
        this._destroyCharts();
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
        if (this.topProductsChartRef.el) {
            const labels = this.state.charts.top_products.labels || [];
            const data = this.state.charts.top_products.data || [];
            const uoms = this.state.charts.top_products.uoms || [];
            this._charts.top = new Chart(this.topProductsChartRef.el, {
                type: "bar",
                data: {
                    labels,
                    datasets: [{ label: _t("Số lượng bán"), data, backgroundColor: ["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6"] }],
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
        if (this.categoryChartRef.el) {
            const sc = this.state.charts.sale_categories || { labels: [], data: [], colors: [] };
            const labels = sc.labels || [];
            const data = sc.data || [];
            let colors = sc.colors || [];
            if (!colors.length) {
                colors = ["#6366F1", "#3B82F6", "#06B6D4", "#10B981", "#84CC16", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#22C55E", "#F97316", "#0EA5E9"];
            }
            this._charts.cat = new Chart(this.categoryChartRef.el, {
                type: "doughnut",
                data: {
                    labels,
                    datasets: [{
                        label: _t("Số đơn theo hạng mục"),
                        data,
                        backgroundColor: colors.slice(0, Math.max(colors.length, data.length)),
                        borderWidth: 1
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
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
                            labels: { usePointStyle: true }
                        },
                    },
                    cutout: "55%",
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
        // TIP: đã lưu filters vào localStorage rồi, nên back lại vẫn khôi phục được
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

    openCategories() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Hạng mục bán hàng"),
            res_model: "sale.order.category",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("wt_sales_dashboard.dashboard", SalesDashboard);
