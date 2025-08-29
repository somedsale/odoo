from odoo import models, fields

class SupplierSummaryWizard(models.TransientModel):
    _name = "supplier.summary.wizard"
    _description = "Wizard chọn nhà cung cấp"

    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        required=True,
        domain=[("supplier_rank", ">", 0)]
    )

    def action_view_report(self):
        """Mở báo cáo công nợ NCC HTML theo partner đã chọn"""
        # Lấy recordset lọc theo partner
        docs = self.env['supplier.summary'].search([('partner_id','=',self.partner_id.id)])
        return self.env.ref(
            "vendor_debt_management.action_report_supplier_summary_html"
        ).report_action(
            docs,
            data={
                "partner_name": self.partner_id.name
            }
        )
