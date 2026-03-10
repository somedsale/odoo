# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ProjectProject(models.Model):
    _inherit = "project.project"

    customer_invoice_ids = fields.One2many(
        "customer.invoice",
        "project_id",
        string="Hóa đơn khách hàng",
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
        store=False,    )
    # Mới
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
    @api.depends(
        "customer_invoice_ids",
        "customer_invoice_ids.amount_total",
        "customer_invoice_ids.amount_untaxed",
        "customer_invoice_ids.account_receipt_ids",
        "work_item_ids.claim_value_done",
                "work_item_ids.claim_value_done",
        "work_item_ids.acceptance_value_done",
        "work_item_ids.value_completed",
    )
    def _compute_customer_invoice_stats(self):
        """
        Dùng sudo để tránh lỗi quyền khi render form project.
        Nếu customer.invoice đã có field:
        - receipt_amount_total
        thì dùng luôn. Nếu chưa có thì fallback cộng từ account_receipt_ids.

        customer_invoice_remaining_total = claim_value_done - customer_invoice_received_total
        """
        Invoice = self.env["customer.invoice"].sudo()

        # Đếm nhanh theo batch
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
            total_invoice = sum(invoices.mapped("amount_total") or [0.0])
            total_untaxed = sum(invoices.mapped("amount_untaxed") or [0.0])

            total_received = 0.0

            for inv in invoices:
                # Ưu tiên field tổng đã thu nếu đã có trên customer.invoice
                if "receipt_amount_total" in inv._fields:
                    total_received += inv.receipt_amount_total or 0.0
                else:
                    # fallback cộng từ phiếu thu
                    receipt_sum = 0.0
                    for r in inv.account_receipt_ids:
                        if "state" in r._fields and r.state in ("draft", "cancel"):
                            continue
                        if "amount" in r._fields:
                            receipt_sum += r.amount or 0.0
                        elif "amount_total" in r._fields:
                            receipt_sum += r.amount_total or 0.0
                    total_received += receipt_sum

            # ✅ MỚI: Còn lại = Giá trị quyết toán - Đã thu
            total_remaining = (rec.claim_value_done or 0.0) - (total_received or 0.0)

            rec.customer_invoice_amount_total = total_invoice
            rec.customer_invoice_received_total = total_received
            rec.customer_invoice_remaining_total = total_remaining
            rec.customer_invoice_untaxed_total = total_untaxed
            rec.payment_process_percent = (
                (total_received / rec.claim_value_done) * 100.0
                if rec.claim_value_done else 0.0
            )
            rec.payment_vs_acceptance_percent = (
                (total_received / rec.acceptance_value_done) * 100.0
                if rec.acceptance_value_done else 0.0
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

        action["domain"] = [("id", "=", self.id)]
        action["context"] = {
            "default_project_id": self.id,
            "search_default_group_partner": 0,
        }

        return action