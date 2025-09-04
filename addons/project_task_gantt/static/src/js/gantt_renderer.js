/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
  Component,
  onWillStart,
  onMounted,
  useState,
  onWillUnmount,
} from "@odoo/owl";
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
      this.keyHandler = (e) => {
        if (e.ctrlKey && e.key === "z") {
          gantt.undo();
        }
        if (e.ctrlKey && e.key === "y") {
          gantt.redo();
        }
      };
      document.addEventListener("keydown", this.keyHandler);
    });
    onWillUnmount(() => {
      // Cleanup tránh leak memory
      if (this.keyHandler) {
        document.removeEventListener("keydown", this.keyHandler);
      }
    });
  }

  async loadProjectsAndTasks() {
    // 1. Lấy project
    const projects = await this.orm.searchRead(
      "project.project",
      [["id", "!=", 4]],
      ["name", "date_start", "date"]
    );

    // 2. Lấy task (dùng completion_percent)
    const tasks = await this.orm.searchRead(
      "project.task",
      [["project_id", "!=", 4]],
      [
        "name",
        "create_date",
        "date_deadline",
        "completion_percent",
        "project_id",
      ],
      { order: "date_deadline asc, create_date asc" }
    );

    const items = [];
    const projectTasks = {}; // map project_id -> list tasks

    // Gom task theo project
    for (const r of tasks) {
      if (!projectTasks[r.project_id?.[0]]) {
        projectTasks[r.project_id?.[0]] = [];
      }
      projectTasks[r.project_id?.[0]].push(r);
    }

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

      // Tính progress trung bình từ task con
      let progress = 0;
      const childTasks = projectTasks[p.id] || [];
      if (childTasks.length) {
        const sum = childTasks.reduce(
          (acc, t) => acc + (t.completion_percent || 0),
          0
        );
        progress = sum / childTasks.length / 100; // convert về 0–1
      }

      items.push({
        id: "p" + p.id,
        text: p.name,
        type: "project",
        start_date: start,
        duration: duration,
        progress: progress,
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
        id: r.id,
        text: r.name,
        start_date: start,
        duration: duration,
        progress: (r.completion_percent || 0) / 100, // dùng completion_percent
        parent: "p" + (r.project_id?.[0] || ""),
      });
    }

    return items;
  }

  renderGantt() {
    if (!this.state.items.length || !window.gantt) return;

    gantt.config.date_format = "%Y-%m-%d";
    gantt.config.columns = [
      { name: "text", label: "Dự án / Nhiệm vụ", tree: true, width: 200 },
      {
        name: "start_date",
        label: "Ngày bắt đầu",
        align: "center",
        width: 100,
      },
      { name: "duration", label: "Số ngày", align: "center", width: 55 },
      {
        name: "progress",
        label: "Tiến độ",
        align: "center",
        template: (task) => {
          return Math.round((task.progress || 0) * 100) + "%";
        },
        width: 55,
      },
      { name: "add", label: "", width: 50 },
    ];
    gantt.templates.task_class = function (start, end, task) {
      if (task.type === "project") {
        return "gantt-project";
      }
      if (task.completion_percent === 100) {
        return "gantt-done";
      }
      if (end < new Date()) {
        return "gantt-late";
      }
      return "gantt-task";
    };
    gantt.config.scales = [
      { unit: "year", step: 1, format: "%Y" }, // cấp 1: Năm
      { unit: "month", step: 1, format: "%M" }, // cấp 2: Tháng
      { unit: "day", step: 1, format: "%d %M" }, // cấp 3: Ngày
    ];

    gantt.config.subscales = []; // xóa subscale mặc định nếu có
    gantt.config.scale_height = 60; //
    gantt.attachEvent("onAfterTaskUpdate", async (id, task) => {
      // Chỉ xử lý task, bỏ qua project
      if (task.type === "project") return;

      // Cập nhật Odoo
      await this.orm.write("project.task", [id], {
        name: task.text,
        completion_percent: Math.round((task.progress || 0) * 100),
        date_deadline: gantt.date.date_to_str("%Y-%m-%d")(task.end_date),
      });
      console.log("✅ Task updated in Odoo:", task.text);
    });

    // --- Đồng bộ Delete ---
    gantt.attachEvent("onBeforeTaskDelete", async (id, task) => {
      if (task.type === "project") return true; // cho phép xóa project bình thường trên UI (không đụng Odoo)

      try {
        await this.orm.unlink("project.task", [id]);
        console.log("🗑️ Task deleted in Odoo:", task.text);
        return true; // cho phép xóa trong Gantt
      } catch (e) {
        console.error("❌ Lỗi khi xóa task:", e);
        return false; // chặn xóa trên Gantt nếu backend fail
      }
    });

    gantt.init("gantt");
    gantt.parse({ data: this.state.items });

    gantt.plugins({
      click_drag: true,
      quick_info: true,
      tooltip: true,
      multiselect: true,
      undo: true,
    });
    gantt.config.undo = true;
    gantt.config.undo_steps = 20; // số bước lưu lại
    gantt.config.undo_select = true; // giữ selection s
  }
}

ProjectTaskGantt.template = "ProjectTaskGantt";

registry.category("actions").add("project_task_gantt", ProjectTaskGantt);
