/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ProjectTaskGantt extends Component {
  setup() {
    this.orm = useService("orm");
    this.state = useState({ items: [] });

    onWillStart(async () => {
      this.state.items = await this.loadProjectsAndTasks();
    });
    onMounted(() => {
      this.renderGantt();
    });
  }

  async loadProjectsAndTasks() {
    // 1. Lấy project
    const projects = await this.orm.searchRead(
      "project.project",
      [],
      ["name", "date_start", "date"]
    );

    // 2. Lấy task
    const tasks = await this.orm.searchRead(
      "project.task",
      [],
      ["name", "create_date", "date_deadline", "progress", "project_id"],
      { order: "date_deadline asc, create_date asc" }
    );

    // 3. Build dạng parent/child
    const items = [];

    // projects
    for (const p of projects) {
      const start = p.date_start ? p.date_start.split(" ")[0] : null;
      const end = p.date ? p.date.split(" ")[0] : start;

      let duration = 1;
      if (start && end) {
        const startDate = new Date(start);
        const endDate = new Date(end);
        duration = Math.max(
          1,
          Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24))
        );
      }

      items.push({
        id: "p" + p.id,
        text: p.name,
        type: "project",
        start_date: start,
        duration: duration,
        open: true,
      });
    }

    // tasks
    for (const r of tasks) {
      const start = r.create_date.split(" ")[0];
      const end = (r.date_deadline || r.create_date).split(" ")[0];
      const startDate = new Date(start);
      const endDate = new Date(end);
      const duration = Math.max(
        1,
        Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24))
      );

      items.push({
        id: "t" + r.id,
        text: r.name,
        start_date: start,
        duration: duration,
        progress: (r.progress || 0) / 100,
        parent: "p" + (r.project_id?.[0] || ""), // gán vào project
      });
    }

    return items;
  }

  renderGantt() {
    if (!this.state.items.length || !window.gantt) return;

    gantt.config.date_format = "%Y-%m-%d";
    gantt.setSkin("terrace");
    gantt.config.autosize = false;

    gantt.init("gantt");
    gantt.parse({ data: this.state.items });

    gantt.plugins({
      click_drag: true,
      quick_info: true,
      tooltip: true,
      multiselect: true,
    });
  }
}

ProjectTaskGantt.template = "ProjectTaskGantt";

registry.category("actions").add("project_task_gantt", ProjectTaskGantt);
