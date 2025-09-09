from odoo import models, fields,api
class AccountPaymentRequest(models.Model):
    _inherit = "account.payment.request"

    supplier_contract_id = fields.Many2one(
        "supplier.contract", 
        string="Hợp đồng NCC"
    )
    receive_type = fields.Selection([
        ('supplier', 'Nhà cung cấp'),
        ('employee', 'Nhân viên'),
        ('other', 'Khác')
    ], string="Loại chi phí", default='supplier',required=True)
    # supplier_id = fields.Many2one("res.partner", string="Nhà cung cấp", related='supplier_contract_id.partner_id', domain=[("supplier_rank", ">", 0)])
    supplier_id = fields.Many2one(
        "res.partner", 
        string="Nhà cung cấp", 
        domain="[('supplier_rank', '>', 0)]"
    )
    employee_id = fields.Many2one("hr.employee", string="Nhân viên")
    # invoice_id = fields.Many2one("supplier.invoice", string="Hóa đơn")
    invoice_id = fields.Many2one(
    "supplier.invoice", 
    string="Hóa đơn",
    domain="[('contract_id', '=', supplier_contract_id)]"
)
    @api.onchange("project_id")
    def _onchange_project_id(self):
        """Filter NCC theo project"""
        if self.project_id:
            contracts = self.env["supplier.contract"].search([("project_id", "=", self.project_id.id)])
            return {
                "domain": {
                    "supplier_id": [("id", "in", contracts.mapped("partner_id").ids)]
                }
            }
        return {"domain": {"supplier_id": [("id", "=", 0)]}}

    @api.onchange("supplier_id", "project_id")
    def _onchange_supplier_contract(self):
        """Tự động gán hợp đồng khi có project + supplier"""
        if self.project_id and self.supplier_id:
            contract = self.env["supplier.contract"].search([
                ("project_id", "=", self.project_id.id),
                ("partner_id", "=", self.supplier_id.id)
            ], limit=1)
            self.supplier_contract_id = contract