/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const STORAGE_KEY = "monthly_revenue_expense_report_filters";

export class RevenueExpenseReport extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const today = new Date();
        const actionFilters = this.props.action.params?.filters || {};
        const savedFilters = this.getSavedFilters();

        this.state = useState({
            loading: true,
            exportingExcel: false,
            exportingPdf: false,
            search: savedFilters.search || "",
            filters: {
                period_type:
                    actionFilters.period_type ||
                    savedFilters.period_type ||
                    "month",

                month:
                    actionFilters.month ||
                    savedFilters.month ||
                    String(today.getMonth() + 1),

                quarter:
                    actionFilters.quarter ||
                    savedFilters.quarter ||
                    "1",

                year:
                    actionFilters.year ||
                    savedFilters.year ||
                    String(today.getFullYear()),
            },
            data: null,
        });

        this.monthOptions = Array.from({ length: 12 }, (_, i) => ({
            value: String(i + 1),
            label: `Tháng ${i + 1}`,
        }));

        this.quarterOptions = [
            { value: "1", label: "Quý I" },
            { value: "2", label: "Quý II" },
            { value: "3", label: "Quý III" },
            { value: "4", label: "Quý IV" },
        ];

        this.yearOptions = [];
        const currentYear = today.getFullYear();

        for (let y = currentYear - 5; y <= currentYear + 2; y++) {
            this.yearOptions.push({
                value: String(y),
                label: String(y),
            });
        }

        onWillStart(async () => {
            await this.loadReport();
        });
    }

    getSavedFilters() {
        try {
            const raw = sessionStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (error) {
            return {};
        }
    }

    saveFilters() {
        try {
            sessionStorage.setItem(
                STORAGE_KEY,
                JSON.stringify({
                    period_type: this.state.filters.period_type,
                    month: this.state.filters.month,
                    quarter: this.state.filters.quarter,
                    year: this.state.filters.year,
                    search: this.state.search || "",
                })
            );
        } catch (error) {
            // ignore
        }
    }

    getCurrentFilters() {
        return {
            period_type: this.state.filters.period_type,
            month: this.state.filters.month,
            quarter: this.state.filters.quarter,
            year: this.state.filters.year,
        };
    }

    async loadReport() {
        this.state.loading = true;
        this.saveFilters();

        this.state.data = await this.orm.call(
            "monthly.revenue.expense.report",
            "get_owl_report_data",
            [],
            {
                filters: this.getCurrentFilters(),
            }
        );

        this.state.loading = false;
    }

    async exportExcel() {
        this.state.exportingExcel = true;
        this.saveFilters();

        try {
            const action = await this.orm.call(
                "monthly.revenue.expense.report",
                "action_export_excel_from_filters",
                [],
                {
                    filters: this.getCurrentFilters(),
                }
            );

            await this.action.doAction(action);
        } finally {
            this.state.exportingExcel = false;
        }
    }

    async exportPdf() {
        this.state.exportingPdf = true;
        this.saveFilters();

        try {
            const action = await this.orm.call(
                "monthly.revenue.expense.report",
                "action_export_pdf_from_filters",
                [],
                {
                    filters: this.getCurrentFilters(),
                }
            );

            await this.action.doAction(action);
        } finally {
            this.state.exportingPdf = false;
        }
    }

    async editExpenseBucketName(ev, line) {
        ev.stopPropagation();

        if (!line || !line.bucket_id) {
            return;
        }

        const oldName = line.name || "";
        const newName = window.prompt("Nhập tên khoản mục báo cáo mới:", oldName);

        if (newName === null) {
            return;
        }

        const cleanName = String(newName || "").trim();

        if (!cleanName) {
            window.alert("Tên khoản mục không được để trống.");
            return;
        }

        if (cleanName === oldName) {
            return;
        }

        await this.orm.call(
            "monthly.revenue.expense.report",
            "update_expense_bucket_name",
            [],
            {
                bucket_id: line.bucket_id,
                new_name: cleanName,
            }
        );

        await this.loadReport();
    }

    formatMoney(value) {
        const number = Number(value || 0);
        return number.toLocaleString("vi-VN");
    }

    normalizeText(value) {
        return String(value || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    matchSearch(value) {
        const keyword = this.normalizeText(this.state.search);

        if (!keyword) {
            return true;
        }

        return this.normalizeText(value).includes(keyword);
    }

    get filteredRevenueData() {
        const data = this.state.data?.revenue_data || [];
        this.saveFilters();

        if (!this.state.search) {
            return data;
        }

        return data
            .map((grp) => {
                const groupMatched = this.matchSearch(grp.type_label);

                const projects = (grp.projects || []).filter((line) => {
                    return groupMatched || this.matchSearch(line.name);
                });

                if (groupMatched || projects.length) {
                    return {
                        ...grp,
                        projects,
                    };
                }

                return null;
            })
            .filter(Boolean);
    }

    get filteredExpenseData() {
        const data = this.state.data?.expense_data || [];
        this.saveFilters();

        if (!this.state.search) {
            return data;
        }

        return data
            .map((grp) => {
                const groupMatched = this.matchSearch(grp.type_label);

                if (grp.subgroups) {
                    const subgroups = grp.subgroups
                        .map((sub) => {
                            const subMatched = this.matchSearch(sub.sub_label);

                            const lines = (sub.lines || []).filter((line) => {
                                return (
                                    groupMatched ||
                                    subMatched ||
                                    this.matchSearch(line.name)
                                );
                            });

                            if (groupMatched || subMatched || lines.length) {
                                return {
                                    ...sub,
                                    lines,
                                };
                            }

                            return null;
                        })
                        .filter(Boolean);

                    if (groupMatched || subgroups.length) {
                        return {
                            ...grp,
                            subgroups,
                        };
                    }

                    return null;
                }

                const lines = (grp.lines || []).filter((line) => {
                    return groupMatched || this.matchSearch(line.name);
                });

                if (groupMatched || lines.length) {
                    return {
                        ...grp,
                        lines,
                    };
                }

                return null;
            })
            .filter(Boolean);
    }

    openDetail(line, title) {
        if (!line || !line.model || !line.domain) {
            return;
        }

        this.saveFilters();

        this.action.doAction({
            type: "ir.actions.act_window",
            name: title || "Chi tiết",
            res_model: line.model,
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: line.domain,
            target: "current",
            context: {
                active_test: false,
            },
        });
    }

    clearFilters() {
        const today = new Date();

        this.state.search = "";
        this.state.filters.period_type = "month";
        this.state.filters.month = String(today.getMonth() + 1);
        this.state.filters.quarter = "1";
        this.state.filters.year = String(today.getFullYear());

        try {
            sessionStorage.removeItem(STORAGE_KEY);
        } catch (error) {
            // ignore
        }

        this.loadReport();
    }
}

RevenueExpenseReport.template = "monthly_revenue_expense_report.RevenueExpenseReport";

registry.category("actions").add(
    "monthly_revenue_expense_report.owl_report",
    RevenueExpenseReport
);