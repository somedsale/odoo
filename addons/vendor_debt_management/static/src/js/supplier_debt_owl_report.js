/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SupplierDebtOwlReport extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            data: null,
            search: "",
            onlyResidual: false,
            onlyOrphanPayments: false,
            showPdfPreview: false,
            expandedProjects: {},
            expandedContracts: {},
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    get summaryId() {
        return (
            this.props?.action?.params?.summary_id ||
            this.props?.action?.context?.active_id ||
            false
        );
    }

    async loadData() {
        try {
            if (!this.summaryId) {
                this.notification.add("Không tìm thấy summary_id để mở báo cáo.", {
                    type: "danger",
                });
                this.state.loading = false;
                return;
            }

            const data = await this.orm.call(
                "supplier.invoice.payment.summary",
                "get_owl_report_data",
                [[this.summaryId]]
            );

            this.state.data = data;
            this.state.loading = false;

            for (const project of data.projects || []) {
                this.state.expandedProjects[project.id] = true;

                for (const contract of project.contracts || []) {
                    this.state.expandedContracts[`${project.id}_${contract.id}`] = true;
                }
            }
        } catch (error) {
            console.error("loadData error", error);
            this.notification.add("Không tải được dữ liệu báo cáo công nợ NCC.", {
                type: "danger",
            });
            this.state.loading = false;
        }
    }

    formatMoney(amount, symbol = "") {
        const value = Number(amount || 0);

        const formatted = new Intl.NumberFormat("vi-VN", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(value);

        return symbol ? `${formatted} ${symbol}` : formatted;
    }

    formatDate(dateStr) {
        if (!dateStr) {
            return "";
        }

        const [y, m, d] = String(dateStr).split("-");

        if (!y || !m || !d) {
            return dateStr;
        }

        return `${d}/${m}/${y}`;
    }

    onSearchInput(ev) {
        this.state.search = (ev.target.value || "").trim().toLowerCase();
    }

    toggleOnlyResidual() {
        this.state.onlyResidual = !this.state.onlyResidual;
    }

    toggleOnlyOrphanPayments() {
        this.state.onlyOrphanPayments = !this.state.onlyOrphanPayments;
    }

    togglePdfPreview() {
        this.state.showPdfPreview = !this.state.showPdfPreview;
    }

    toggleProject(projectId) {
        this.state.expandedProjects[projectId] = !this.state.expandedProjects[projectId];
    }

    toggleContract(projectId, contractId) {
        const key = `${projectId}_${contractId}`;
        this.state.expandedContracts[key] = !this.state.expandedContracts[key];
    }

    async printPdf() {
        try {
            const action = await this.orm.call(
                "supplier.invoice.payment.summary",
                "action_print_pdf_report",
                [[this.summaryId]]
            );

            if (action) {
                return this.action.doAction(action);
            }
        } catch (error) {
            console.error("printPdf error", error);
            this.notification.add("Không in được PDF báo cáo.", {
                type: "danger",
            });
        }
    }

    openPdfInNewTab() {
        const url = this.state.data?.summary?.pdf_url;

        if (url) {
            window.open(url, "_blank");
        }
    }

    openContract(contract) {
        const selection = window.getSelection?.().toString();

        if (selection) {
            return;
        }

        if (!contract || !contract.contract_id) {
            this.notification.add("Dòng này chưa có hợp đồng để mở.", {
                type: "warning",
            });
            return;
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Hợp đồng",
            res_model: contract.contract_model || "customer.contract",
            res_id: contract.contract_id,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
        });
    }

    openInvoice(row) {
        const selection = window.getSelection?.().toString();

        if (selection) {
            return;
        }

        if (!row || !row.invoice_id) {
            this.notification.add("Dòng này chưa có hóa đơn để mở.", {
                type: "warning",
            });
            return;
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Hóa đơn",
            res_model: row.invoice_model || "customer.invoice",
            res_id: row.invoice_id,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
        });
    }

    openPayment(row) {
        const selection = window.getSelection?.().toString();

        if (selection) {
            return;
        }

        if (!row || !row.payment_id) {
            this.notification.add("Dòng này chưa có phiếu chi để mở.", {
                type: "warning",
            });
            return;
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Phiếu chi",
            res_model: row.payment_model || "account.payment.request",
            res_id: row.payment_id,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
        });
    }

    getContractResidualTotal(rows) {
        /*
         * Cách tính đúng:
         * - 1 hóa đơn có thể có nhiều phiếu chi.
         * - Mỗi dòng phiếu chi có residual_display là số dư chạy.
         * - Không được cộng tất cả residual_display.
         * - Với mỗi invoice_id, chỉ lấy residual_display của dòng cuối cùng.
         */
        const invoiceResidualMap = new Map();
        let noInvoiceResidual = 0;

        for (const row of rows || []) {
            const hasResidual =
                row.residual_display !== false &&
                row.residual_display !== null &&
                row.residual_display !== undefined;

            if (!hasResidual) {
                continue;
            }

            const residualValue = Number(row.residual_display || 0);

            if (row.invoice_id) {
                invoiceResidualMap.set(row.invoice_id, residualValue);
            } else {
                noInvoiceResidual += residualValue;
            }
        }

        let total = noInvoiceResidual;

        for (const value of invoiceResidualMap.values()) {
            total += Number(value || 0);
        }

        return total;
    }

    get filteredProjects() {
        const projects = this.state.data?.projects || [];
        const term = this.state.search;

        const result = projects
            .map((project) => {
                const clonedProject = {
                    ...project,
                    contracts: (project.contracts || [])
                        .map((contract) => {
                            const rows = (contract.rows || []).filter((row) => {
                                if (
                                    this.state.onlyResidual &&
                                    !(Number(row.residual_display || 0) > 0)
                                ) {
                                    return false;
                                }

                                if (
                                    this.state.onlyOrphanPayments &&
                                    row.note !== "Không có hóa đơn"
                                ) {
                                    return false;
                                }

                                if (!term) {
                                    return true;
                                }

                                const haystack = [
                                    project.project_name,
                                    contract.contract_name,
                                    row.invoice_note,
                                    this.formatDate(contract.contract_date),
                                    row.invoice_name,
                                    this.formatDate(row.invoice_date),
                                    this.formatDate(row.invoice_due_date),
                                    row.payment_name,
                                    row.payment_note,
                                    this.formatDate(row.payment_date),
                                    row.note,
                                ]
                                    .filter(Boolean)
                                    .join(" ")
                                    .toLowerCase();

                                return haystack.includes(term);
                            });

                            return {
                                ...contract,
                                rows,
                                invoice_total: rows
                                    .filter((r) => r.show_invoice)
                                    .reduce(
                                        (sum, r) => sum + Number(r.invoice_amount || 0),
                                        0
                                    ),
                                payment_total: rows.reduce(
                                    (sum, r) => sum + Number(r.payment_amount || 0),
                                    0
                                ),
                                residual_total: this.getContractResidualTotal(rows),
                            };
                        })
                        .filter((contract) => contract.rows.length > 0),
                };

                clonedProject.invoice_total = clonedProject.contracts.reduce(
                    (sum, c) => sum + Number(c.invoice_total || 0),
                    0
                );

                clonedProject.payment_total = clonedProject.contracts.reduce(
                    (sum, c) => sum + Number(c.payment_total || 0),
                    0
                );

                clonedProject.residual_total = clonedProject.contracts.reduce(
                    (sum, c) => sum + Number(c.residual_total || 0),
                    0
                );

                return clonedProject;
            })
            .filter((project) => project.contracts.length > 0);

        // Đánh lại STT theo đúng thứ tự đang hiển thị từ trên xuống dưới
        for (const project of result) {
            let projectIndex = 1;

            for (const contract of project.contracts) {
                for (const row of contract.rows) {
                    row.display_stt = projectIndex++;
                }
            }
        }

        return result;
    }

    goBack() {
        window.history.back();
    }

    async shareReport() {
        try {
            const result = await this.orm.call(
                "supplier.invoice.payment.summary",
                "action_generate_share_link",
                [[this.summaryId]]
            );

            const shareUrl = result?.url || result?.share_url || result;

            if (!shareUrl) {
                this.notification.add("Không tạo được link chia sẻ.", {
                    type: "danger",
                });
                return;
            }

            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(shareUrl);
                this.notification.add("Đã copy link chia sẻ vào clipboard.", {
                    type: "success",
                });
            } else {
                window.prompt("Copy link chia sẻ:", shareUrl);
            }

            window.open(shareUrl, "_blank");
        } catch (error) {
            console.error("shareReport error", error);
            this.notification.add("Không tạo được link chia sẻ.", {
                type: "danger",
            });
        }
    }

    async openRecordList(type) {
        if (!this.summaryId) {
            return;
        }

        const mapping = {
            invoices: "action_open_invoices",
            contracts: "action_open_contracts",
            payments: "action_open_payments",
        };

        const method = mapping[type];

        if (!method) {
            return;
        }

        const action = await this.orm.call(
            "supplier.invoice.payment.summary",
            method,
            [[this.summaryId]]
        );

        if (action) {
            this.action.doAction(action);
        }
    }
}

SupplierDebtOwlReport.template = "vendor_debt_management.SupplierDebtOwlReport";

registry.category("actions").add(
    "vendor_debt_management.supplier_debt_owl_report",
    SupplierDebtOwlReport
);