from odoo import models, fields, api
from odoo.exceptions import UserError


class SupplierSummaryWizard(models.TransientModel):
    _name = "supplier.summary.wizard"
    _description = "Wizard chọn nhà cung cấp"

    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        required=True,
        domain=lambda self: self._get_partner_domain(),
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        required=True,
        domain="[('id', 'in', available_currency_ids)]",
    )

    available_currency_ids = fields.Many2many(
        "res.currency",
        compute="_compute_available_currency_ids",
        string="Danh sách tiền tệ khả dụng",
    )

    @api.model
    def _get_partner_domain(self):
        """Chỉ cho chọn NCC có dòng trong supplier.invoice.payment.summary"""
        summary = self.env["supplier.invoice.payment.summary"].search([])
        partner_ids = summary.mapped("partner_id").ids
        return [("id", "in", partner_ids)]

    @api.depends("partner_id")
    def _compute_available_currency_ids(self):
        Summary = self.env["supplier.invoice.payment.summary"]
        for rec in self:
            if rec.partner_id:
                summaries = Summary.search([("partner_id", "=", rec.partner_id.id)])
                rec.available_currency_ids = summaries.mapped("currency_id")
            else:
                rec.available_currency_ids = False

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.currency_id = False
        if self.partner_id:
            summaries = self.env["supplier.invoice.payment.summary"].search([
                ("partner_id", "=", self.partner_id.id)
            ])
            currencies = summaries.mapped("currency_id")
            if len(currencies) == 1:
                self.currency_id = currencies[0]

    def action_view_report(self):
        """Mở OWL report theo NCC + tiền tệ đã chọn"""
        self.ensure_one()
        Summary = self.env["supplier.invoice.payment.summary"]

        summary = Summary.search([
            ("partner_id", "=", self.partner_id.id),
            ("currency_id", "=", self.currency_id.id),
        ], limit=1)

        if not summary:
            raise UserError("Không tìm thấy dữ liệu công nợ cho nhà cung cấp và tiền tệ này.")

        return {
            "type": "ir.actions.client",
            "tag": "vendor_debt_management.supplier_debt_owl_report",
            "name": "Báo cáo công nợ NCC",
            "context": {
                "active_id": summary.id,
                "active_model": "supplier.invoice.payment.summary",
            },
            "params": {
                "summary_id": summary.id,
            },
            "target": "current",
        }