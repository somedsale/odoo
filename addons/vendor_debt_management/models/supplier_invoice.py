from odoo import models, fields

class SupplierInvoice(models.Model):
    _name = "supplier.invoice"
    _description = "Supplier Invoice"

    name = fields.Char("Số hóa đơn", required=True)
    contract_id = fields.Many2one("supplier.contract", string="Hợp đồng", required=True)
    settlement_id = fields.Many2one("supplier.settlement", string="Hồ sơ quyết toán")
    date = fields.Date("Ngày hóa đơn", required=True)
    amount = fields.Monetary("Số tiền", required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    partner_id = fields.Many2one(related="contract_id.partner_id", string="Nhà cung cấp", store=True)
    project_id = fields.Many2one(related="contract_id.project_id", string="Dự án", store=True)
