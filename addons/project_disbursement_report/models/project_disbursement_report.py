# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectDisbursementReport(models.Model):
    _name = "project.disbursement.report"
    _description = "Báo cáo giải ngân theo dự án"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "report_date desc, id desc"

    name = fields.Char(string="Tên báo cáo", required=True, default="New", tracking=True)
    project_id = fields.Many2one("project.project", string="Dự án", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Công ty",
        related="project_id.company_id", store=True, readonly=True
    )
    currency_id = fields.Many2one(
        "res.currency", string="Tiền tệ",
        related="company_id.currency_id", store=True, readonly=True
    )
    partner_id = fields.Many2one(
        "res.partner", string="Khách hàng",
        related="project_id.partner_id", store=True, readonly=True
    )

    report_date = fields.Date(string="Ngày báo cáo", default=fields.Date.context_today, required=True)
    date_from = fields.Date(string="Từ ngày")
    date_to = fields.Date(string="Đến ngày")

    state = fields.Selection([
        ("draft", "Nháp"),
        ("confirmed", "Xác nhận"),
    ], default="draft", string="Trạng thái", tracking=True)

    invoice_ids = fields.Many2many(
        "customer.invoice",
        string="Chi tiết hóa đơn",
        compute="_compute_invoice_ids",
        compute_sudo=True,
    )

    account_receipt_ids = fields.Many2many(
        "account.receipt",
        string="Chi tiết phiếu thu",
        compute="_compute_account_receipt_ids",
        compute_sudo=True,
    )

    invoice_count = fields.Integer(string="Số hóa đơn", compute="_compute_totals", store=False)
    receipt_count = fields.Integer(string="Số phiếu thu", compute="_compute_totals", store=False)
    amount_invoice_total = fields.Monetary(string="Tổng giá trị hóa đơn", compute="_compute_totals", store=False)
    amount_received_total = fields.Monetary(string="Tổng đã thu", compute="_compute_totals", store=False)
    amount_remaining_total = fields.Monetary(string="Còn phải thu", compute="_compute_totals", store=False)
    receipt_percent_total = fields.Float(string="Tỷ lệ thu (%)", compute="_compute_totals", store=False)

    note = fields.Text(string="Ghi chú")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                project_name = False
                if vals.get("project_id"):
                    project = self.env["project.project"].browse(vals["project_id"])
                    project_name = project.name
                date_str = fields.Date.context_today(self).strftime("%d/%m/%Y")
                vals["name"] = f"Báo cáo giải ngân - {project_name or 'Dự án'} - {date_str}"
        return super().create(vals_list)

    def _get_invoice_domain(self):
        self.ensure_one()
        domain = [("project_id", "=", self.project_id.id)]
        if self.date_from:
            domain.append(("date", ">=", self.date_from))
        if self.date_to:
            domain.append(("date", "<=", self.date_to))
        return domain

    def _get_receipt_domain(self):
        self.ensure_one()
        domain = [
            ("project_id", "=", self.project_id.id),
            ("state", "=", "posted"),
        ]
        if self.date_from:
            domain.append(("date", ">=", self.date_from))
        if self.date_to:
            domain.append(("date", "<=", self.date_to))
        return domain

    @api.depends("project_id", "date_from", "date_to")
    def _compute_invoice_ids(self):
        Invoice = self.env["customer.invoice"].sudo()
        for rec in self:
            if not rec.project_id:
                rec.invoice_ids = [(5, 0, 0)]
                continue

            invoices = Invoice.search(rec._get_invoice_domain(), order="date asc, id asc")
            rec.invoice_ids = [(6, 0, invoices.ids)]

    @api.depends("project_id", "date_from", "date_to")
    def _compute_account_receipt_ids(self):
        Receipt = self.env["account.receipt"].sudo()
        for rec in self:
            if not rec.project_id:
                rec.account_receipt_ids = [(5, 0, 0)]
                continue

            receipts = Receipt.search(rec._get_receipt_domain(), order="date asc, id asc")
            rec.account_receipt_ids = [(6, 0, receipts.ids)]

    @api.depends(
        "project_id",
        "date_from",
        "date_to",
        "invoice_ids",
        "invoice_ids.amount_total",
        "account_receipt_ids",
        "account_receipt_ids.amount",
        "account_receipt_ids.state",
    )
    def _compute_totals(self):
        for rec in self:
            invoices = rec.invoice_ids
            receipts = rec.account_receipt_ids.filtered(lambda r: r.state == "posted")

            rec.invoice_count = len(invoices)
            rec.receipt_count = len(receipts)
            rec.amount_invoice_total = sum(invoices.mapped("amount_total") or [0.0])
            rec.amount_received_total = sum(receipts.mapped("amount") or [0.0])
            rec.amount_remaining_total = rec.amount_invoice_total - rec.amount_received_total
            rec.receipt_percent_total = (
                (rec.amount_received_total / rec.amount_invoice_total) * 100.0
                if rec.amount_invoice_total else 0.0
            )

    @api.onchange("project_id", "date_from", "date_to")
    def _onchange_project_or_date(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise UserError(_("Từ ngày không được lớn hơn Đến ngày."))

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_reset_draft(self):
        self.write({"state": "draft"})