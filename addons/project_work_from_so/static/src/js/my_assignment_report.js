/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

export class MyAssignmentReport extends Component {
    static template = "project_work_from_so.MyAssignmentReport";
    static components = { View };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        const actionContext = this.props.action?.context || {};

        const contextProjectId = actionContext.default_project_id || null;
        const storedProjectId = window.sessionStorage.getItem("my_assignment_project_id");
        const storedSelectedPeriod = window.sessionStorage.getItem("my_assignment_selected_period");
        const storedManagerMode = window.sessionStorage.getItem("my_assignment_manager_mode");

        const managerMode =
            typeof actionContext.manager_mode !== "undefined"
                ? !!actionContext.manager_mode
                : storedManagerMode === "true";

        this.state = useState({
            loading: true,
            saving: false,
            projectId: contextProjectId || (storedProjectId ? Number(storedProjectId) : null),
            managerMode: managerMode,
            project: {},
            assignableUsers: [],
            projectAssignUserId: null,
            availablePeriods: [],
            currentPeriodNo: 0,
            selectedPeriod: storedSelectedPeriod ? Number(storedSelectedPeriod) : null,
            rowsByPeriod: {},
            embeddedFormKey: 0,
        });

        window.sessionStorage.setItem(
            "my_assignment_manager_mode",
            String(this.state.managerMode)
        );

        if (this.state.projectId) {
            window.sessionStorage.setItem(
                "my_assignment_project_id",
                String(this.state.projectId)
            );
        }

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
                form_view_ref: "project_work_from_so.view_project_project_form_chatter_only",
            },
            display: {
                controlPanel: false,
            },
            mode: "edit",
        };
    }

    backToProjectList() {
        const currentHref = window.location.href;

        if (window.history.length > 1) {
            window.history.back();

            setTimeout(() => {
                if (window.location.href === currentHref) {
                    const fallbackActionXmlId = this.state.managerMode
                        ? "project_work_from_so.action_manager_assignment_project_report"
                        : "project_work_from_so.action_my_assignment_project_report";

                    this.action.doAction(fallbackActionXmlId);
                }
            }, 300);
            return;
        }

        const fallbackActionXmlId = this.state.managerMode
            ? "project_work_from_so.action_manager_assignment_project_report"
            : "project_work_from_so.action_my_assignment_project_report";

        this.action.doAction(fallbackActionXmlId);
    }

    async loadData() {
        if (!this.state.projectId) {
            this.notification.add("Không tìm thấy dự án để nhập báo cáo.", {
                type: "warning",
            });
            this.state.loading = false;
            return;
        }

        window.sessionStorage.setItem(
            "my_assignment_project_id",
            String(this.state.projectId)
        );
        window.sessionStorage.setItem(
            "my_assignment_manager_mode",
            String(this.state.managerMode)
        );

        this.state.loading = true;
        try {
            const result = await this.orm.call(
                "project.project",
                "get_assignment_report_rows",
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

            if (this.state.managerMode) {
                this.state.projectAssignUserId = this.state.project.assignment_user_id
                    ? Number(this.state.project.assignment_user_id)
                    : null;
            } else {
                this.state.projectAssignUserId = null;
            }

            const available = this.state.availablePeriods || [];
            const current = this.state.currentPeriodNo || 0;

            if (!available.length) {
                this.state.selectedPeriod = null;
            } else if (this.state.managerMode) {
                this.state.selectedPeriod =
                    current && available.includes(current)
                        ? current
                        : available[available.length - 1];
            } else if (
                this.state.selectedPeriod &&
                available.includes(this.state.selectedPeriod)
            ) {
                // giữ kỳ cũ
            } else {
                this.state.selectedPeriod =
                    current && available.includes(current)
                        ? current
                        : available[available.length - 1];
            }

            if (this.state.selectedPeriod) {
                window.sessionStorage.setItem(
                    "my_assignment_selected_period",
                    String(this.state.selectedPeriod)
                );
            } else {
                window.sessionStorage.removeItem("my_assignment_selected_period");
            }

            this.state.embeddedFormKey += 1;
        } catch (error) {
            console.error(error);
            this.notification.add("Không tải được dữ liệu báo cáo sản lượng.", {
                type: "danger",
            });
            throw error;
        } finally {
            this.state.loading = false;
        }
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

    formatPrice(value) {
        return this.formatNumber(value, 0);
    }

    formatMoney(value) {
        return this.formatNumber(value, 0);
    }

    formatDate(value) {
        if (!value) {
            return "";
        }
        const parts = String(value).split("-");
        if (parts.length === 3) {
            return `${parts[2]}/${parts[1]}/${parts[0]}`;
        }
        return value;
    }

    formatPercent(value) {
        return `${Math.round(Number(value || 0))}%`;
    }

    onPeriodChange(ev) {
        this.state.selectedPeriod = Number(ev.target.value);
        if (this.state.selectedPeriod) {
            window.sessionStorage.setItem(
                "my_assignment_selected_period",
                String(this.state.selectedPeriod)
            );
        }
    }

    get selectedRows() {
        if (!this.state.selectedPeriod) {
            return [];
        }
        return this.state.rowsByPeriod[String(this.state.selectedPeriod)] || [];
    }

    get isReadonlyPeriod() {
        if (this.state.project?.is_completed) {
            return true;
        }
        return Number(this.state.selectedPeriod) !== Number(this.state.currentPeriodNo);
    }

    get groupedSelectedRows() {
        const rows = this.selectedRows || [];
        const groups = [];
        const map = new Map();

        for (const row of rows) {
            const sectionName = (row.section_name || "").trim() || "Khác";
            if (!map.has(sectionName)) {
                const group = {
                    section_name: sectionName,
                    rows: [],
                };
                map.set(sectionName, group);
                groups.push(group);
            }
            map.get(sectionName).rows.push(row);
        }

        for (const group of groups) {
            group.rows.forEach((row, index) => {
                row.line_no = index + 1;
            });
        }

        return groups;
    }

    onQtyInput(row, ev) {
        if (this.isReadonlyPeriod || !row.is_editable) {
            return;
        }

        let value = parseFloat(ev.target.value || 0);
        if (isNaN(value) || value < 0) {
            value = 0;
        }

        row.current_qty_week = value;
        row.current_qty_cum = (row.prev_qty_cum || 0) + value;

        this.recomputeRowValues(row);
        row._dirty = true;
    }

    recomputeRowValues(row) {
        const qtyPlan = Number(row.qty_plan || 0);
        const qtyArise = Number(row.qty_arise || 0);
        const contractQty = qtyPlan + qtyArise;

        row.contract_qty = contractQty;
        row.max_total = contractQty;
        row.qty_remaining = Math.max(0, contractQty - Number(row.current_qty_cum || 0));

        const priceUnitTax = Number(row.price_unit_tax || 0);
        row.contract_value_tax = contractQty * priceUnitTax;
        row.prev_value_tax = Number(row.prev_qty_cum || 0) * priceUnitTax;
        row.current_value_tax = Number(row.current_qty_week || 0) * priceUnitTax;
        row.current_value_cum_tax = Number(row.current_qty_cum || 0) * priceUnitTax;
        row.value_remaining_tax = Math.max(
            0,
            row.contract_value_tax - row.current_value_cum_tax
        );
    }

    onQtyAriseInput(row, ev) {
        if (!this.state.managerMode || this.isReadonlyPeriod) {
            return;
        }

        let value = parseFloat(ev.target.value);
        if (isNaN(value)) {
            value = 0;
        }

        row.qty_arise = value;
        this.recomputeRowValues(row);
        row._dirty = true;
    }

    onNoteInput(row, ev) {
        if (this.isReadonlyPeriod || !row.is_editable) {
            return;
        }

        row.current_note = ev.target.value || "";
        row._dirty = true;
    }

    async saveAll() {
        if (this.state.project?.is_completed) {
            this.notification.add("Dự án đã hoàn tất, không được nhập báo cáo.", {
                type: "warning",
            });
            return;
        }

        if (this.isReadonlyPeriod) {
            this.notification.add("Kỳ trước chỉ được xem, không được chỉnh sửa.", {
                type: "warning",
            });
            return;
        }

        const dirtyRows = this.selectedRows
            .filter((row) => row._dirty && (row.is_editable || this.state.managerMode))
            .map((row) => ({
                id: row.id,
                assignment_id: row.assignment_id || false,
                work_item_id: row.work_item_id || false,
                qty_arise: this.state.managerMode ? (row.qty_arise || 0) : false,
                current_qty_week: row.current_qty_week || 0,
                current_note: row.current_note || "",
            }));

        if (!dirtyRows.length) {
            this.notification.add("Không có dữ liệu thay đổi.", {
                type: "info",
            });
            return;
        }

        this.state.saving = true;
        try {
            const result = await this.orm.call(
                "project.project",
                "save_assignment_report_rows",
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

            if (this.state.managerMode) {
                this.state.projectAssignUserId = this.state.project.assignment_user_id
                    ? Number(this.state.project.assignment_user_id)
                    : null;
            }

            this.state.embeddedFormKey += 1;

            this.notification.add("Đã lưu báo cáo sản lượng.", {
                type: "success",
            });
        } catch (error) {
            console.error(error);
            this.notification.add(error?.message || "Lưu dữ liệu thất bại.", {
                type: "danger",
            });
            throw error;
        } finally {
            this.state.saving = false;
        }
    }

    async reload() {
        await this.loadData();
    }

    onProjectAssignUserChange(ev) {
        this.state.projectAssignUserId = Number(ev.target.value || 0) || null;
    }

    async assignProjectUser() {
        if (!this.state.managerMode) {
            return;
        }

        if (!this.state.projectAssignUserId) {
            this.notification.add("Vui lòng chọn người phụ trách.", {
                type: "warning",
            });
            return;
        }

        try {
            const result = await this.orm.call(
                "project.project",
                "action_assign_project_report_user",
                [[this.state.projectId], this.state.projectAssignUserId]
            );

            this.notification.add(
                result.message || "Đã cập nhật người phụ trách cho dự án.",
                { type: "success" }
            );

            await this.loadData();
        } catch (error) {
            console.error(error);
            this.notification.add(
                error?.message || "Không cập nhật được người phụ trách dự án.",
                { type: "danger" }
            );
            throw error;
        }
    }

    async syncWorkItemsFromSO(showSuccess = false) {
        try {
            const pid = this.state.projectId;
            if (!pid) {
                return;
            }

            const project = this.state.project || {};
            if (
                Object.keys(project).length &&
                !project.contract_id &&
                !project.sale_order_id
            ) {
                this.notification.add(
                    "Dự án chưa có hợp đồng và cũng chưa có đơn bán để đồng bộ.",
                    { type: "warning" }
                );
                return;
            }

            try {
                await this.orm.call(
                    "project.project",
                    "action_sync_project_data_from_contract_so",
                    [[pid]]
                );
            } catch {
                await this.orm.call(
                    "project.project",
                    "action_sync_work_items_from_so",
                    [[pid]]
                );
            }

            if (showSuccess) {
                this.notification.add("Đã đồng bộ dữ liệu từ hợp đồng/đơn bán.", {
                    type: "success",
                });
            }
        } catch (e) {
            console.error(e);
            this.notification.add(e?.message || "Không đồng bộ được dữ liệu.", {
                type: "danger",
            });
        }
    }

    async manualSyncWorkItemsFromSO() {
        await this.syncWorkItemsFromSO(true);
        await this.loadData();
    }
}

registry
    .category("actions")
    .add("project_work_from_so.MyAssignmentReport", MyAssignmentReport);