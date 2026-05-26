/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class BidProjectViewAction extends Component {
    static template = "bid_estimation.BidProjectViewAction";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            projects: [],
            project: null,
            sections: [],
            items: [],
            lines: [],
            quotes: [],
            partners: [],
            selectedProjectId: this.props.action?.params?.project_id || false,
            selectedSectionId: false,
            searchText: "",
            expandedLineIds: {},
            supplierFormLineId: false,
            editingQuoteId: false,
            supplierForm: this.getEmptySupplierForm(),
            supplierSearch: "",
            supplierDropdownOpen: false,
            lineFormItemId: false,
            lineFormSectionId: false,
            editingLineId: false,
            lineForm: this.getEmptyLineForm(),
            projectFormOpen: false,
            projectForm: { name: "", note: "" },
            supplierImportOpen: false,
            supplierImportFilename: "",
            supplierImportContent: "",
            supplierImportSupplierName: "",
            supplierImportLoading: false,
        });

        onWillStart(async () => {
            await this.loadProjects();
            await this.loadPartners();
            if (this.state.selectedProjectId) {
                await this.loadProject(this.state.selectedProjectId);
            } else if (this.state.projects.length) {
                await this.loadProject(this.state.projects[0].id);
            }
            this.state.loading = false;
        });
    }

    getEmptySupplierForm() {
        return {
            partner_id: "",
            partner_name: "",
            price_unit: "",
            delivery_time: "",
            warranty: "",
            payment_term: "",
            note: "",
            is_selected: false,
        };
    }

    getEmptyLineForm() {
        return {
            stt: "",
            name: "",
            uom_name: "",
            quantity: "",
            price_unit: "",
            technical_note: "",
        };
    }

    async loadProjects() {
        this.state.projects = await this.orm.searchRead(
            "bid.project",
            [],
            ["name", "amount_total", "section_count", "line_count"],
            { order: "id desc", limit: 80 }
        );
    }

    async loadPartners() {
        this.state.partners = await this.orm.searchRead(
            "res.partner",
            [["active", "=", true]],
            ["name"],
            { order: "name", limit: 300 }
        );
    }

    async onChangeProject(ev) {
        const projectId = parseInt(ev.target.value || 0);
        if (projectId) {
            await this.loadProject(projectId);
        }
    }

    async loadProject(projectId) {
        this.state.loading = true;
        this.state.selectedProjectId = projectId;
        this.state.selectedSectionId = false;
        this.state.searchText = "";
        this.state.expandedLineIds = {};
        this.cancelSupplierForm();
        this.cancelLineForm();
        this.cancelProjectForm();

        const projects = await this.orm.searchRead(
            "bid.project",
            [["id", "=", projectId]],
            ["name", "note", "amount_total", "supplier_best_amount_total", "saving_amount_total", "section_count", "line_count", "supplier_quote_count"]
        );
        this.state.project = projects[0] || null;

        this.state.sections = await this.orm.searchRead(
            "bid.section",
            [["project_id", "=", projectId]],
            ["name", "code", "amount_total", "supplier_best_amount_total", "saving_amount_total", "sequence"],
            { order: "sequence,id" }
        );

        this.state.items = await this.orm.searchRead(
            "bid.item",
            [["project_id", "=", projectId]],
            ["name", "code", "section_id", "parent_id", "amount_total", "supplier_best_amount_total", "saving_amount_total", "sequence", "is_material_parent", "uom_name", "quantity", "price_unit"],
            { order: "section_id,sequence,id" }
        );

        this.state.lines = await this.orm.searchRead(
            "bid.line",
            [["project_id", "=", projectId]],
            ["stt", "name", "section_id", "item_id", "parent_id", "sequence", "uom_name", "quantity", "price_unit", "amount_total", "technical_note", "supplier_quote_count", "supplier_best_partner_id", "supplier_best_price_unit", "supplier_best_amount_total", "saving_amount", "saving_percent", "selected_partner_id", "selected_price_unit", "selected_amount_total"],
            { order: "section_id,sequence,id" }
        );

        this.state.quotes = await this.orm.searchRead(
            "bid.supplier.quote",
            [["project_id", "=", projectId]],
            ["line_id", "partner_id", "price_unit", "amount_total", "diff_price_unit", "diff_amount_total", "diff_percent", "is_selected", "delivery_time", "warranty", "payment_term", "note"],
            { order: "line_id,price_unit,id" }
        );

        if (this.state.sections.length) {
            this.state.selectedSectionId = this.state.sections[0].id;
        }
        this.state.loading = false;
    }

    selectSection(sectionId) {
        this.state.selectedSectionId = sectionId;
        this.state.searchText = "";
        this.state.expandedLineIds = {};
    }

    onSearch(ev) {
        this.state.searchText = ev.target.value || "";
    }

    get selectedSection() {
        return this.state.sections.find((s) => s.id === this.state.selectedSectionId) || null;
    }

    get sectionItems() {
        if (!this.state.selectedSectionId) {
            return [];
        }
        return this.state.items.filter((item) => item.section_id?.[0] === this.state.selectedSectionId);
    }

    get rootSectionItems() {
        return this.sectionItems.filter((item) => !item.parent_id);
    }

    getChildItems(parentId) {
        return this.sectionItems.filter((item) => item.parent_id?.[0] === parentId);
    }

    getDescendantItemIds(itemId) {
        const ids = [itemId];
        const stack = [itemId];
        while (stack.length) {
            const parent = stack.pop();
            const children = this.getChildItems(parent);
            for (const child of children) {
                ids.push(child.id);
                stack.push(child.id);
            }
        }
        return ids;
    }

    get sectionDisplayItems() {
        const items = this.sectionItems;
        const byParent = new Map();
        for (const item of items) {
            const parentId = item.parent_id?.[0] || 0;
            if (!byParent.has(parentId)) {
                byParent.set(parentId, []);
            }
            byParent.get(parentId).push(item);
        }
        for (const list of byParent.values()) {
            list.sort((a, b) => (a.sequence || 0) - (b.sequence || 0) || a.id - b.id);
        }
        const result = [];
        const visit = (parentId, level) => {
            for (const item of byParent.get(parentId) || []) {
                result.push({ ...item, level });
                visit(item.id, level + 1);
            }
        };
        visit(0, 0);
        const pushed = new Set(result.map((item) => item.id));
        for (const item of items) {
            if (!pushed.has(item.id)) {
                result.push({ ...item, level: 0 });
            }
        }
        return result;
    }

    getItemIndentStyle(item) {
        return `padding-left: ${(item.level || 0) * 22}px`;
    }

    get sectionLines() {
        if (!this.state.selectedSectionId) {
            return [];
        }
        const keyword = (this.state.searchText || "").toLowerCase().trim();
        let lines = this.state.lines.filter((line) => line.section_id?.[0] === this.state.selectedSectionId);
        if (keyword) {
            lines = lines.filter((line) => {
                const text = `${line.name || ""} ${line.uom_name || ""} ${line.technical_note || ""}`.toLowerCase();
                return text.includes(keyword);
            });
        }
        return lines;
    }

    get sectionTotalQty() {
        return this.sectionLines.reduce((sum, line) => sum + (line.quantity || 0), 0);
    }

    get sectionTotalAmount() {
        return this.sectionLines.reduce((sum, line) => sum + (line.amount_total || 0), 0);
    }

    get sectionBestAmount() {
        return this.sectionLines.reduce((sum, line) => sum + (line.supplier_best_amount_total || 0), 0);
    }

    get sectionSavingAmount() {
        return this.sectionLines.reduce((sum, line) => sum + (line.saving_amount || 0), 0);
    }

    getItemLines(itemId, includeChildren = false) {
        if (!includeChildren) {
            return this.sectionLines.filter((line) => line.item_id?.[0] === itemId);
        }
        const ids = new Set(this.getDescendantItemIds(itemId));
        return this.sectionLines.filter((line) => line.item_id?.[0] && ids.has(line.item_id[0]));
    }

    getLooseLines() {
        return this.sectionLines.filter((line) => !line.item_id);
    }

    getLineStt(line) {
        return line.stt || line.sequence || "";
    }

    getLineNameStyle(line) {
        return line.parent_id ? "padding-left: 18px" : "";
    }

    getLineQuotes(lineId) {
        return this.state.quotes.filter((quote) => quote.line_id?.[0] === lineId);
    }

    getBestQuote(line) {
        const quotes = this.getLineQuotes(line.id).filter((quote) => (quote.price_unit || 0) > 0);
        if (!quotes.length) {
            return null;
        }
        return [...quotes].sort((a, b) => (a.price_unit || 0) - (b.price_unit || 0) || a.id - b.id)[0];
    }

    getSelectedQuote(line) {
        return this.getLineQuotes(line.id).find((quote) => quote.is_selected) || null;
    }

    getCompareClass(line) {
        const best = this.getBestQuote(line);
        if (!best) {
            return "";
        }
        if ((best.price_unit || 0) < (line.price_unit || 0)) {
            return "good";
        }
        if ((best.price_unit || 0) > (line.price_unit || 0)) {
            return "bad";
        }
        return "neutral";
    }

    getSupplierBadgeClass(line) {
        const count = line.supplier_quote_count || 0;
        if (!count) return "empty";
        if (count >= 3) return "rich";
        return "normal";
    }

    isLineExpanded(line) {
        return Boolean(this.state.expandedLineIds[line.id]);
    }

    toggleLine(line) {
        this.state.expandedLineIds[line.id] = !this.state.expandedLineIds[line.id];
    }

    async selectQuote(quote) {
        if (!quote) return;
        await this.orm.call("bid.supplier.quote", "action_select_quote", [[quote.id]]);
        this.notification.add("Đã chọn báo giá nhà cung cấp.", { type: "success" });
        await this.refresh(false);
    }

    openAddSupplierForm(line) {
        if (!line) return;
        this.state.expandedLineIds[line.id] = true;
        this.state.supplierFormLineId = line.id;
        this.state.editingQuoteId = false;
        this.state.supplierForm = this.getEmptySupplierForm();
        this.state.supplierSearch = "";
        this.state.supplierDropdownOpen = false;
    }

    openEditSupplierForm(quote) {
        if (!quote) return;
        const lineId = quote.line_id?.[0];
        this.state.expandedLineIds[lineId] = true;
        this.state.supplierFormLineId = lineId;
        this.state.editingQuoteId = quote.id;
        this.state.supplierSearch = quote.partner_id?.[1] || "";
        this.state.supplierDropdownOpen = false;
        this.state.supplierForm = {
            partner_id: quote.partner_id?.[0] ? String(quote.partner_id[0]) : "",
            partner_name: "",
            price_unit: quote.price_unit || "",
            delivery_time: quote.delivery_time || "",
            warranty: quote.warranty || "",
            payment_term: quote.payment_term || "",
            note: quote.note || "",
            is_selected: Boolean(quote.is_selected),
        };
    }

    cancelSupplierForm() {
        this.state.supplierFormLineId = false;
        this.state.editingQuoteId = false;
        this.state.supplierForm = this.getEmptySupplierForm();
        this.state.supplierSearch = "";
    }

    isSupplierFormOpen(line) {
        return Boolean(line && this.state.supplierFormLineId === line.id);
    }


    onSupplierSearchInput(ev) {
        const value = ev.target.value || "";
        this.state.supplierSearch = value;
        this.state.supplierDropdownOpen = true;
        // Khi người dùng gõ tìm NCC khác, bỏ chọn NCC cũ để tránh lưu nhầm.
        this.state.supplierForm.partner_id = "";
    }

    openSupplierDropdown() {
        this.state.supplierDropdownOpen = true;
    }

    closeSupplierDropdown() {
        // Delay nhỏ để click chọn NCC trong dropdown kịp chạy trước khi blur.
        setTimeout(() => {
            this.state.supplierDropdownOpen = false;
        }, 180);
    }

    clearSupplierPartner() {
        this.state.supplierForm.partner_id = "";
        this.state.supplierSearch = "";
        this.state.supplierDropdownOpen = true;
    }

    chooseSupplierPartner(partner) {
        if (!partner) return;
        this.state.supplierForm.partner_id = String(partner.id);
        this.state.supplierSearch = partner.name || "";
        this.state.supplierForm.partner_name = "";
        this.state.supplierDropdownOpen = false;
    }

    filteredPartners() {
        const keyword = (this.state.supplierSearch || "").trim().toLowerCase();
        if (!keyword) {
            return this.state.partners.slice(0, 80);
        }
        return this.state.partners
            .filter((partner) => (partner.name || "").toLowerCase().includes(keyword))
            .slice(0, 80);
    }

    onSelectSupplierPartner(ev) {
        const partnerId = ev.target.value || "";
        this.state.supplierForm.partner_id = partnerId;
        const partner = this.state.partners.find((p) => String(p.id) === String(partnerId));
        if (partner) {
            this.state.supplierSearch = partner.name || "";
            this.state.supplierForm.partner_name = "";
        }
    }

    onSupplierInput(ev) {
        const name = ev.target.name;
        if (!name) return;
        if (ev.target.type === "checkbox") {
            this.state.supplierForm[name] = ev.target.checked;
        } else {
            this.state.supplierForm[name] = ev.target.value;
        }
    }

    async saveSupplierQuote(line) {
        if (!line) return;
        const form = this.state.supplierForm;
        const priceUnit = Number(String(form.price_unit || "").replace(/,/g, ""));
        if (!priceUnit || priceUnit <= 0) {
            this.notification.add("Vui lòng nhập đơn giá NCC hợp lệ.", { type: "warning" });
            return;
        }

        let partnerId = parseInt(form.partner_id || 0);
        const newPartnerName = (form.partner_name || "").trim();
        if (!partnerId && newPartnerName) {
            const createdPartner = await this.orm.create("res.partner", [{ name: newPartnerName }]);
            partnerId = Array.isArray(createdPartner) ? createdPartner[0] : createdPartner;
            await this.loadPartners();
        }
        if (!partnerId) {
            this.notification.add("Vui lòng chọn NCC hoặc nhập tên NCC mới.", { type: "warning" });
            return;
        }

        const vals = {
            line_id: line.id,
            partner_id: partnerId,
            price_unit: priceUnit,
            delivery_time: form.delivery_time || false,
            warranty: form.warranty || false,
            payment_term: form.payment_term || false,
            note: form.note || false,
            is_selected: Boolean(form.is_selected),
        };

        if (this.state.editingQuoteId) {
            await this.orm.write("bid.supplier.quote", [this.state.editingQuoteId], vals);
            this.notification.add("Đã cập nhật báo giá NCC.", { type: "success" });
        } else {
            await this.orm.create("bid.supplier.quote", [vals]);
            this.notification.add("Đã thêm báo giá NCC.", { type: "success" });
        }

        const expanded = { ...this.state.expandedLineIds, [line.id]: true };
        this.cancelSupplierForm();
        await this.refresh(false);
        this.state.expandedLineIds = expanded;
    }

    async deleteSupplierQuote(quote) {
        if (!quote) return;
        await this.orm.unlink("bid.supplier.quote", [quote.id]);
        this.notification.add("Đã xóa báo giá NCC.", { type: "success" });
        const lineId = quote.line_id?.[0];
        const expanded = { ...this.state.expandedLineIds };
        if (lineId) expanded[lineId] = true;
        if (this.state.editingQuoteId === quote.id) {
            this.cancelSupplierForm();
        }
        await this.refresh(false);
        this.state.expandedLineIds = expanded;
    }

    openAddLineForm(item = null) {
        if (!this.state.project || !this.state.selectedSectionId) return;
        this.cancelSupplierForm();
        this.state.editingLineId = false;
        this.state.lineFormSectionId = this.state.selectedSectionId;
        this.state.lineFormItemId = item?.id || false;
        this.state.lineForm = this.getEmptyLineForm();
    }

    openEditLineForm(line) {
        if (!line) return;
        this.cancelSupplierForm();
        this.state.expandedLineIds[line.id] = true;
        this.state.editingLineId = line.id;
        this.state.lineFormSectionId = line.section_id?.[0] || this.state.selectedSectionId;
        this.state.lineFormItemId = line.item_id?.[0] || false;
        this.state.lineForm = {
            stt: line.stt || "",
            name: line.name || "",
            uom_name: line.uom_name || "",
            quantity: line.quantity || "",
            price_unit: line.price_unit || "",
            technical_note: line.technical_note || "",
        };
    }

    cancelLineForm() {
        this.state.lineFormItemId = false;
        this.state.lineFormSectionId = false;
        this.state.editingLineId = false;
        this.state.lineForm = this.getEmptyLineForm();
    }

    isLineFormOpenForItem(item) {
        return Boolean(!this.state.editingLineId && item && this.state.lineFormItemId === item.id);
    }

    isLooseLineFormOpen() {
        return Boolean(!this.state.editingLineId && !this.state.lineFormItemId && this.state.lineFormSectionId === this.state.selectedSectionId);
    }

    isEditingLine(line) {
        return Boolean(line && this.state.editingLineId === line.id);
    }

    onLineInput(ev) {
        const name = ev.target.name;
        if (!name) return;
        this.state.lineForm[name] = ev.target.value;
    }

    async saveLine() {
        const form = this.state.lineForm;
        const name = (form.name || "").trim();
        if (!name) {
            this.notification.add("Vui lòng nhập tên vật tư.", { type: "warning" });
            return;
        }
        const quantity = Number(String(form.quantity || "0").replace(/,/g, "")) || 0;
        const priceUnit = Number(String(form.price_unit || "0").replace(/,/g, "")) || 0;
        const vals = {
            project_id: this.state.project.id,
            section_id: this.state.lineFormSectionId || this.state.selectedSectionId,
            item_id: this.state.lineFormItemId || false,
            stt: form.stt || false,
            name,
            uom_name: form.uom_name || false,
            quantity,
            price_unit: priceUnit,
            technical_note: form.technical_note || false,
        };

        let keepExpandedLineId = false;
        if (this.state.editingLineId) {
            await this.orm.write("bid.line", [this.state.editingLineId], vals);
            keepExpandedLineId = this.state.editingLineId;
            this.notification.add("Đã cập nhật vật tư.", { type: "success" });
        } else {
            const created = await this.orm.create("bid.line", [vals]);
            keepExpandedLineId = Array.isArray(created) ? created[0] : created;
            this.notification.add("Đã thêm vật tư.", { type: "success" });
        }
        const currentSection = this.state.selectedSectionId;
        this.cancelLineForm();
        await this.refresh(false);
        if (currentSection) this.state.selectedSectionId = currentSection;
        if (keepExpandedLineId) this.state.expandedLineIds[keepExpandedLineId] = true;
    }

    async deleteLine(line) {
        if (!line) return;
        const ok = window.confirm(`Xóa vật tư "${line.name || ""}" và toàn bộ báo giá NCC của vật tư này?`);
        if (!ok) return;
        await this.orm.unlink("bid.line", [line.id]);
        if (this.state.editingLineId === line.id) {
            this.cancelLineForm();
        }
        this.notification.add("Đã xóa vật tư.", { type: "success" });
        await this.refresh(false);
    }

    openLineForm(line) {
        if (!line) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Vật tư",
            res_model: "bid.line",
            res_id: line.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openSupplierQuotes(line) {
        if (!line) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Báo giá NCC",
            res_model: "bid.supplier.quote",
            views: [[false, "tree"], [false, "form"]],
            domain: [["line_id", "=", line.id]],
            context: { default_line_id: line.id },
            target: "current",
        });
    }


    openEditProject() {
        if (!this.state.project) return;
        this.state.projectFormOpen = true;
        this.state.projectForm = {
            name: this.state.project.name || "",
            note: this.state.project.note || "",
        };
    }

    cancelProjectForm() {
        this.state.projectFormOpen = false;
        this.state.projectForm = { name: "", note: "" };
    }

    async saveProject() {
        if (!this.state.project) return;
        const name = (this.state.projectForm.name || "").trim();
        if (!name) {
            this.notification.add("Vui lòng nhập tên dự toán dự thầu.", { type: "warning" });
            return;
        }
        await this.orm.write("bid.project", [this.state.project.id], {
            name,
            note: this.state.projectForm.note || false,
        });
        this.notification.add("Đã cập nhật dự toán dự thầu.", { type: "success" });
        this.cancelProjectForm();
        await this.loadProjects();
        await this.loadProject(this.state.project.id);
    }

    async deleteProject() {
        if (!this.state.project) return;
        const name = this.state.project.name || "";
        const ok = window.confirm(`Xóa dự toán dự thầu "${name}"? Toàn bộ hạng mục, vật tư và báo giá NCC thuộc dự án này cũng sẽ bị xóa.`);
        if (!ok) return;
        const projectId = this.state.project.id;
        await this.orm.unlink("bid.project", [projectId]);
        this.notification.add("Đã xóa dự toán dự thầu.", { type: "success" });
        this.openProjectList();
    }

    openProjectForm() {
        if (!this.state.project) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Dự án dự thầu",
            res_model: "bid.project",
            res_id: this.state.project.id,
            views: [[false, "form"]],
            target: "current",
        });
    }


    openSupplierImport() {
        if (!this.state.project) return;
        this.state.supplierImportOpen = true;
        this.state.supplierImportFilename = "";
        this.state.supplierImportContent = "";
        this.state.supplierImportSupplierName = "";
    }

    cancelSupplierImport() {
        this.state.supplierImportOpen = false;
        this.state.supplierImportFilename = "";
        this.state.supplierImportContent = "";
        this.state.supplierImportSupplierName = "";
        this.state.supplierImportLoading = false;
    }

    async onSupplierImportFileChange(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        this.state.supplierImportFilename = file.name;
        this.state.supplierImportContent = await this.fileToDataUrl(file);
    }

    fileToDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(file);
        });
    }

    async importSupplierExcel() {
        if (!this.state.project) return;
        if (!this.state.supplierImportSupplierName || !this.state.supplierImportSupplierName.trim()) {
            this.notification.add("Vui lòng nhập tên nhà cung cấp.", { type: "warning" });
            return;
        }
        if (!this.state.supplierImportContent) {
            this.notification.add("Vui lòng chọn file Excel báo giá NCC.", { type: "warning" });
            return;
        }
        this.state.supplierImportLoading = true;
        try {
            const response = await fetch('/bid_estimation/import_supplier_quotes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        project_id: this.state.project.id,
                        filename: this.state.supplierImportFilename,
                        file_content: this.state.supplierImportContent,
                        supplier_name: this.state.supplierImportSupplierName.trim(),
                    },
                }),
            });
            const payload = await response.json();
            if (payload.error) {
                throw new Error(payload.error.data?.message || payload.error.message || "Import NCC thất bại.");
            }
            const data = payload.result || {};
            this.notification.add(
                `Đã import NCC: thêm ${data.created || 0}, cập nhật ${data.updated || 0}, bỏ qua ${data.skipped || 0}.`,
                { type: "success" }
            );
            this.cancelSupplierImport();
            await this.refresh(false);
        } catch (error) {
            this.notification.add(error.message || "Import NCC thất bại.", { type: "danger" });
        } finally {
            this.state.supplierImportLoading = false;
        }
    }

    openExportExcel() {
        if (!this.state.project) return;
        window.open(`/bid_estimation/export_excel/${this.state.project.id}`, "_blank");
    }


    openProjectList() {
        this.action.doAction({
            type: "ir.actions.client",
            name: "Danh sách dự án dự thầu",
            tag: "bid_estimation_project_list_action",
            target: "current",
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

    formatNumber(value) {
        return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value || 0);
    }

    formatMoney(value) {
        return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value || 0);
    }

    async refresh(showToast = true) {
        if (this.state.selectedProjectId) {
            const currentSection = this.state.selectedSectionId;
            const expanded = { ...this.state.expandedLineIds };
            await this.loadProject(this.state.selectedProjectId);
            if (currentSection && this.state.sections.some((s) => s.id === currentSection)) {
                this.state.selectedSectionId = currentSection;
            }
            this.state.expandedLineIds = expanded;
            if (showToast) {
                this.notification.add("Đã tải lại dữ liệu dự án.", { type: "success" });
            }
        }
    }
}

registry.category("actions").add("bid_estimation_project_view_action", BidProjectViewAction);
