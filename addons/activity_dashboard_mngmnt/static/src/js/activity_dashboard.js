/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { Component, onWillStart, markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class ActivityDashboard extends Component {
    setup() {
        super.setup();
        this.userService = useService("user");
        this.orm = useService("orm");
        this.action = useService("action");

        onWillStart(async () => {
            await this.render_dashboards();
        });
    }

    async _isSystemUser() {
        return await this.orm.call("res.users", "has_group", ["base.group_system"], {});
    }

    async render_dashboards() {
        const today = luxon.DateTime.local().toISODate();
        const uid = this.userService.userId;

        const isSystem = await this._isSystemUser();
        const myDomain = isSystem ? [] : [["user_id", "=", uid]];

        // ✅ chỉ lấy trong 1 tháng gần đây
        const fromDt = luxon.DateTime.local().minus({ months: 1 }).toFormat("yyyy-MM-dd HH:mm:ss");
        const fromDate = luxon.DateTime.local().minus({ months: 1 }).toISODate();

        // Giữ activity nếu (create_date OR date_deadline OR date_done) nằm trong 1 tháng gần đây
        const timeDomain = ["|", "|",
            ["create_date", ">=", fromDt],
            ["date_deadline", ">=", fromDate],
            ["date_done", ">=", fromDt],
        ];

        const fields = [
            "id",
            "display_name",
            "summary",
            "note",
            "activity_type_id",
            "user_id",
            "create_uid",
            "date_deadline",
            "date_done",
            "res_model",
            "res_id",
            "active",
        ];

        // ✅ 1 RPC duy nhất
        const all = await this.orm.call("mail.activity", "search_read", [], {
            domain: [...myDomain, ["active", "in", [true, false]], ...timeDomain],
            fields,
            order: "date_deadline asc, id desc",
            // limit: 2000,
        });

        // phân nhóm
        const planned = [];
        const todayList = [];
        const overdue = [];
        const nodeadline = [];
        const done = [];

        for (const a of all) {
            // render HTML note
            a.note_html = markup(a.note || "");

            if (a.active === false) {
                done.push(a);
                continue;
            }

            if (!a.date_deadline) {
                nodeadline.push(a);
            } else if (a.date_deadline > today) {
                planned.push(a);
            } else if (a.date_deadline === today) {
                todayList.push(a);
            } else {
                overdue.push(a);
            }
        }

        this.len_planned = planned.length;
        this.len_today = todayList.length;
        this.len_overdue = overdue.length;
        this.len_nodeadline = nodeadline.length;
        this.len_done = done.length;
        this.len_all = all.length;

        this.planned_activity = planned;
        this.today_activity = todayList;
        this.overdue_activity = overdue;
        this.nodeadline_activity = nodeadline;
        this.done_activity = done;
    }

    // ✅ không RPC
    click_origin(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const model = ev.currentTarget.dataset.model;
        const resid = parseInt(ev.currentTarget.dataset.resid, 10);

        if (model && resid) {
            return this.action.doAction({
                type: "ir.actions.act_window",
                name: _t("Xem chi tiết"),
                res_model: model,
                res_id: resid,
                views: [[false, "form"]],
                target: "current",
            });
        }
    }

    show_all_activities(e) {
        e?.preventDefault?.();
        e?.stopPropagation?.();

        const uid = this.userService.userId;

        this._isSystemUser().then((isSystem) => {
            const domain = isSystem
                ? [["active", "in", [true, false]]]
                : [["user_id", "=", uid], ["active", "in", [true, false]]];

            return this.action.doAction({
                name: _t("All Activities"),
                type: "ir.actions.act_window",
                res_model: "mail.activity",
                view_mode: "tree,form",
                domain,
                views: [[false, "list"], [false, "form"]],
                target: "current",
            });
        });
    }
}

ActivityDashboard.template = "ActivityDashboard";
ActivityDashboard.components = { Layout };
registry.category("actions").add("activity_dashboard", ActivityDashboard);
