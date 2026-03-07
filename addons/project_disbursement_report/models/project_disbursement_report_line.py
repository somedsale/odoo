# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectDisbursementReportLine(models.Model):
    _name = "project.disbursement.report.line"
    _description = "Chi tiết báo cáo giải ngân theo hóa đơn"
    _order = "invoice_date asc, id asc"

    report_id = fields.Many2one(
        "project.disbursement.report",
        string="Báo cáo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    currency_id = fields.Many2one(
        related="report_id.currency_id",
        store=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        related="report_id.project_id",
        store=True,
        readonly=True,
    )

    invoice_id = fields.Many2one("customer.invoice", string="Hóa đơn", required=True, ondelete="restrict")

    invoice_name = fields.Char(related="invoice_id.name", string="Mã hóa đơn", store=True, readonly=True)
    invoice_number = fields.Char(related="invoice_id.invoice_number", string="Số hóa đơn", store=True, readonly=True)
    invoice_date = fields.Date(related="invoice_id.date", string="Ngày hóa đơn", store=True, readonly=True)
    partner_id = fields.Many2one(related="invoice_id.partner_id", store=True, readonly=True)

    amount_untaxed = fields.Monetary(related="invoice_id.amount_untaxed", string="Trước thuế", store=True, readonly=True)
    amount_tax = fields.Monetary(related="invoice_id.amount_tax", string="Thuế", store=True, readonly=True)
    amount_total = fields.Monetary(related="invoice_id.amount_total", string="Tổng hóa đơn", store=True, readonly=True)

    receipt_amount_total = fields.Monetary(
        related="invoice_id.receipt_amount_total",
        string="Đã thu",
        store=True,
        readonly=True,
    )
    receivable_remaining = fields.Monetary(
        related="invoice_id.receivable_remaining",
        string="Còn phải thu",
        store=True,
        readonly=True,
    )
    receipt_percent = fields.Float(
        related="invoice_id.receipt_percent",
        string="Tỷ lệ thu (%)",
        store=True,
        readonly=True,
    )

    receipt_count = fields.Integer(string="Số phiếu thu", compute="_compute_receipt_count")
    note = fields.Char(string="Ghi chú")

    @api.depends("invoice_id.account_receipt_ids")
    def _compute_receipt_count(self):
        for rec in self:
            rec.receipt_count = len(rec.invoice_id.account_receipt_ids) if rec.invoice_id else 0

    def action_open_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Hóa đơn khách hàng",
            "res_model": "customer.invoice",
            "res_id": self.invoice_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_receipts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Phiếu thu",
            "res_model": "account.receipt",
            "view_mode": "tree,form",
            "domain": [("invoice_id", "=", self.invoice_id.id)],
            "context": {"default_invoice_id": self.invoice_id.id},
            "target": "current",
        }