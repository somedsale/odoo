/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

export class CostEstimateStandardScreen extends Component {
  static template = "project_work_from_so.CostEstimateStandardScreen";
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
      costEstimateId: null,
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

      const estimateIds = await this.orm.search("cost.estimate", [
        ["project_id", "=", projectId],
      ]);

      let estimateId = estimateIds?.length ? estimateIds[0] : null;

      if (!estimateId) {
        estimateId = await this.orm.create("cost.estimate", [
          {
            project_id: projectId,
            name: this.state.projectName
              ? `Dự toán - ${this.state.projectName}`
              : "Dự toán chi phí",
          },
        ]);
      }

      this.state.costEstimateId = estimateId;

      this.state.embeddedViewProps = {
        type: "form",
        resModel: "cost.estimate",
        resId: estimateId,
        mode: "edit",
        context: {
          default_project_id: projectId,
        },
        display: {
          controlPanel: true,
        },
      };
    } catch (e) {
      console.error("[CostEstimateStandardScreen] loadData error:", e);
      this.notification.add("Không tải được form chuẩn Dự toán chi phí.", {
        type: "danger",
      });
    } finally {
      this.state.loading = false;
    }
  }
}