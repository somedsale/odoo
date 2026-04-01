/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

export class ProjectInvoiceStandardScreen extends Component {
  static template = "project_work_from_so.ProjectInvoiceStandardScreen";
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
      disbursementFormViewId: null,
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

      const viewIds = await this.orm.search("ir.ui.view", [
        ["model", "=", "project.project"],
        ["name", "=", "project.project.disbursement.form"],
      ]);

      const formViewId = viewIds?.length ? viewIds[0] : false;
      this.state.disbursementFormViewId = formViewId || false;

      this.state.embeddedViewProps = {
        type: "form",
        resModel: "project.project",
        resId: projectId,
        mode: "readonly",
        context: {},
        display: {
          controlPanel: true,
        },
        viewId: formViewId || undefined,
      };
    } catch (e) {
      console.error("[ProjectInvoiceStandardScreen] loadData error:", e);
      this.notification.add("Không tải được form Giải ngân dự án.", {
        type: "danger",
      });
    } finally {
      this.state.loading = false;
    }
  }
}