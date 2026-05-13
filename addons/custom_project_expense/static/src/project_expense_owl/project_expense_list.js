/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class ProjectExpenseList extends Component {
    static template = "project_expense.ProjectExpenseList";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            records: [],
            keyword: "",
            filterMode: "",
            page: 1,
            pageSize: 20,
            totalCount: 0,
            totals: {
                count: 0,

                estimateTotal: 0,
                varianceEstimate: 0,

                totalCost: 0,
                totalSpent: 0,
                totalNotSpent: 0,

                totalMaterial: 0,
                totalLabor: 0,
                totalManufacturing: 0,

                spentMaterial: 0,
                spentLabor: 0,
                spentManufacturing: 0,

                notSpentMaterial: 0,
                notSpentLabor: 0,
                notSpentManufacturing: 0,
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    getDomain() {
        const domain = [];

        if (this.state.filterMode === "has_spent") {
            domain.push(["total_spent", ">", 0]);
        }

        if (this.state.filterMode === "has_not_spent") {
            domain.push(["total_not_spent", ">", 0]);
        }

        if (this.state.filterMode === "has_material") {
            domain.push(["total_material", ">", 0]);
        }

        if (this.state.filterMode === "has_labor") {
            domain.push(["total_labor", ">", 0]);
        }

        if (this.state.filterMode === "has_manufacturing") {
            domain.push(["total_manufacturing", ">", 0]);
        }

        // Vượt dự toán: Tổng chi phí - Tổng dự toán > 0
        if (this.state.filterMode === "over_estimate") {
            domain.push(["cost_vs_estimate_amount", ">", 0]);
        }

        // Thấp hơn dự toán: Tổng chi phí - Tổng dự toán < 0
        if (this.state.filterMode === "under_estimate") {
            domain.push(["cost_vs_estimate_amount", "<", 0]);
        }

        if (this.state.keyword && this.state.keyword.trim()) {
            const kw = this.state.keyword.trim();

            domain.push(
                "|", "|", "|",
                ["project_id.name", "ilike", kw],
                ["partner_id.name", "ilike", kw],
                ["contract_number", "ilike", kw],
                ["name", "ilike", kw]
            );
        }

        return domain;
    }

    async loadData() {
        this.state.loading = true;

        const domain = this.getDomain();
        const offset = (this.state.page - 1) * this.state.pageSize;

        try {
            const totalCount = await this.orm.searchCount("project.expense.custom", domain);

            const records = await this.orm.searchRead(
                "project.expense.custom",
                domain,
                [
                    "name",
                    "project_id",
                    "partner_id",
                    "contract_number",
                    "signature_date",
                    "date_start",
                    "date_end",

                    "cost_estimate_id",
                    "estimate_total_non_tax",
                    "estimate_total_with_tax",
                    "estimate_material_with_tax",
                    "estimate_labor_with_tax",
                    "estimate_manufacturing_with_tax",
                    "estimate_additional_with_tax",
                    "cost_vs_estimate_amount",
                    "cost_vs_estimate_percent",
                    "spent_vs_estimate_percent",

                    "total_spent",
                    "total_not_spent",
                    "total_cost",

                    "total_spent_material",
                    "total_spent_labor",
                    "total_spent_manufacturing",

                    "total_not_spent_material",
                    "total_not_spent_labor",
                    "total_not_spent_manufacturing",

                    "total_material",
                    "total_labor",
                    "total_manufacturing",

                    "currency_id",
                    "create_date",
                ],
                {
                    order: "create_date desc",
                    limit: this.state.pageSize,
                    offset: offset,
                }
            );

            this.state.totalCount = totalCount;
            this.state.records = records;

            await this.computeTotals(domain);
        } catch (error) {
            console.error(error);
            this.notification.add("Không tải được dữ liệu chi phí dự án.", {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async computeTotals(domain) {
        const allRecords = await this.orm.searchRead(
            "project.expense.custom",
            domain,
            [
                "estimate_total_with_tax",
                "cost_vs_estimate_amount",

                "total_spent",
                "total_not_spent",
                "total_cost",

                "total_spent_material",
                "total_spent_labor",
                "total_spent_manufacturing",

                "total_not_spent_material",
                "total_not_spent_labor",
                "total_not_spent_manufacturing",

                "total_material",
                "total_labor",
                "total_manufacturing",
            ],
            {
                limit: 0,
            }
        );

        const totals = {
            count: allRecords.length,

            estimateTotal: 0,
            varianceEstimate: 0,

            totalCost: 0,
            totalSpent: 0,
            totalNotSpent: 0,

            totalMaterial: 0,
            totalLabor: 0,
            totalManufacturing: 0,

            spentMaterial: 0,
            spentLabor: 0,
            spentManufacturing: 0,

            notSpentMaterial: 0,
            notSpentLabor: 0,
            notSpentManufacturing: 0,
        };

        for (const rec of allRecords) {
            totals.estimateTotal += rec.estimate_total_with_tax || 0;
            totals.varianceEstimate += rec.cost_vs_estimate_amount || 0;

            totals.totalCost += rec.total_cost || 0;
            totals.totalSpent += rec.total_spent || 0;
            totals.totalNotSpent += rec.total_not_spent || 0;

            totals.totalMaterial += rec.total_material || 0;
            totals.totalLabor += rec.total_labor || 0;
            totals.totalManufacturing += rec.total_manufacturing || 0;

            totals.spentMaterial += rec.total_spent_material || 0;
            totals.spentLabor += rec.total_spent_labor || 0;
            totals.spentManufacturing += rec.total_spent_manufacturing || 0;

            totals.notSpentMaterial += rec.total_not_spent_material || 0;
            totals.notSpentLabor += rec.total_not_spent_labor || 0;
            totals.notSpentManufacturing += rec.total_not_spent_manufacturing || 0;
        }

        this.state.totals = totals;
    }

    goBack() {
        if (window.history.length > 1) {
            window.history.back();
        } else {
            this.openClassicList();
        }
    }

    async onSearch(ev) {
        this.state.keyword = ev.target.value || "";
        this.state.page = 1;
        await this.loadData();
    }

    async onChangeFilterMode(ev) {
        this.state.filterMode = ev.target.value || "";
        this.state.page = 1;
        await this.loadData();
    }

    async resetFilters() {
        this.state.keyword = "";
        this.state.filterMode = "";
        this.state.page = 1;
        await this.loadData();
    }

    async refresh() {
        await this.loadData();
        this.notification.add("Đã làm mới dữ liệu.", {
            type: "success",
        });
    }

    async onChangePageSize(ev) {
        this.state.pageSize = parseInt(ev.target.value || "20");
        this.state.page = 1;
        await this.loadData();
    }

    get totalPages() {
        if (!this.state.totalCount) return 1;
        return Math.max(1, Math.ceil(this.state.totalCount / this.state.pageSize));
    }

    get pageStart() {
        if (!this.state.totalCount) return 0;
        return (this.state.page - 1) * this.state.pageSize + 1;
    }

    get pageEnd() {
        if (!this.state.totalCount) return 0;
        return Math.min(this.state.page * this.state.pageSize, this.state.totalCount);
    }

    get pageTokens() {
        const total = this.totalPages;
        const current = this.state.page;
        const pages = [];

        const addPage = (p) => {
            pages.push({
                key: `p_${p}`,
                page: p,
                label: String(p),
                ellipsis: false,
            });
        };

        const addEllipsis = (key) => {
            pages.push({
                key,
                label: "...",
                ellipsis: true,
            });
        };

        if (total <= 7) {
            for (let p = 1; p <= total; p++) {
                addPage(p);
            }
            return pages;
        }

        addPage(1);

        if (current > 4) {
            addEllipsis("e_left");
        }

        const start = Math.max(2, current - 1);
        const end = Math.min(total - 1, current + 1);

        for (let p = start; p <= end; p++) {
            addPage(p);
        }

        if (current < total - 3) {
            addEllipsis("e_right");
        }

        addPage(total);

        return pages;
    }

    async firstPage() {
        if (this.state.page <= 1) return;
        this.state.page = 1;
        await this.loadData();
    }

    async prevPage() {
        if (this.state.page <= 1) return;
        this.state.page -= 1;
        await this.loadData();
    }

    async nextPage() {
        if (this.state.page >= this.totalPages) return;
        this.state.page += 1;
        await this.loadData();
    }

    async lastPage() {
        if (this.state.page >= this.totalPages) return;
        this.state.page = this.totalPages;
        await this.loadData();
    }

    async onClickPage(ev) {
        const page = parseInt(ev.currentTarget.dataset.page || "1");
        if (!page || page === this.state.page) return;

        this.state.page = page;
        await this.loadData();
    }

    openRecord(ev) {
        const row = ev.currentTarget;
        const id = parseInt(row.dataset.id || "0");
        if (!id) return;

        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Chi phí dự án",
            res_model: "project.expense.custom",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
            context: {
                readonly_by_ctx: true,
            },
        });
    }

    createRecord() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tạo chi phí dự án",
            res_model: "project.expense.custom",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openClassicList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Chi phí dự án",
            res_model: "project.expense.custom",
            views: [[false, "tree"], [false, "form"]],
            target: "current",
        });
    }

    money(value) {
        const number = value || 0;
        return new Intl.NumberFormat("vi-VN", {
            style: "currency",
            currency: "VND",
            maximumFractionDigits: 0,
        }).format(number);
    }

    formatDate(value) {
        if (!value) return "-";
        return new Date(value).toLocaleDateString("vi-VN");
    }

    many2oneName(value) {
        if (Array.isArray(value) && value.length > 1) {
            return value[1];
        }
        return "-";
    }

    percent(value, total) {
        const v = value || 0;
        const t = total || 0;
        if (!t) return "0%";
        return `${Math.round((v / t) * 100)}%`;
    }

    percentClass(value, total) {
        const v = value || 0;
        const t = total || 0;
        const p = t ? (v / t) * 100 : 0;

        if (p >= 100) return "pe-percent-badge is-done";
        if (p >= 70) return "pe-percent-badge is-good";
        if (p >= 30) return "pe-percent-badge is-mid";
        return "pe-percent-badge is-low";
    }

    percentBadgeByValue(value) {
        const number = value || 0;

        if (number >= 100) return "pe-percent-badge is-done";
        if (number >= 70) return "pe-percent-badge is-good";
        if (number >= 30) return "pe-percent-badge is-mid";
        return "pe-percent-badge is-low";
    }

    compareClass(value) {
        const number = value || 0;

        if (number > 0) {
            return "pe-compare-badge is-over";
        }

        if (number < 0) {
            return "pe-compare-badge is-under";
        }

        return "pe-compare-badge is-ok";
    }
}

registry.category("actions").add("project_expense_owl_list", ProjectExpenseList);