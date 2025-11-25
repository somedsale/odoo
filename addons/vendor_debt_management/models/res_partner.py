from odoo import models, fields, api
class ResPartner(models.Model):
    _inherit = "res.partner"

    contract_ids = fields.One2many("supplier.contract", "partner_id", string="Hợp đồng nhà cung cấp")
    # Loại NCC: trong nước / nước ngoài
    # supplier_category = fields.Selection(
    #     [
    #         ("domestic", "NCC trong nước"),
    #         ("foreign", "NCC nước ngoài"),
    #     ],
    #     default="domestic",
    #     string="Loại nhà cung cấp",
    #     help="Phân loại nhà cung cấp: trong nước hoặc nước ngoài.",
    # )

    # supplier_domestic_type = fields.Selection(
    #     [
    #         ("labor", "NCC Nhân công"),
    #         ("material_service", "NCC Vật tư, dịch vụ"),
    #     ],
    #     string="Nhóm NCC trong nước",
    #     help="Áp dụng khi Loại NCC là 'NCC trong nước'.",
    # )
    # supply_category= fields.Many2one(
    #     "supplier.supply.category",
    #     string="Hạng mục cung cấp",
    #     help="Hạng mục cung cấp của nhà cung cấp.",
    # )
class SupplierSupplyCategory(models.Model):
    _name = "supplier.supply.category"
    _description = "Hạng mục cung cấp NCC"
    _order = "name"

    name = fields.Char("Tên hạng mục")