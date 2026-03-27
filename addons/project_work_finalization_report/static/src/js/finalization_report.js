/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

export class FinalizationReport extends Component {
    static template = "project_work_finalization_report.FinalizationReport";
    static components = { View };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        const actionContext = this.props.action?.context || {};
        const contextProjectId = actionContext.default_project_id || null;

        const storedProjectId = window.sessionStorage.getItem("finalization_project_id");
        const storedSelectedPeriod = window.sessionStorage.getItem("finalization_selected_period");
        const storedManagerMode = window.sessionStorage.getItem("finalization_manager_mode");

        const projectId = contextProjectId || (storedProjectId ? Number(storedProjectId) : null);

        let managerMode;
        if (typeof actionContext.manager_mode !== "undefined") {
            managerMode = !!actionContext.manager_mode;
        } else {
            managerMode = storedManagerMode === "true";
        }

        this.state = useState({
            loading: true,
            saving: false,
            projectId,
            managerMode,
            project: {},
            assignableUsers: [],
            projectAssignUserId: null,
            availablePeriods: [],
            currentPeriodNo: 0,
            selectedPeriod: storedSelectedPeriod ? Number(storedSelectedPeriod) : null,
            rowsByPeriod: {},
            embeddedFormKey: 0,
        });

        if (this.state.projectId) {
            window.sessionStorage.setItem("finalization_project_id", String(this.state.projectId));
        }
        window.sessionStorage.setItem(
            "finalization_manager_mode",
            this.state.managerMode ? "true" : "false"
        );

        onWillStart(async () => {
            if (this.state.managerMode) {
                await this.syncWorkItemsFromSO(false);
            }
            await this.loadData();
        });
    }

    get embeddedProjectFormProps() {
        if (!this.state.projectId) {
            return null;
        }

        return {
            type: "form",
            resModel: "project.project",
            resId: this.state.projectId,
            context: {
                ...(this.props.action?.context || {}),
                form_view_ref:
                    "project_work_from_so.view_project_project_form_chatter_only",
            },
            display: {
                controlPanel: false,
            },
            mode: "edit",
        };
    }

    async syncWorkItemsFromSO(showNotice = true) {
        if (!this.state.projectId) return;
        try {
            await this.orm.call("project.project", "action_sync_work_items_from_so", [[this.state.projectId]]);
            if (showNotice) {
                this.notification.add("Đã đồng bộ hạng mục từ đơn bán.", { type: "success" });
            }
        } catch (error) {
            console.error(error);
            if (showNotice) {
                this.notification.add("Không thể đồng bộ hạng mục từ đơn bán.", { type: "warning" });
            }
        }
    }

    async loadData() {
        if (!this.state.projectId) {
            this.notification.add("Không tìm thấy dự án để nhập thanh/quyết toán.", { type: "warning" });
            this.state.loading = false;
            return;
        }

        window.sessionStorage.setItem("finalization_project_id", String(this.state.projectId));
        window.sessionStorage.setItem(
            "finalization_manager_mode",
            this.state.managerMode ? "true" : "false"
        );

        this.state.loading = true;
        try {
            const result = await this.orm.call(
                "project.project",
                "get_finalization_report_rows",
                [[this.state.projectId], this.state.managerMode]
            );

            this.state.project = result.project || {};
            this.state.assignableUsers = result.assignable_users || [];
            this.state.availablePeriods = result.available_periods || [];
            this.state.currentPeriodNo = result.current_period_no || 0;
            this.state.rowsByPeriod = {};

            for (const [periodKey, rows] of Object.entries(result.rows_by_period || {})) {
                this.state.rowsByPeriod[periodKey] = rows.map((row) => ({
                    ...row,
                    _dirty: false,
                }));
            }

            this.state.projectAssignUserId = this.state.project.finalization_user_id || null;

            const available = this.state.availablePeriods || [];
            this.state.selectedPeriod = available.length ? available[available.length - 1] : null;

            if (this.state.selectedPeriod) {
                window.sessionStorage.setItem(
                    "finalization_selected_period",
                    String(this.state.selectedPeriod)
                );
            } else {
                window.sessionStorage.removeItem("finalization_selected_period");
            }

            this.state.embeddedFormKey += 1;
        } catch (error) {
            console.error(error);
            this.notification.add("Không tải được dữ liệu báo cáo thanh/quyết toán.", { type: "danger" });
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    get selectedRows() {
        if (!this.state.selectedPeriod) return [];
        return this.state.rowsByPeriod[String(this.state.selectedPeriod)] || [];
    }

    get isReadonlyPeriod() {
        if (this.state.project?.is_completed) return true;
        return Number(this.state.selectedPeriod) !== Number(this.state.currentPeriodNo);
    }

    get groupedSelectedRows() {
        const rows = this.selectedRows || [];
        const groups = [];
        const map = new Map();

        for (const row of rows) {
            const sectionName = (row.section_name || "").trim() || "Khác";
            if (!map.has(sectionName)) {
                const group = { section_name: sectionName, rows: [] };
                map.set(sectionName, group);
                groups.push(group);
            }
            map.get(sectionName).rows.push(row);
        }

        return groups;
    }

    formatNumber(value, digits = 2) {
        const number = Number(value || 0);
        return new Intl.NumberFormat("vi-VN", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(number);
    }

    formatQty(value) {
        return this.formatNumber(value, 2);
    }

    formatMoney(value) {
        return this.formatNumber(value, 0);
    }

    formatDate(value) {
        if (!value) return "";
        const parts = String(value).split("-");
        return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : value;
    }

    onPeriodChange(ev) {
        this.state.selectedPeriod = Number(ev.target.value);
        if (this.state.selectedPeriod) {
            window.sessionStorage.setItem(
                "finalization_selected_period",
                String(this.state.selectedPeriod)
            );
        }
    }

onQtyInput(row, ev) {
    if (this.isReadonlyPeriod || !row.is_editable) return;

    let value = parseFloat(ev.target.value || 0);
    if (isNaN(value) || value < 0) value = 0;

    const prevQty = Math.max(0, Number(row.prev_qty_cum || 0));
    const acceptedQty = Math.max(0, Number(row.accepted_qty || 0));

    // Không cho QT lũy kế vượt quá khối lượng đã nghiệm thu
    const maxCurrentQty = Math.max(0, acceptedQty - prevQty);
    if (value > maxCurrentQty) {
        value = maxCurrentQty;
        ev.target.value = value;
    }

    row.current_qty_week = value;
    row.current_qty_cum = prevQty + value;

    this.recomputeRowValues(row);
    row._dirty = true;
}

    onNoteInput(row, ev) {
        if (this.isReadonlyPeriod || !row.is_editable) return;
        row.current_note = ev.target.value || "";
        row._dirty = true;
    }

recomputeRowValues(row) {
    const acceptedQty = Math.max(0, Number(row.accepted_qty || 0));
    const prevQty = Math.max(0, Number(row.prev_qty_cum || 0));
    const currentQty = Math.max(0, Number(row.current_qty_week || 0));
    const priceUnitTax = Math.max(0, Number(row.price_unit_tax || 0));

    // Không cho lũy kế QT vượt quá khối lượng đã nghiệm thu
    let currentQtyCum = prevQty + currentQty;
    if (currentQtyCum > acceptedQty) {
        currentQtyCum = acceptedQty;
    }

    const currentQtyWeek = Math.max(0, currentQtyCum - prevQty);

    row.current_qty_week = currentQtyWeek;
    row.current_qty_cum = currentQtyCum;

    // Còn lại = đã nghiệm thu - đã thanh/quyết toán
    row.qty_remaining = Math.max(0, acceptedQty - currentQtyCum);

    row.prev_value_tax = prevQty * priceUnitTax;
    row.current_value_tax = currentQtyWeek * priceUnitTax;
    row.current_value_cum_tax = currentQtyCum * priceUnitTax;

    const acceptedValueTax =
        row.accepted_value_tax !== undefined && row.accepted_value_tax !== null
            ? Number(row.accepted_value_tax || 0)
            : acceptedQty * priceUnitTax;

    row.accepted_value_tax = acceptedValueTax;

    // Giá trị còn lại QT = giá trị đã nghiệm thu - giá trị đã QT
    row.value_remaining_tax = Math.max(
        0,
        acceptedValueTax - row.current_value_cum_tax
    );
}

    async saveAll() {
        if (this.state.project?.is_completed) {
            this.notification.add("Dự án đã hoàn tất, không được nhập thanh/quyết toán.", { type: "warning" });
            return;
        }

        if (this.isReadonlyPeriod) {
            this.notification.add("Kỳ trước chỉ được xem, không được chỉnh sửa.", { type: "warning" });
            return;
        }

        const dirtyRows = this.selectedRows
            .filter((row) => row._dirty && row.assignment_id)
            .map((row) => ({
                finalization_id: row.finalization_id || false,
                assignment_id: row.assignment_id,
                work_item_id: row.work_item_id || false,
                current_qty_week: row.current_qty_week || 0,
                current_note: row.current_note || "",
            }));

        if (!dirtyRows.length) {
            this.notification.add("Không có dữ liệu thay đổi.", { type: "info" });
            return;
        }

        this.state.saving = true;
        try {
            const result = await this.orm.call(
                "project.project",
                "save_finalization_report_rows",
                [[this.state.projectId], this.state.selectedPeriod, dirtyRows, this.state.managerMode]
            );

            this.state.project = result.project || {};
            this.state.assignableUsers = result.assignable_users || [];
            this.state.availablePeriods = result.available_periods || [];
            this.state.currentPeriodNo = result.current_period_no || 0;
            this.state.rowsByPeriod = {};

            for (const [periodKey, rows] of Object.entries(result.rows_by_period || {})) {
                this.state.rowsByPeriod[periodKey] = rows.map((row) => ({
                    ...row,
                    _dirty: false,
                }));
            }

            this.state.embeddedFormKey += 1;

            this.notification.add("Đã lưu báo cáo thanh/quyết toán.", { type: "success" });
        } catch (error) {
            console.error(error);
            this.notification.add(error?.message || "Lưu dữ liệu thất bại.", { type: "danger" });
            throw error;
        } finally {
            this.state.saving = false;
        }
    }

    onProjectAssignUserChange(ev) {
        this.state.projectAssignUserId = ev.target.value ? Number(ev.target.value) : null;
    }

    async assignProjectUser() {
        if (!this.state.projectId || !this.state.projectAssignUserId) return;

        try {
            const result = await this.orm.call(
                "project.project",
                "action_assign_project_finalization_user",
                [[this.state.projectId], this.state.projectAssignUserId]
            );
            this.notification.add(
                result?.message || "Đã cập nhật người phụ trách thanh/quyết toán.",
                { type: "success" }
            );
            await this.loadData();
        } catch (error) {
            console.error(error);
            this.notification.add("Không thể cập nhật người phụ trách.", { type: "danger" });
            throw error;
        }
    }

    backToProjectList() {
        const fallbackActionXmlId = this.state.managerMode
            ? "project_work_finalization_report.action_manager_finalization_project_report"
            : "project_work_finalization_report.action_my_finalization_project_report";
        this.action.doAction(fallbackActionXmlId);
    }

    async reload() {
        await this.loadData();
    }
}

registry.category("actions").add(
    "project_work_finalization_report.FinalizationReport",
    FinalizationReport
);