/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SupplierDebtRealReport extends Component {
    static template = "vendor_debt_management.SupplierDebtRealReport";

setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.notification = useService("notification");

    this.openDetailReport = this.openDetailReport.bind(this);
    this.prevPage = this.prevPage.bind(this);
    this.nextPage = this.nextPage.bind(this);
    this.refreshData = this.refreshData.bind(this);
    this.exportPdf = this.exportPdf.bind(this);

    this.state = useState({
        loading: true,
        search: "",
        sectionFilter: "all",
        supplierTypeFilter: "all",
        page: 1,
        pageSize: 20,
        data: {
            done_domestic_labor: [],
            done_domestic_material: [],
            done_foreign: [],
            pending_domestic_labor: [],
            pending_domestic_material: [],
            pending_foreign: [],
        },
    });

    onWillStart(async () => {
        await this.loadData();
    });
}

    async loadData() {
        try {
            this.state.loading = true;
            const result = await this.orm.call(
                "supplier.invoice.payment.summary",
                "get_supplier_debt_real_report_data",
                []
            );
            this.state.data = result || {
                done_domestic_labor: [],
                done_domestic_material: [],
                done_foreign: [],
                pending_domestic_labor: [],
                pending_domestic_material: [],
                pending_foreign: [],
            };
        } catch (error) {
            this.notification.add("Không tải được dữ liệu báo cáo.", {
                type: "danger",
            });
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    _decorateRows(items, sectionKey, supplierTypeKey, sectionLabel, supplierTypeLabel) {
        return (items || []).map((item) => ({
            ...item,
            sectionKey,
            supplierTypeKey,
            sectionLabel,
            supplierTypeLabel,
        }));
    }

    get rawRows() {
        return [
            ...this._decorateRows(
                this.state.data.done_domestic_labor,
                "done",
                "domestic_labor",
                "Đã đối chiếu",
                "NCC nhân công"
            ),
            ...this._decorateRows(
                this.state.data.done_domestic_material,
                "done",
                "domestic_material",
                "Đã đối chiếu",
                "NCC vật tư, dịch vụ"
            ),
            ...this._decorateRows(
                this.state.data.done_foreign,
                "done",
                "foreign",
                "Đã đối chiếu",
                "NCC nước ngoài"
            ),
            ...this._decorateRows(
                this.state.data.pending_domestic_labor,
                "pending",
                "domestic_labor",
                "Chờ đối chiếu",
                "NCC nhân công"
            ),
            ...this._decorateRows(
                this.state.data.pending_domestic_material,
                "pending",
                "domestic_material",
                "Chờ đối chiếu",
                "NCC vật tư, dịch vụ"
            ),
            ...this._decorateRows(
                this.state.data.pending_foreign,
                "pending",
                "foreign",
                "Chờ đối chiếu",
                "NCC nước ngoài"
            ),
        ];
    }

    get filteredRows() {
        const keyword = (this.state.search || "").trim().toLowerCase();

        return this.rawRows.filter((row) => {
            const matchSection =
                this.state.sectionFilter === "all" ||
                row.sectionKey === this.state.sectionFilter;

            const matchSupplierType =
                this.state.supplierTypeFilter === "all" ||
                row.supplierTypeKey === this.state.supplierTypeFilter;

            const partnerName = (row.partner_name || "").toLowerCase();
            const supplyCategoryName = (row.supply_category_name || "").toLowerCase();
            const dueDays = (row.due_days || "").toLowerCase();

            const matchSearch =
                !keyword ||
                partnerName.includes(keyword) ||
                supplyCategoryName.includes(keyword) ||
                dueDays.includes(keyword);

            return matchSection && matchSupplierType && matchSearch;
        });
    }

    get totalRows() {
        return this.filteredRows.length;
    }

    get totalPages() {
        return Math.max(1, Math.ceil(this.totalRows / this.state.pageSize));
    }

    get pagedRows() {
        const start = (this.state.page - 1) * this.state.pageSize;
        const end = start + this.state.pageSize;
        return this.filteredRows.slice(start, end);
    }

    get pageStart() {
        if (!this.totalRows) {
            return 0;
        }
        return (this.state.page - 1) * this.state.pageSize + 1;
    }

    get pageEnd() {
        return Math.min(this.state.page * this.state.pageSize, this.totalRows);
    }

    sumRows(rows) {
        return (rows || []).reduce(
            (acc, row) => {
                acc.old_debt += row.old_debt || 0;
                acc.contract_amount += row.contract_amount || 0;
                acc.invoice_amount += row.invoice_amount || 0;
                acc.paid_hd += row.paid_hd || 0;
                acc.advance_amount += row.advance_amount || 0;
                acc.residual_amount += row.residual_amount || 0;
                return acc;
            },
            {
                old_debt: 0,
                contract_amount: 0,
                invoice_amount: 0,
                paid_hd: 0,
                advance_amount: 0,
                residual_amount: 0,
            }
        );
    }

    get totals() {
        return this.sumRows(this.filteredRows);
    }

    get groupedPagedRows() {
        const rows = this.pagedRows.map((row, index) => ({
            ...row,
            stt: (this.state.page - 1) * this.state.pageSize + index + 1,
        }));

        const result = [];
        const sectionOrder = ["done", "pending"];
        const supplierTypeOrder = ["domestic_labor", "domestic_material", "foreign"];

        for (const sectionKey of sectionOrder) {
            const sectionRows = rows.filter((r) => r.sectionKey === sectionKey);
            if (!sectionRows.length) {
                continue;
            }

            result.push({
                type: "section",
                key: `section_${sectionKey}`,
                label: sectionRows[0].sectionLabel,
                totals: this.sumRows(sectionRows),
            });

            for (const supplierTypeKey of supplierTypeOrder) {
                const typeRows = sectionRows.filter((r) => r.supplierTypeKey === supplierTypeKey);
                if (!typeRows.length) {
                    continue;
                }

                result.push({
                    type: "supplier_type",
                    key: `supplier_type_${sectionKey}_${supplierTypeKey}`,
                    label: typeRows[0].supplierTypeLabel,
                    totals: this.sumRows(typeRows),
                });

                for (const row of typeRows) {
                    result.push({
                        type: "row",
                        key: `row_${row.sectionKey}_${row.supplierTypeKey}_${row.partner_id}_${row.stt}`,
                        data: row,
                    });
                }
            }
        }

        return result;
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value || "";
        this.state.page = 1;
    }

    onSectionFilterChange(ev) {
        this.state.sectionFilter = ev.target.value;
        this.state.page = 1;
    }

    onSupplierTypeFilterChange(ev) {
        this.state.supplierTypeFilter = ev.target.value;
        this.state.page = 1;
    }

    onPageSizeChange(ev) {
        this.state.pageSize = parseInt(ev.target.value, 10) || 20;
        this.state.page = 1;
    }

    prevPage() {
        if (this.state.page > 1) {
            this.state.page--;
        }
    }

    nextPage() {
        if (this.state.page < this.totalPages) {
            this.state.page++;
        }
    }

    exportPdf() {
        this.action.doAction("vendor_debt_management.action_supplier_debt_real_report_pdf");
    }

    async refreshData() {
        await this.loadData();
        this.state.page = 1;
    }

    formatMoney(value) {
        return new Intl.NumberFormat("vi-VN", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(value || 0);
    }
openDetailReport(row) {
    console.log("CLICK ROW:", row);

    if (!row || !row.summary_id) {
        this.notification.add(
            `Không tìm thấy dữ liệu chi tiết của nhà cung cấp này. summary_id=${row?.summary_id || false}, partner_id=${row?.partner_id || false}, currency_id=${row?.currency_id || false}`,
            { type: "warning" }
        );
        return;
    }

    this.action.doAction({
        type: "ir.actions.client",
        name: "Báo cáo chi tiết công nợ NCC",
        tag: "vendor_debt_management.supplier_debt_owl_report",
        target: "current",
        context: {
            active_model: "supplier.invoice.payment.summary",
            active_id: row.summary_id,
            active_ids: [row.summary_id],
        },
        params: {
            summary_id: row.summary_id,
        },
    });
}
}

registry.category("actions").add(
    "vendor_debt_management.supplier_debt_real_report",
    SupplierDebtRealReport
);