/** @odoo-module **/

import { registry } from "@web/core/registry";

const serviceRegistry = registry.category("services");

serviceRegistry.add("project_work_item_assignment_notification_handler", {
    dependencies: ["bus_service", "notification", "action"],
    start(env, { bus_service, notification, action }) {
        bus_service.addEventListener("notification", ({ detail: notifications }) => {
            for (const item of notifications) {
                const { type, payload } = item || {};
                if (type !== "project_work_item_assignment_notification") {
                    continue;
                }

                const title = payload?.title || "Thông báo";
                const message = payload?.message || "";
                const nextAction = payload?.next_action || null;
                const sticky = !!payload?.sticky;

                notification.add(message, {
                    title,
                    type: "info",
                    sticky,
                    buttons: nextAction
                        ? [
                              {
                                  name: "Mở báo cáo",
                                  primary: true,
                                  onClick: () => action.doAction(nextAction),
                              },
                          ]
                        : [],
                });
            }
        });

        return {};
    },
});