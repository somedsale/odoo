/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

export class ProjectExpenseStandardScreen extends Component {
  static template = "project_work_from_so.ProjectExpenseStandardScreen";
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
      expenseId: null,
      embeddedViewProps: null,
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

      const [project] = await this.orm.read("project.project", [projectId], [
        "name",
      ]);
      this.state.projectName = project?.name || "";

      const expenseIds = await this.orm.search("project.expense.custom", [
        ["project_id", "=", projectId],
      ]);

      let expenseId = expenseIds?.length ? expenseIds[0] : null;

      if (!expenseId) {
        expenseId = await this.orm.create("project.expense.custom", [
          {
            project_id: projectId,
            name: this.state.projectName
              ? `Chi phí - ${this.state.projectName}`
              : "Chi phí dự án",
          },
        ]);
      }

      this.state.expenseId = expenseId;

      this.state.embeddedViewProps = {
        type: "form",
        resModel: "project.expense.custom",
        resId: expenseId,
        mode: "edit",
        context: {
          default_project_id: projectId,
        },
        display: {
          controlPanel: true,
        },
      };
    } catch (e) {
      console.error("[ProjectExpenseStandardScreen] loadData error:", e);
      this.notification.add("Không tải được form chuẩn Chi phí dự án.", {
        type: "danger",
      });
    } finally {
      this.state.loading = false;
    }
  }
}