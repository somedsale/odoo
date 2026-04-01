# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ProjectProject(models.Model):
    _inherit = "project.project"

    customer_invoice_ids = fields.One2many(
        "customer.invoice",
        "project_id",
        string="Hóa đơn khách hàng",
    )

    account_receipt_ids = fields.One2many(
        "account.receipt",
        "project_id",
        string="Phiếu thu",
    )

    customer_invoice_count = fields.Integer(
        string="Số hóa đơn",
        compute="_compute_customer_invoice_stats",
    )
    customer_invoice_untaxed_total = fields.Monetary(
        string="Tổng giá trị chưa thuế",
        compute="_compute_customer_invoice_stats",
        currency_field="currency_id",
    )
    customer_invoice_amount_total = fields.Monetary(
        string="Tổng giá trị hóa đơn",
        compute="_compute_customer_invoice_stats",
        currency_field="currency_id",
    )

    customer_invoice_received_total = fields.Monetary(
        string="Đã thu",
        compute="_compute_customer_invoice_stats",
        currency_field="currency_id",
    )

    customer_invoice_remaining_total = fields.Monetary(
        string="Còn phải thu",
        compute="_compute_customer_invoice_stats",
        currency_field="currency_id",
    )

    payment_process_percent = fields.Float(
        string="% Tiền đã thu so với giá trị quyết toán",
        compute="_compute_customer_invoice_stats",
        store=False,
    )
    payment_vs_acceptance_percent = fields.Float(
        string="% Tiền đã thu so với nghiệm thu",
        compute="_compute_customer_invoice_stats",
        store=False,
    )
    payment_vs_completed_percent = fields.Float(
        string="% Tiền đã thu so với sản lượng đã thực hiện",
        compute="_compute_customer_invoice_stats",
        store=False,
    )
    payment_vs_invoice_percent = fields.Float(
        string="% Tiền đã thu so với hóa đơn",
        compute="_compute_customer_invoice_stats",
        store=False,
    )
    receivable_by_finalization_total = fields.Monetary(
        string="Phải thu theo thanh/quyết toán",
        compute="_compute_customer_invoice_stats",
        currency_field="currency_id",
    )
    @api.depends(
        "customer_invoice_ids",
        "customer_invoice_ids.amount_total",
        "customer_invoice_ids.amount_untaxed",
        "account_receipt_ids",
        "account_receipt_ids.amount",
        "account_receipt_ids.state",
        "work_item_ids.value_finalized_tax",
        "work_item_ids.value_accepted_tax",
        "work_item_ids.value_completed",
        "work_item_ids.value_done_tax",
        "value_finalized",
        "value_accepted",
        "value_completed",
    )
    def _compute_customer_invoice_stats(self):
        """
        Tổng hóa đơn: lấy từ customer.invoice theo project
        Tổng đã thu: lấy trực tiếp từ account.receipt theo project, KHÔNG phụ thuộc invoice

        - customer_invoice_remaining_total: còn phải thu theo hóa đơn
        - receivable_by_finalization_total: phải thu theo thanh/quyết toán
        """
        Invoice = self.env["customer.invoice"].sudo()
        Receipt = self.env["account.receipt"].sudo()

        counts = {}
        if self.ids:
            data = Invoice.read_group(
                [("project_id", "in", self.ids)],
                ["project_id"],
                ["project_id"],
            )
            counts = {
                d["project_id"][0]: d["project_id_count"]
                for d in data
                if d.get("project_id")
            }

        for rec in self:
            rec.customer_invoice_count = counts.get(rec.id, 0)

            invoices = Invoice.search([("project_id", "=", rec.id)])
            receipts = Receipt.search([
                ("project_id", "=", rec.id),
                ("state", "=", "posted"),
            ])

            total_invoice = sum(invoices.mapped("amount_total") or [0.0])
            total_untaxed = sum(invoices.mapped("amount_untaxed") or [0.0])
            total_received = sum(receipts.mapped("amount") or [0.0])

            # Còn phải thu theo hóa đơn
            total_remaining_invoice = total_invoice - total_received

            # Phải thu theo thanh/quyết toán
            total_remaining_finalization = (rec.value_finalized or 0.0) - total_received

            rec.customer_invoice_amount_total = total_invoice
            rec.customer_invoice_received_total = total_received
            rec.customer_invoice_remaining_total = total_remaining_invoice
            rec.receivable_by_finalization_total = total_remaining_finalization
            rec.customer_invoice_untaxed_total = total_untaxed

            rec.payment_process_percent = (
                (total_received / rec.value_finalized) * 100.0
                if rec.value_finalized else 0.0
            )
            rec.payment_vs_acceptance_percent = (
                (total_received / rec.value_accepted) * 100.0
                if rec.value_accepted else 0.0
            )
            rec.payment_vs_completed_percent = (
                (total_received / rec.value_completed) * 100.0
                if rec.value_completed else 0.0
            )
            rec.payment_vs_invoice_percent = (
                (total_received / total_invoice) * 100.0
                if total_invoice else 0.0
            )
    def action_view_customer_invoices(self):
        """Mở màn hình báo cáo giải ngân và lọc đúng dự án hiện tại."""
        self.ensure_one()

        action = self.env.ref(
            "project_disbursement_report.action_project_disbursement_dashboard"
        ).read()[0]

        action["domain"] = [("project_id", "=", self.id)]
        action["context"] = {
            "default_project_id": self.id,
            "search_default_group_partner": 0,
        }

        return action