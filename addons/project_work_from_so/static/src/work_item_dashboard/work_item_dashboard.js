/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

function clamp(n, min, max) {
    n = Number(n || 0);
    return Math.max(min, Math.min(max, n));
}

export class WorkItemManagerDashboard extends Component {
    static template = "project_work_from_so.WorkItemManagerDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            query: "",
            onlyActive: true,
            onlyNotDone: false,
            groupByProject: true,
            limit: 300,

            // computed
            projects: [],      // [{projectId, projectName, items:[], kpi:{...}, expanded:true}]
            totals: { items: 0, qty_plan: 0, qty_done: 0, avg_progress: 0 },

            // ui
            expanded: {},      // projectId -> bool
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    _domain() {
        const domain = [];
        if (this.state.onlyActive) {
            domain.push(["active", "=", true]);
        }
        if (this.state.onlyNotDone) {
            domain.push(["progress_percent", "<", 100]);
        }
        if (this.state.query && this.state.query.trim()) {
            const q = this.state.query.trim();
            domain.push(["name", "ilike", q]);
        }
        return domain;
    }

    async load() {
        try {
            this.state.loading = true;

            const fields = [
                "name",
                "project_id",
                "product_id",
                "qty_plan",
                "qty_done",
                "qty_remaining",
                "progress_percent",
                "active",
                "assigned_user_ids",
                "price_subtotal",
                "value_completed",
                "value_remaining",
            ];

            const records = await this.orm.searchRead(
                "project.work.item",
                this._domain(),
                fields,
                {
                    limit: this.state.limit,
                    order: "project_id asc, id asc",
                }
            );

            // Group by project
            const byProject = new Map();
            for (const r of records) {
                const proj = r.project_id; // [id, name] or false
                const projectId = proj ? proj[0] : 0;
                const projectName = proj ? proj[1] : "Không có dự án";

                if (!byProject.has(projectId)) {
                    byProject.set(projectId, {
                        projectId,
                        projectName,
                        items: [],
                        kpi: { items: 0, qty_plan: 0, qty_done: 0, avg_progress: 0 },
                    });
                }

                // tránh lỗi undefined array (m2m)
                r.assigned_user_ids = Array.isArray(r.assigned_user_ids) ? r.assigned_user_ids : [];

                byProject.get(projectId).items.push(r);
            }

            const projects = Array.from(byProject.values()).map((p) => {
                let plan = 0;
                let done = 0;
                let count = p.items.length;
                let sumProgress = 0;

                for (const it of p.items) {
                    plan += Number(it.qty_plan || 0);
                    done += Number(it.qty_done || 0);
                    sumProgress += Number(it.progress_percent || 0);
                }

                p.kpi.items = count;
                p.kpi.qty_plan = plan;
                p.kpi.qty_done = done;
                p.kpi.avg_progress = count ? (sumProgress / count) : 0;

                // expanded default: true (hoặc giữ theo state.expanded)
                const saved = this.state.expanded[p.projectId];
                p.expanded = (saved === undefined) ? true : !!saved;

                return p;
            });

            // totals
            let tItems = records.length;
            let tPlan = 0;
            let tDone = 0;
            let tSumProgress = 0;

            for (const r of records) {
                tPlan += Number(r.qty_plan || 0);
                tDone += Number(r.qty_done || 0);
                tSumProgress += Number(r.progress_percent || 0);
            }

            this.state.projects = projects;
            this.state.totals = {
                items: tItems,
                qty_plan: tPlan,
                qty_done: tDone,
                avg_progress: tItems ? (tSumProgress / tItems) : 0,
            };
        } catch (e) {
            this.notification.add(
                "Không tải được dữ liệu dashboard. Kiểm tra quyền hoặc model/field.",
                { type: "danger" }
            );
            // console for debug
            console.error("[WorkItemDashboard] load error:", e);
        } finally {
            this.state.loading = false;
        }
    }

    async onRefresh() {
        await this.load();
    }

    async onToggleActive(ev) {
        this.state.onlyActive = !!ev.target.checked;
        await this.load();
    }

    async onToggleNotDone(ev) {
        this.state.onlyNotDone = !!ev.target.checked;
        await this.load();
    }

    async onQueryInput(ev) {
        this.state.query = ev.target.value || "";
        // debounce nhẹ
        clearTimeout(this._qTimer);
        this._qTimer = setTimeout(() => this.load(), 300);
    }

toggleProject(ev) {
    const projectId = Number(ev.currentTarget?.dataset?.projectId || 0);

    const current = this.state.expanded[projectId];
    const next = !(current === undefined ? true : current);

    this.state.expanded[projectId] = next;

    const p = this.state.projects.find(x => x.projectId === projectId);
    if (p) p.expanded = next;
}

    openWorkItem(ev) {
        const id = Number(ev.currentTarget?.dataset?.workItemId || 0);
        if (!id) return;

        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.work.item",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openProject(ev) {
        const projectId = Number(ev.currentTarget?.dataset?.projectId || 0);
        if (!projectId) return;

        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.project",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }


    progressWidth(pct) {
        // cho đẹp: clamp 0..200 (vì bạn cho phép >100%)
        return `${clamp(pct, 0, 200)}%`;
    }
}

registry.category("actions").add("project_work_item_manager_dashboard", WorkItemManagerDashboard);
