/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

export class MyFinalizationProjectListController extends ListController {
    async openRecord(record) {
        await this.actionService.doAction({
            type: "ir.actions.client",
            name: "Báo cáo thanh/quyết toán của tôi",
            tag: "project_work_finalization_report.FinalizationReport",
            target: "current",
            context: {
                default_project_id: record.resId,
                manager_mode: false,
            },
        });
    }
}

export const myFinalizationProjectListView = {
    ...listView,
    Controller: MyFinalizationProjectListController,
};

registry.category("views").add("my_finalization_project_list", myFinalizationProjectListView);

export class ManagerFinalizationProjectListController extends ListController {
    async openRecord(record) {
        await this.actionService.doAction({
            type: "ir.actions.client",
            name: "Báo cáo thanh/quyết toán quản lý",
            tag: "project_work_finalization_report.FinalizationReport",
            target: "current",
            context: {
                default_project_id: record.resId,
                manager_mode: true,
            },
        });
    }
}

export const managerFinalizationProjectListView = {
    ...listView,
    Controller: ManagerFinalizationProjectListController,
};

registry.category("views").add("manager_finalization_project_list", managerFinalizationProjectListView);