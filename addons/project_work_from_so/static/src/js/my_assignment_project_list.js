/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

export class MyAssignmentProjectListController extends ListController {
    async openRecord(record) {
        // record.resId là id của project.project đang click
        await this.actionService.doAction({
            type: "ir.actions.client",
            name: "Báo cáo sản lượng của tôi",
            tag: "project_work_from_so.MyAssignmentReport",
            target: "current",
            context: {
                default_project_id: record.resId,
            },
        });
    }
}

export const myAssignmentProjectListView = {
    ...listView,
    Controller: MyAssignmentProjectListController,
};

registry.category("views").add("my_assignment_project_list", myAssignmentProjectListView);

export class ManagerAssignmentProjectListController extends ListController {
    async openRecord(record) {
        await this.actionService.doAction({
            type: "ir.actions.client",
            name: "Báo cáo sản lượng quản lý",
            tag: "project_work_from_so.MyAssignmentReport",
            target: "current",
            context: {
                default_project_id: record.resId,
                manager_mode: true,
            },
        });
    }
}

export const managerAssignmentProjectListView = {
    ...listView,
    Controller: ManagerAssignmentProjectListController,
};

registry.category("views").add("manager_assignment_project_list", managerAssignmentProjectListView);