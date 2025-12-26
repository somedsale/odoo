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
            kpis: { total_sales: 0, avg_order_value: 0, order_count: 0, category_count: 0, total_quotations: 0, quotation_count: 0, contract_count: 0, total_contract: 0, },
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
        const { date_from, date_to } = this.state.filters;

        // 1) Sales trend (click 1 điểm -> mở đơn của ngày đó)
        const fmtVN = (s) => {
            if (!s) return "";
            const [y, m, d] = String(s).split("-");
            return `${d}/${m}/${y}`;
        };

        if (this.salesTrendChartRef.el) {
            this._charts.sales = new Chart(this.salesTrendChartRef.el, {
                type: "line",
                data: {
                    labels: this.state.charts.sales_trend.labels, // vẫn là YYYY-MM-DD
                    datasets: [{
                        label: _t("Doanh thu"),
                        data: this.state.charts.sales_trend.data,
                        borderColor: "#4F46E5",
                        backgroundColor: "rgba(79, 70, 229, 0.1)",
                        fill: true, tension: 0.3,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,

                    // ✅ format nhãn trục X thành dd/mm/yyyy
                    scales: {
                        x: {
                            ticks: {
                                callback: (val, idx) => fmtVN(this.state.charts.sales_trend.labels[idx]),
                            },
                        },
                    },

                    // ✅ format tiêu đề tooltip thành dd/mm/yyyy
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

                    // ✅ khi click, tiêu đề action hiển thị dd/mm/yyyy; domain vẫn dùng YYYY-MM-DD
                    onClick: (evt, elements) => {
                        if (!elements?.length) return;
                        const idx = elements[0].index;               // v4 vẫn hợp lệ
                        const day = this.state.charts.sales_trend.labels[idx]; // "YYYY-MM-DD"
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

        // 2) Top products (click 1 thanh -> mở đơn chứa sản phẩm đó)
        if (this.topProductsChartRef.el) {
            const tp = this.state.charts.top_products || {};
            const labels = tp.labels || [];
            const data = tp.data || [];
            const uoms = tp.uoms || [];
            const ids = tp.ids || []; // <-- NEW

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
                    responsive: true, maintainAspectRatio: false, indexAxis: "y",
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
                                ["order_line.product_id", "=", productId], // lọc theo SP
                            ],
                            target: "current",
                        });
                    },
                },
            });
        }

        // 3) Sale categories (click 1 phần -> mở đơn thuộc hạng mục đó)
        if (this.categoryChartRef.el) {
            const sc = this.state.charts.sale_categories || { labels: [], data: [], colors: [], ids: [] };
            const labels = sc.labels || [];
            const data = sc.data || [];
            const colors = (sc.colors && sc.colors.length ? sc.colors : ["#6366F1", "#3B82F6", "#06B6D4", "#10B981", "#84CC16", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#22C55E", "#F97316", "#0EA5E9"]);
            const ids = sc.ids || []; // <-- NEW (category ids)

            this._charts.cat = new Chart(this.categoryChartRef.el, {
                type: "doughnut",
                data: { labels, datasets: [{ label: _t("Số đơn theo hạng mục"), data, backgroundColor: colors, borderWidth: 1 }] },
                options: {
                    responsive: true, maintainAspectRatio: false, cutout: "55%",
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
                        legend: { position: "right", labels: { usePointStyle: true } },
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
                                ["sales_category_ids", "in", [catId]], // lọc theo hạng mục
                            ],
                            target: "current",
                        });
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
    openTotalAmountQuotations() {
        const { date_from, date_to } = this.state.filters;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Báo giá theo khoảng ngày"),
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [
                ["date_order", ">=", date_from],
                ["date_order", "<=", date_to],
                ["state", "in", ["sent"]],
            ],
            target: "current",
        });
    }
    openTotalQuotations() { this.openTotalAmountQuotations(); }
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
