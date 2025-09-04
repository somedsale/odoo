from odoo import models, fields

class SupplierSettlement(models.Model):
    _name = "supplier.settlement"
    _description = "Supplier Settlement"

    name = fields.Char("Số hồ sơ quyết toán", required=True)
    contract_id = fields.Many2one("supplier.contract", string="Hợp đồng", required=True)
    date = fields.Date("Ngày quyết toán")
    amount = fields.Monetary("Giá trị quyết toán", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)

    invoice_ids = fields.One2many("supplier.invoice", "settlement_id", string="Hóa đơn")
