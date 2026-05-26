/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class BidImportAction extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            projectName: "",
            note: "",
            filename: "",
            fileContent: "",
            loadingSheets: false,
            loadingPreview: false,
            creating: false,
            sheetInfo: null,
            preview: null,
            activeSectionIndex: 0,
            error: "",
        });
    }

    formatNumber(value) {
        const number = Number(value || 0);
        return number.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
    }

    get selectedSheets() {
        if (!this.state.sheetInfo || !this.state.sheetInfo.sheets) {
            return [];
        }
        return this.state.sheetInfo.sheets.filter((sheet) => sheet.selected).map((sheet) => sheet.name);
    }

    get selectedSheetCount() {
        return this.selectedSheets.length;
    }

    get hasFile() {
        return Boolean(this.state.fileContent);
    }

    get activeSection() {
        if (!this.state.preview || !this.state.preview.sections.length) {
            return null;
        }
        return this.state.preview.sections[this.state.activeSectionIndex] || null;
    }

    async onFileChange(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;

        this.state.filename = file.name;
        this.state.fileContent = "";
        this.state.sheetInfo = null;
        this.state.preview = null;
        this.state.error = "";

        const allowed = ["xls", "xlsx", "xlsm"];
        const ext = file.name.split(".").pop().toLowerCase();
        if (!allowed.includes(ext)) {
            this.state.error = "Chỉ hỗ trợ file Excel .xls, .xlsx, .xlsm";
            return;
        }

        this.state.fileContent = await this._readFileAsDataURL(file);
        if (!this.state.projectName) {
            this.state.projectName = file.name.replace(/\.(xls|xlsx|xlsm)$/i, "");
        }
        await this.loadSheets();
    }

    _readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    async loadSheets() {
        if (!this.state.fileContent) {
            this.notification.add("Vui lòng chọn file Excel", { type: "warning" });
            return;
        }
        this.state.loadingSheets = true;
        this.state.error = "";
        this.state.preview = null;
        try {
            const result = await this.rpc("/bid_estimation/get_sheets", {
                filename: this.state.filename,
                file_content: this.state.fileContent,
            });
            this.state.sheetInfo = result;
            const count = result.sheets.filter((sheet) => sheet.selected).length;
            this.notification.add(`Đã đọc ${result.sheet_count} sheet, đang chọn ${count} sheet có dữ liệu`, { type: "success" });
        } catch (error) {
            this.state.error = error.message || "Không đọc được danh sách sheet";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loadingSheets = false;
        }
    }

    toggleSheet(sheet) {
        sheet.selected = !sheet.selected;
        this.state.preview = null;
    }

    selectAllSheets() {
        if (!this.state.sheetInfo) return;
        for (const sheet of this.state.sheetInfo.sheets) {
            sheet.selected = true;
        }
        this.state.preview = null;
    }

    selectDataSheetsOnly() {
        if (!this.state.sheetInfo) return;
        for (const sheet of this.state.sheetInfo.sheets) {
            sheet.selected = Boolean(sheet.has_data);
        }
        this.state.preview = null;
    }

    clearSheetSelection() {
        if (!this.state.sheetInfo) return;
        for (const sheet of this.state.sheetInfo.sheets) {
            sheet.selected = false;
        }
        this.state.preview = null;
    }

    async previewExcel() {
        if (!this.state.fileContent) {
            this.notification.add("Vui lòng chọn file Excel", { type: "warning" });
            return;
        }
        if (!this.selectedSheetCount) {
            this.notification.add("Vui lòng chọn ít nhất 1 sheet để preview/import", { type: "warning" });
            return;
        }
        this.state.loadingPreview = true;
        this.state.error = "";
        try {
            const result = await this.rpc("/bid_estimation/import_preview", {
                filename: this.state.filename,
                file_content: this.state.fileContent,
                selected_sheets: this.selectedSheets,
            });
            this.state.preview = result;
            this.state.activeSectionIndex = 0;
            this.notification.add("Đã preview dữ liệu từ các sheet đã chọn", { type: "success" });
        } catch (error) {
            this.state.error = error.message || "Không đọc được dữ liệu trong sheet đã chọn";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loadingPreview = false;
        }
    }

    selectSection(index) {
        this.state.activeSectionIndex = index;
    }

    async createProject() {
        if (!this.state.projectName) {
            this.notification.add("Vui lòng nhập tên dự án dự thầu", { type: "warning" });
            return;
        }
        if (!this.state.preview) {
            this.notification.add("Vui lòng preview các sheet cần import trước", { type: "warning" });
            return;
        }

        this.state.creating = true;
        this.state.error = "";
        try {
            const result = await this.rpc("/bid_estimation/create_project", {
                project_name: this.state.projectName,
                note: this.state.note,
                preview: this.state.preview,
            });
            this.notification.add("Đã tạo dự án dự thầu", { type: "success" });
            await this.action.doAction({
                type: "ir.actions.client",
                name: "Xem dự án OWL",
                tag: "bid_estimation_project_view_action",
                target: "current",
                params: { project_id: result.project_id },
            });
        } catch (error) {
            this.state.error = error.message || "Không tạo được dự án";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.creating = false;
        }
    }
}

BidImportAction.template = "bid_estimation.BidImportAction";
registry.category("actions").add("bid_estimation_import_action", BidImportAction);
