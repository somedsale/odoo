/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class CostEstimateList extends Component {
    static template = "cost_estimate.CostEstimateList";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            records: [],
            keyword: "",
            stateFilter: "",
            page: 1,
            pageSize: 10,
            totalCount: 0,
            totals: {
                count: 0,
                draft: 0,
                submitted: 0,
                approved: 0,
                rejected: 0,
                cancel: 0,
                totalFinalNonTax: 0,
                totalFinalTax: 0,
                additionalNonTax: 0,
                additionalWithTax: 0,
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    getDomain() {
        const domain = [];

        if (this.state.stateFilter) {
            domain.push(["state", "=", this.state.stateFilter]);
        }

        if (this.state.keyword && this.state.keyword.trim()) {
            const kw = this.state.keyword.trim();

            domain.push(
                "|", "|", "|", "|",
                ["name", "ilike", kw],
                ["code", "ilike", kw],
                ["project_id.name", "ilike", kw],
                ["sale_order_id.name", "ilike", kw],
                ["sale_order_partner.name", "ilike", kw]
            );
        }

        return domain;
    }

    async loadData() {
        this.state.loading = true;

        const domain = this.getDomain();
        const offset = (this.state.page - 1) * this.state.pageSize;

        try {
            const totalCount = await this.orm.searchCount("cost.estimate", domain);

            const records = await this.orm.searchRead(
                "cost.estimate",
                domain,
                [
                    "name",
                    "code",
                    "project_id",
                    "sale_order_id",
                    "sale_order_partner",
                    "contract_id",

                    "signature_date",
                    "date_start",
                    "date_end",

                    "estimate_material_total",
                    "estimate_labor_total",
                    "estimate_manufacturing_total",
                    "estimate_total_breakdown",

                    "estimate_material_total_with_tax",
                    "estimate_labor_total_with_tax",
                    "estimate_manufacturing_total_with_tax",
                    "estimate_total_breakdown_with_tax",

                    "amount_additional_expense",
                    "amount_additional_expense_with_tax",

                    "total_final_non_tax",
                    "total_final_tax",

                    "state",
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
            this.notification.add("Không tải được dữ liệu dự toán.", {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async computeTotals(domain) {
        const allRecords = await this.orm.searchRead(
            "cost.estimate",
            domain,
            [
                "state",
                "total_final_non_tax",
                "total_final_tax",
                "amount_additional_expense",
                "amount_additional_expense_with_tax",
            ],
            {
                limit: 0,
            }
        );

        const totals = {
            count: allRecords.length,
            draft: 0,
            submitted: 0,
            approved: 0,
            rejected: 0,
            cancel: 0,
            totalFinalNonTax: 0,
            totalFinalTax: 0,
            additionalNonTax: 0,
            additionalWithTax: 0,
        };

        for (const rec of allRecords) {
            if (rec.state === "draft") totals.draft += 1;
            if (rec.state === "submitted") totals.submitted += 1;
            if (rec.state === "approved") totals.approved += 1;
            if (rec.state === "rejected") totals.rejected += 1;
            if (rec.state === "cancel") totals.cancel += 1;

            totals.totalFinalNonTax += rec.total_final_non_tax || 0;
            totals.totalFinalTax += rec.total_final_tax || 0;
            totals.additionalNonTax += rec.amount_additional_expense || 0;
            totals.additionalWithTax += rec.amount_additional_expense_with_tax || 0;
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

    async onChangeStateFilter(ev) {
        this.state.stateFilter = ev.target.value || "";
        this.state.page = 1;
        await this.loadData();
    }

    async resetFilters() {
        this.state.keyword = "";
        this.state.stateFilter = "";
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
        this.state.pageSize = parseInt(ev.target.value || "10");
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
            name: "Dự toán chi phí Dự án",
            res_model: "cost.estimate",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    createRecord() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tạo dự toán chi phí",
            res_model: "cost.estimate",
            views: [[false, "form"]],
            target: "current",
            context: {},
        });
    }

    openClassicList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Dự toán chi phí Dự án",
            res_model: "cost.estimate",
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

    stateLabel(state) {
        const labels = {
            draft: "Nháp",
            submitted: "Gửi duyệt",
            approved: "Đã phê duyệt",
            rejected: "Bị từ chối",
            cancel: "Hủy bỏ",
        };
        return labels[state] || state || "-";
    }

    stateBadgeClass(state) {
        const classes = {
            draft: "ce-state-badge is-draft",
            submitted: "ce-state-badge is-submitted",
            approved: "ce-state-badge is-approved",
            rejected: "ce-state-badge is-rejected",
            cancel: "ce-state-badge is-cancel",
        };
        return classes[state] || "ce-state-badge";
    }
}

registry.category("actions").add("cost_estimate_owl_list", CostEstimateList);