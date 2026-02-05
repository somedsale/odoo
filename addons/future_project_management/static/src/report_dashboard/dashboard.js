/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FutureProjectDashboard extends Component {
    static template = "future_project_management.FutureProjectDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // ✅ tránh crash nếu repo chưa load (nhưng khi assets đúng thì sẽ có)
        this.repo = null;
        try {
            this.repo = useService("future_project_dashboard_repo");
        } catch (e) {
            console.warn("[FP_DASH] repo service missing, fallback orm.call()", e);
        }

        const today = new Date();
        const month = String(today.getMonth() + 1);

        const now = new Date();
        const currentYear = now.getFullYear();
        const fromYear = currentYear - 5;
        const toYear = currentYear + 10;
        const yearOptions = [];
        for (let y = toYear; y >= fromYear; y--) yearOptions.push(y);

        this.state = useState({
            loading: true,
            data: {
                meta: { start_date: null, end_date: null, period_type: "all" },
                kpi: {},
                stage_summary: [],
                location_summary: [],
                projects: [],
                location_options: [],
                stage_options: [],
            },
            locationOptions: [],
            stageOptions: [],
            yearOptions: yearOptions,
            monthOptions: Array.from({ length: 12 }, (_, i) => ({
                value: String(i + 1),
                label: `Tháng ${i + 1}`,
            })),
            filters: {
                period_type: "all",
                year: today.getFullYear(),
                month,
                quarter: String(Math.floor(today.getMonth() / 3) + 1),
                location_id: "",
            },
            listFilters: {
                stage_id: "",
            },
            metaText: "",
            stageHint: "Đang hiển thị tất cả trạng thái",
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    percentOf(v, total) {
        const t = total || 0;
        if (!t) return "0.00";
        return ((v / t) * 100).toFixed(2);
    }

    formatMoney(amount) {
        const v = Number(amount || 0);
        return v.toLocaleString("vi-VN");
    }

    formatDate(d) {
        if (!d) return "-";
        const s = String(d);
        const parts = s.split("-");
        if (parts.length !== 3) return s;
        const [y, m, day] = parts;
        return `${day}/${m}/${y}`;
    }

    buildMetaText(meta) {
        if (!meta?.start_date || !meta?.end_date) {
            return "Đang hiển thị: tất cả dự án (kể cả không khả thi)";
        }
        const s = this.formatDate(meta.start_date);
        const e = this.formatDate(meta.end_date);
        return `Kỳ: ${s} - ${e}`;
    }

    _buildPayload() {
        const payload = {
            ...this.state.filters,
            list_stage_id: this.state.listFilters.stage_id || "",
        };
        if (!payload.location_id) delete payload.location_id;
        if (!payload.list_stage_id) delete payload.list_stage_id;
        return payload;
    }

    async _fetchDashboardData(payload) {
        if (this.repo?.getDashboardData) {
            return await this.repo.getDashboardData(payload);
        }
        return await this.orm.call("future.project", "get_dashboard_data", [payload]);
    }

    async loadData() {
        this.state.loading = true;
        try {
            const payload = this._buildPayload();
            const data = await this._fetchDashboardData(payload);

            this.state.data = data;
            this.state.locationOptions = data.location_options || [];
            this.state.stageOptions = data.stage_options || [];
            this.state.metaText = this.buildMetaText(data.meta);

            this.state.stageHint = this.state.listFilters.stage_id
                ? "Đang lọc danh sách theo trạng thái"
                : "Danh sách: tất cả trạng thái";
        } catch (e) {
            this.notification.add("Không tải được dữ liệu dashboard. Kiểm tra log server.", { type: "danger" });
            console.error(e);
        } finally {
            this.state.loading = false;
        }
    }

    async onApply() {
        await this.loadData();
    }

    async onPickStageClick(ev) {
        const stageId = ev.currentTarget.dataset.stageId || "";
        this.state.listFilters.stage_id = stageId;
        await this.loadData();
    }

    async onOpenListAll() {
        const domain = this._buildDomainBase();
        await this._openFutureProjectKanban(domain);
    }

    async onOpenListFromList() {
        const domain = this._buildDomainForList();
        await this._openFutureProjectKanban(domain);
    }

    async onOpenForm(ev) {
        const id = parseInt(ev.currentTarget.dataset.projectId || "0", 10);
        if (!id) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "future.project",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
            context: { active_test: false },
        });
    }

    async _openFutureProjectKanban(domain, extraContext = {}) {
        const action = {
            type: "ir.actions.act_window",
            name: "Dự án tiềm năng",
            res_model: "future.project",
            view_mode: "kanban,tree,form",
            views: [[false, "kanban"], [false, "tree"], [false, "form"]],
            target: "current",
            domain: domain || [],
            context: {
                ...(this.env.searchModel?.context || {}),
                ...extraContext,
                search_default_group_by_stage_id: 1,
                default_group_by: "stage_id",
            },
        };
        await this.action.doAction(action);
    }

    async onOpenListByStage(ev) {
        const sid = parseInt(ev.currentTarget.dataset.stageId || "0", 10);
        const domain = this._buildDomainBase();
        if (sid) domain.push(["stage_id", "=", sid]);

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Dự án theo trạng thái",
            res_model: "future.project",
            views: [[false, "list"], [false, "form"], [false, "kanban"]],
            target: "current",
            domain,
            context: { active_test: false },
        });
    }

    async onOpenListByLocation(ev) {
        const locationId = parseInt(ev.currentTarget.dataset.locationId || "0", 10);
        const domain = this._buildDomainBase();
        if (locationId) domain.push(["location_id", "=", locationId]);
        await this._openFutureProjectKanban(domain);
    }

    _buildDomainBase() {
        const meta = this.state.data?.meta || {};
        const domain = [];

        if (meta.start_date) domain.push(["expected_bid_date", ">=", meta.start_date]);
        if (meta.end_date) domain.push(["expected_bid_date", "<=", meta.end_date]);

        if (this.state.filters.location_id) {
            domain.push(["location_id", "=", parseInt(this.state.filters.location_id, 10)]);
        }
        return domain;
    }

    _buildDomainForList() {
        const domain = this._buildDomainBase();

        domain.push(["active", "=", true]);

        const lostStages = (this.state.stageOptions || []).filter(
            (s) => (s.name || "").toLowerCase().trim() === "không khả thi"
        );
        if (lostStages.length) {
            domain.push(["stage_id", "not in", lostStages.map((s) => s.id)]);
        }

        if (this.state.listFilters.stage_id) {
            domain.push(["stage_id", "=", parseInt(this.state.listFilters.stage_id, 10)]);
        }
        return domain;
    }
}

registry.category("actions").add("future_project_dashboard", FutureProjectDashboard);
