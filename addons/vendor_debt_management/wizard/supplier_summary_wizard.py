from odoo import models, fields,api
from odoo.exceptions import UserError
from odoo.tools.misc import format_amount
from odoo.tools import format_date
import datetime
class SupplierSummaryWizard(models.TransientModel):
    _name = "supplier.summary.wizard"
    _description = "Wizard chọn nhà cung cấp"

    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        required=True,
        # domain=[("supplier_rank", ">", 0)]
        domain=lambda self: self._get_partner_domain(),
    )
    @api.model
    def _get_partner_domain(self):
        # Lấy partner_id từ supplier.summary (có dữ liệu công nợ)
        partner_ids = self.env["supplier.summary"].search([]).mapped("partner_id").ids
        return [("id", "in", partner_ids)]

    def action_view_report(self):
        """Mở báo cáo công nợ NCC HTML theo partner đã chọn"""
        # Lấy recordset lọc theo partner
        docs = self.env['supplier.summary'].search([('partner_id', '=', self.partner_id.id)])
        
        # Kiểm tra nếu không có bản ghi
        if not docs:
            raise UserError("Không tìm thấy dữ liệu công nợ cho nhà cung cấp này.")
        
        # Gọi report_action với docs và truyền partner_id qua data
        return self.env.ref(
            "vendor_debt_management.action_report_supplier_summary_html"
        ).report_action(
            docs,
            data={
                'partner_id': self.partner_id.id,
                'partner_name': self.partner_id.name
            }
        )
class ReportSupplierSummary(models.AbstractModel):
    _name = 'report.vendor_debt_management.report_sup_summary_html'
    _description = 'Supplier Summary Report'

    def _get_report_values(self, docids, data=None):
        # Lấy partner_id từ data nếu có
        partner_id = data.get('partner_id') if data else False
        if partner_id:
            docs = self.env['supplier.summary'].search([('partner_id', '=', partner_id)])
        else:
            docs = self.env['supplier.summary'].browse(docids)
        
        return {
            'doc_ids': docs.ids,
            'doc_model': 'supplier.summary',
            'docs': docs,
            'partner_name': data.get('partner_name') if data else False,
            'format_amount': lambda amount, currency: format_amount(self.env, amount, currency),
            'user_id': self.env.user,
            'format_date': lambda date: format_date(self.env, date, date_format='dd/MM/yyyy'),
        }
