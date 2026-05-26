/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class BidProjectListAction extends Component {
    static template = "bid_estimation.BidProjectListAction";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            projects: [],
            searchText: "",
            viewMode: "card",
            projectFormOpen: false,
            editingProjectId: false,
            projectForm: { name: "", note: "" },
        });

        onWillStart(async () => {
            await this.loadProjects();
            this.state.loading = false;
        });
    }

    async loadProjects() {
        this.state.projects = await this.orm.searchRead(
            "bid.project",
            [],
            [
                "name",
                "note",
                "amount_total",
                "supplier_best_amount_total",
                "saving_amount_total",
                "section_count",
                "line_count",
                "supplier_quote_count",
                "create_date",
                "write_date",
            ],
            { order: "id desc", limit: 120 }
        );
    }

    async refresh() {
        await this.loadProjects();
        this.notification.add("Đã tải lại danh sách dự án.", { type: "success" });
    }

    onSearch(ev) {
        this.state.searchText = ev.target.value || "";
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
    }

    get filteredProjects() {
        const keyword = (this.state.searchText || "").toLowerCase().trim();
        if (!keyword) {
            return this.state.projects;
        }
        return this.state.projects.filter((project) => {
            const text = `${project.name || ""} ${project.note || ""}`.toLowerCase();
            return text.includes(keyword);
        });
    }

    get totalAmount() {
        return this.filteredProjects.reduce((sum, project) => sum + (project.amount_total || 0), 0);
    }

    get totalBestAmount() {
        return this.filteredProjects.reduce((sum, project) => sum + (project.supplier_best_amount_total || 0), 0);
    }

    get totalSavingAmount() {
        return this.filteredProjects.reduce((sum, project) => sum + (project.saving_amount_total || 0), 0);
    }


    openEditProject(project) {
        if (!project) return;
        this.state.projectFormOpen = true;
        this.state.editingProjectId = project.id;
        this.state.projectForm = {
            name: project.name || "",
            note: project.note || "",
        };
    }

    cancelProjectForm() {
        this.state.projectFormOpen = false;
        this.state.editingProjectId = false;
        this.state.projectForm = { name: "", note: "" };
    }

    async saveProject() {
        const name = (this.state.projectForm.name || "").trim();
        if (!name) {
            this.notification.add("Vui lòng nhập tên dự toán dự thầu.", { type: "warning" });
            return;
        }
        if (!this.state.editingProjectId) return;
        await this.orm.write("bid.project", [this.state.editingProjectId], {
            name,
            note: this.state.projectForm.note || false,
        });
        this.notification.add("Đã cập nhật tên dự toán dự thầu.", { type: "success" });
        this.cancelProjectForm();
        await this.loadProjects();
    }

    async deleteProject(project) {
        if (!project) return;
        const ok = window.confirm(`Xóa dự toán dự thầu "${project.name || ""}"? Toàn bộ hạng mục, vật tư và báo giá NCC thuộc dự án này cũng sẽ bị xóa.`);
        if (!ok) return;
        await this.orm.unlink("bid.project", [project.id]);
        this.notification.add("Đã xóa dự toán dự thầu.", { type: "success" });
        if (this.state.editingProjectId === project.id) {
            this.cancelProjectForm();
        }
        await this.loadProjects();
    }

    openProject(project) {
        if (!project) return;
        this.action.doAction({
            type: "ir.actions.client",
            name: project.name,
            tag: "bid_estimation_project_view_action",
            target: "current",
            params: { project_id: project.id },
        });
    }

    openImport() {
        this.action.doAction({
            type: "ir.actions.client",
            name: "Import Excel dự thầu",
            tag: "bid_estimation_import_action",
            target: "current",
        });
    }

    openProjectForm(project) {
        if (!project) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Dự án dự thầu",
            res_model: "bid.project",
            res_id: project.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
    openExportExcel(project) {
        if (!project) return;
        window.open(`/bid_estimation/export_excel/${project.id}`, "_blank");
    }


    openBackendList() {
        this.action.doAction("bid_estimation.action_bid_project");
    }

    formatMoney(value) {
        return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value || 0);
    }

    formatDateTime(value) {
        if (!value) return "";
        const date = new Date(value.replace(" ", "T"));
        if (Number.isNaN(date.getTime())) return value;
        return new Intl.DateTimeFormat("vi-VN", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        }).format(date);
    }
}

registry.category("actions").add("bid_estimation_project_list_action", BidProjectListAction);
