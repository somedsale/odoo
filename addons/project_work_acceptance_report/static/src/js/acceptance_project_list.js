/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

export class MyAcceptanceProjectListController extends ListController {
    async openRecord(record) {
        await this.actionService.doAction({
            type: "ir.actions.client",
            name: "Báo cáo nghiệm thu của tôi",
            tag: "project_work_acceptance_report.AcceptanceReport",
            target: "current",
            context: {
                default_project_id: record.resId,
                manager_mode: false,
            },
        });
    }
}

export const myAcceptanceProjectListView = {
    ...listView,
    Controller: MyAcceptanceProjectListController,
};

registry.category("views").add("my_acceptance_project_list", myAcceptanceProjectListView);

export class ManagerAcceptanceProjectListController extends ListController {
    async openRecord(record) {
        await this.actionService.doAction({
            type: "ir.actions.client",
            name: "Báo cáo nghiệm thu quản lý",
            tag: "project_work_acceptance_report.AcceptanceReport",
            target: "current",
            context: {
                default_project_id: record.resId,
                manager_mode: true,
            },
        });
    }
}

export const managerAcceptanceProjectListView = {
    ...listView,
    Controller: ManagerAcceptanceProjectListController,
};

registry.category("views").add("manager_acceptance_project_list", managerAcceptanceProjectListView);