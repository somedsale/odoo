from odoo import models, fields,api
class AccountPaymentRequest(models.Model):
    _inherit = "account.payment.request"

    supplier_contract_id = fields.Many2one(
        "supplier.contract", 
        string="Hợp đồng NCC",
        domain="[('partner_id', '=', supplier_id)]"
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
    # Loại NCC: trong nước / nước ngoài
    supplier_category = fields.Selection(
        [
            ("domestic", "NCC trong nước"),
            ("foreign", "NCC nước ngoài"),
        ],
        string="Loại NCC",
        default="domestic",
        help="Phân loại nhà cung cấp: trong nước hoặc nước ngoài.",
    )

    # Nhóm NCC trong nước: nhân công / vật tư, dịch vụ
    supplier_domestic_type = fields.Selection(
        [
            ("labor", "NCC Nhân công"),
            ("material_service", "NCC Vật tư, dịch vụ"),
        ],
        string="Nhóm NCC trong nước",
        help="Áp dụng khi Loại NCC là 'NCC trong nước'.",
    )

    # Hạng mục cung cấp
    supply_category = fields.Many2one(
        "supplier.supply.category",
        string="Hạng mục cung cấp",
        help="Hạng mục cung cấp của nhà cung cấp.",
    )

    # Đã đối chiếu công nợ
    reconciled = fields.Boolean(
        string="Đã đối chiếu công nợ",
        help="Đánh dấu phiếu chi này đã được đối chiếu công nợ.",
    )

    # ===== Đồng bộ từ hóa đơn (nếu chọn invoice_id) =====
    @api.onchange("invoice_id")
    def _onchange_invoice_sync_supplier_info(self):
        for rec in self:
            inv = rec.invoice_id
            if not inv:
                continue
            rec.supplier_category = inv.supplier_category or rec.supplier_category
            rec.supplier_domestic_type = (
                inv.supplier_domestic_type or rec.supplier_domestic_type
            )
            rec.supply_category = inv.supply_category or rec.supply_category

    # (tùy chọn) nếu muốn set default khi chọn NCC nhưng chưa chọn hóa đơn
    @api.onchange("supplier_id")
    def _onchange_supplier_set_default_category(self):
        for rec in self:
            if rec.invoice_id:
                # đã đồng bộ theo hóa đơn rồi, khỏi đụng nữa
                continue
            # nếu chưa chọn gì thì mặc định là NCC trong nước
            if not rec.supplier_category:
                rec.supplier_category = "domestic"
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