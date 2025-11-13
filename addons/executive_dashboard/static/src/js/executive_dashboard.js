/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState, nextTick } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

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
        this.productChartRef = useRef("productChart"); // ✅ dùng ref an toàn hơn getElementById
        this._chart = null;

        this.years = Array.from({ length: 10 }, (_, i) => 2022 + i);

        // Khi load component
        onWillStart(async () => await this.fetchData());

        onMounted(() => {
            this._onClickOutside = this.onClickOutside.bind(this);
            document.addEventListener("click", this._onClickOutside);
        });

        // Cleanup khi destroy component
        onWillUnmount(() => {
            document.removeEventListener("click", this._onClickOutside);
            if (this._chart) this._chart.destroy();
        });
    }

    // ==========================
    // FETCH DATA
    // ==========================
    async fetchData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call("wt.executive.dashboard", "get_dashboard_data", [this.state.filters]);
            this.state.data = data;

            // ✅ Đợi DOM cập nhật xong rồi mới vẽ chart
            await new Promise((resolve) => setTimeout(resolve));
            this.renderCharts();
        } catch (err) {
            console.error("Dashboard Error:", err);
            this.notification.add(_t("Không thể tải dữ liệu Dashboard."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // ==========================
    // RENDER CHART
    // ==========================
    renderCharts() {
        if (!window.Chart || !this.state.data) return;

        const canvas = this.productChartRef.el;
        if (!canvas) return;

        const products = this.state.data.top_products || [];
        if (!products.length) return;

        const labels = products.map((p) => p.name);
        const quotations = products.map((p) => p.quotation_qty);
        const orders = products.map((p) => p.order_qty);

        if (this._chart) this._chart.destroy(); // tránh đè biểu đồ cũ

        this._chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: _t("Báo giá"),
                        data: quotations,
                        backgroundColor: "rgba(37, 99, 235, 0.6)",
                        borderRadius: 6,
                    },
                    {
                        label: _t("Đã bán"),
                        data: orders,
                        backgroundColor: "rgba(16, 185, 129, 0.6)",
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" },
                    title: {
                        display: true,
                        text: _t("So sánh Báo giá & Đơn hàng theo sản phẩm"),
                        font: { size: 14 },
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) =>
                                `${ctx.dataset.label}: ${ctx.parsed.y?.toLocaleString("vi-VN") || 0} sản phẩm`,
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: _t("Số lượng") },
                    },
                    x: { grid: { display: false } },
                },
            },
        });
    }

    // ==========================
    // FILTERS
    // ==========================
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

    // ==========================
    // CLICK NGOÀI PANEL ĐỂ ĐÓNG
    // ==========================
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
