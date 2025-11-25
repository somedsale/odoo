from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.misc import format_amount
from odoo.tools import format_date


class SupplierSummaryWizard(models.TransientModel):
    _name = "supplier.summary.wizard"
    _description = "Wizard chọn nhà cung cấp"

    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        required=True,
        domain=lambda self: self._get_partner_domain(),
    )

    @api.model
    def _get_partner_domain(self):
        """Chỉ cho chọn NCC có dòng trong supplier.invoice.payment.summary"""
        summary = self.env["supplier.invoice.payment.summary"].search([])
        partner_ids = summary.mapped("partner_id").ids
        return [("id", "in", partner_ids)]

    def action_view_report(self):
        """Mở báo cáo chi tiết công nợ NCC (HTML) theo NCC đã chọn"""
        Summary = self.env["supplier.invoice.payment.summary"]

        docs = Summary.search([("partner_id", "=", self.partner_id.id)])
        if not docs:
            raise UserError("Không tìm thấy dữ liệu công nợ cho nhà cung cấp này.")

        return self.env.ref(
            "vendor_debt_management.action_report_supplier_summary_html"
        ).report_action(
            docs,
            data={
                "partner_id": self.partner_id.id,
                "partner_name": self.partner_id.name,
            },
        )


class ReportSupplierSummary(models.AbstractModel):
    _name = "report.vendor_debt_management.report_sup_summary_html"
    _description = "Supplier Invoice Payment Summary Detail Report"

    def _get_report_values(self, docids, data=None):
        Summary = self.env["supplier.invoice.payment.summary"]

        partner_id = data.get("partner_id") if data else False
        if partner_id:
            docs = Summary.search([("partner_id", "=", partner_id)])
        else:
            docs = Summary.browse(docids)

        # Lọc: chỉ giữ NCC còn công nợ hoặc tạm ứng
        docs = docs.filtered(
            lambda r: (r.residual_amount or 0.0) != 0.0
            or (r.advance_amount or 0.0) != 0.0
        )

        return {
            "doc_ids": docs.ids,
            "doc_model": "supplier.invoice.payment.summary",
            "docs": docs,
            "partner_name": data.get("partner_name") if data else False,
            "format_amount": lambda amount, currency: format_amount(
                self.env, amount, currency
            ),
            "user_id": self.env.user,
            "format_date": lambda d: format_date(
                self.env, d, date_format="dd/MM/yyyy"
            ),
        }
