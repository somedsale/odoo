from odoo import models, fields
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
    supplier_id = fields.Many2one("res.partner", string="Nhà cung cấp", related='supplier_contract_id.partner_id', domain=[("supplier_rank", ">", 0)])
    employee_id = fields.Many2one("hr.employee", string="Nhân viên")