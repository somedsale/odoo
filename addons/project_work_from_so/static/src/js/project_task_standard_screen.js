/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

export class ProjectTaskStandardScreen extends Component {
  static template = "project_work_from_so.ProjectTaskStandardScreen";
  static components = { View };
  static props = {
    projectId: { type: Number, optional: true },
    onBack: { type: Function, optional: true },
  };

  setup() {
    this.orm = useService("orm");
    this.notification = useService("notification");

    this.state = useState({
      loading: true,
      projectName: "",
      embeddedViewProps: null,
      taskAction: null,
    });

    onWillStart(async () => {
      await this.loadData();
    });
  }

  async loadData() {
    const projectId = Number(this.props.projectId || 0);
    if (!projectId) {
      this.state.loading = false;
      return;
    }

    try {
      this.state.loading = true;

      const [project] = await this.orm.read("project.project", [projectId], ["name"]);
      this.state.projectName = project?.name || "";

      const action = await this.orm.call(
        "project.project",
        "action_view_tasks_custom",
        [[projectId]]
      );

      this.state.taskAction = action || null;

      const domain = action?.domain || [["project_id", "=", projectId]];
      const context = action?.context || { default_project_id: projectId };
      const views = Array.isArray(action?.views) ? action.views : [];
      const formView = views.find((v) => v[1] === "form");
      const listView = views.find((v) => v[1] === "list" || v[1] === "tree");

      this.state.embeddedViewProps = {
        type: "list",
        resModel: action?.res_model || "project.task",
        domain,
        context,
        display: {
          controlPanel: true,
        },
        searchMenuTypes: ["filter", "groupBy", "favorite"],
        viewId: listView?.[0] || undefined,
        views: views.length ? views : undefined,
        formViewId: formView?.[0] || undefined,
      };
    } catch (e) {
      console.error("[ProjectTaskStandardScreen] loadData error:", e);
      this.notification.add("Không tải được danh sách nhiệm vụ.", {
        type: "danger",
      });
    } finally {
      this.state.loading = false;
    }
  }
}