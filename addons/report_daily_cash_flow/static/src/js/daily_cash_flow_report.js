/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

function todayISO() {
    const date = new Date();

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");

    return `${year}-${month}-${day}`;
}

function currentQuarter() {
    const month = new Date().getMonth() + 1;
    return String(Math.floor((month - 1) / 3) + 1);
}

export class DailyCashFlowReport extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const now = new Date();

        this.state = useState({
            loading: false,
            syncingOpening: false,
            report: null,

            filters: {
                period_type: "custom",
                date_from: todayISO(),
                date_to: todayISO(),
                month: String(now.getMonth() + 1),
                quarter: currentQuarter(),
                year: now.getFullYear(),
                opening_bank: 0,
                opening_cash: 0,
            },

            pagination: {
                page: 1,
                pageSize: 20,
            },
        });

        onWillStart(async () => {
            await this.syncOpeningByFilter();
            await this.loadReport();
        });
    }

    get months() {
        return Array.from({ length: 12 }, (_, index) => {
            const value = String(index + 1);
            return {
                value,
                label: `Tháng ${value}`,
            };
        });
    }

    get quarters() {
        return [
            { value: "1", label: "Q1" },
            { value: "2", label: "Q2" },
            { value: "3", label: "Q3" },
            { value: "4", label: "Q4" },
        ];
    }

    // =========================================================
    // Pagination
    // =========================================================
    get pageSizeOptions() {
        return [10, 20, 50, 100];
    }

    get totalRows() {
        if (!this.state.report || !this.state.report.rows) {
            return 0;
        }

        return this.state.report.rows.length;
    }

    get totalPages() {
        if (!this.totalRows) {
            return 1;
        }

        return Math.max(1, Math.ceil(this.totalRows / this.state.pagination.pageSize));
    }

    get currentPage() {
        return Math.min(this.state.pagination.page, this.totalPages);
    }

    get pageStart() {
        if (!this.totalRows) {
            return 0;
        }

        return (this.currentPage - 1) * this.state.pagination.pageSize + 1;
    }

    get pageEnd() {
        if (!this.totalRows) {
            return 0;
        }

        return Math.min(
            this.currentPage * this.state.pagination.pageSize,
            this.totalRows
        );
    }

    get paginatedRows() {
        if (!this.state.report || !this.state.report.rows) {
            return [];
        }

        const start = (this.currentPage - 1) * this.state.pagination.pageSize;
        const end = start + this.state.pagination.pageSize;

        return this.state.report.rows.slice(start, end);
    }

    get visiblePageNumbers() {
        const total = this.totalPages;
        const current = this.currentPage;

        const pages = [];

        let start = Math.max(1, current - 2);
        let end = Math.min(total, current + 2);

        if (current <= 2) {
            end = Math.min(total, 5);
        }

        if (current >= total - 1) {
            start = Math.max(1, total - 4);
        }

        for (let page = start; page <= end; page++) {
            pages.push(page);
        }

        return pages;
    }

    setPageSize(ev) {
        const pageSize = Number(ev.target.value || 20);

        this.state.pagination.pageSize = pageSize;
        this.state.pagination.page = 1;
    }

    goToPage(page) {
        const targetPage = Number(page || 1);

        if (targetPage < 1) {
            this.state.pagination.page = 1;
            return;
        }

        if (targetPage > this.totalPages) {
            this.state.pagination.page = this.totalPages;
            return;
        }

        this.state.pagination.page = targetPage;
    }

    prevPage() {
        this.goToPage(this.currentPage - 1);
    }

    nextPage() {
        this.goToPage(this.currentPage + 1);
    }

    // =========================================================
    // Format tiền hiển thị trên bảng
    // =========================================================
    formatMoney(value) {
        const amount = Number(value || 0);

        return new Intl.NumberFormat("vi-VN", {
            maximumFractionDigits: 0,
        }).format(amount);
    }

    // =========================================================
    // Format tiền cho input tồn đầu kỳ
    // =========================================================
    parseInputMoney(value) {
        if (value === null || value === undefined) {
            return 0;
        }

        const cleanValue = String(value)
            .replace(/\./g, "")
            .replace(/,/g, "")
            .replace(/\s/g, "")
            .replace(/[^\d-]/g, "");

        const numberValue = Number(cleanValue);

        if (!Number.isFinite(numberValue)) {
            return 0;
        }

        return numberValue;
    }

    formatInputMoney(value) {
        const numberValue = this.parseInputMoney(value);

        if (!numberValue) {
            return "";
        }

        return new Intl.NumberFormat("vi-VN", {
            maximumFractionDigits: 0,
        }).format(numberValue);
    }

    onMoneyFocus(ev) {
        const name = ev.target.name;
        const value = this.state.filters[name] || 0;

        ev.target.value = value ? String(value) : "";
        ev.target.select();
    }

    onMoneyInput(ev) {
        const name = ev.target.name;
        const value = this.parseInputMoney(ev.target.value);

        this.state.filters[name] = value;
    }

    onMoneyBlur(ev) {
        const name = ev.target.name;
        const value = this.parseInputMoney(ev.target.value);

        this.state.filters[name] = value;
        ev.target.value = this.formatInputMoney(value);
    }

    // =========================================================
    // Filter
    // =========================================================
    updateFilterValue(ev) {
        const name = ev.target.name;
        let value = ev.target.value;

        if (name === "year") {
            value = value === "" ? 0 : Number(value);
        }

        this.state.filters[name] = value;
    }

    async updateFilter(ev) {
        const name = ev.target.name;

        this.updateFilterValue(ev);

        const dateFields = [
            "period_type",
            "date_from",
            "date_to",
            "month",
            "quarter",
            "year",
        ];

        if (dateFields.includes(name)) {
            await this.syncOpeningByFilter();
            await this.loadReport();
        }
    }

    async syncOpeningByFilter() {
        this.state.syncingOpening = true;

        try {
            const data = await this.orm.call(
                "daily.cash.flow.wizard",
                "get_opening_from_filters",
                [this.state.filters]
            );

            this.state.filters.date_from = data.date_from;
            this.state.filters.date_to = data.date_to;

            this.state.filters.opening_bank = data.opening_bank || 0;
            this.state.filters.opening_cash = data.opening_cash || 0;
        } catch (error) {
            this.notification.add(
                error?.message || "Không lấy được tồn đầu kỳ.",
                { type: "danger" }
            );
        } finally {
            this.state.syncingOpening = false;
        }
    }

    async loadReport() {
        this.state.loading = true;

        try {
            const data = await this.orm.call(
                "daily.cash.flow.wizard",
                "get_report_data",
                [this.state.filters]
            );

            this.state.report = data;

            this.state.filters.opening_bank = data.opening_bank || 0;
            this.state.filters.opening_cash = data.opening_cash || 0;

            // Mỗi lần tải dữ liệu mới thì quay về trang 1.
            this.state.pagination.page = 1;

            if (!data.has_opening_snapshot && (data.opening_bank || data.opening_cash)) {
                this.notification.add(
                    "Đã lưu tồn đầu kỳ nhập tay làm tồn cuối của ngày trước kỳ lọc.",
                    { type: "success" }
                );
            }
        } catch (error) {
            this.notification.add(
                error?.message || "Không tải được báo cáo thu chi.",
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    async exportExcel() {
        try {
            const action = await this.orm.call(
                "daily.cash.flow.wizard",
                "action_export_excel_from_filters",
                [this.state.filters]
            );

            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(
                error?.message || "Không xuất được Excel.",
                { type: "danger" }
            );
        }
    }

    async exportPdf() {
        try {
            const action = await this.orm.call(
                "daily.cash.flow.wizard",
                "action_export_pdf_from_filters",
                [this.state.filters]
            );

            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(
                error?.message || "Không xuất được PDF.",
                { type: "danger" }
            );
        }
    }

    async openReceipt(row) {
        if (!row.receipt_id) {
            return;
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.receipt",
            res_id: row.receipt_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openPayment(row) {
        if (!row.payment_id) {
            return;
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.payment.request",
            res_id: row.payment_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

DailyCashFlowReport.template = "report_daily_cash_flow.DailyCashFlowReport";

registry.category("actions").add("daily_cash_flow_report_owl", DailyCashFlowReport);