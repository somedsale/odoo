from odoo import models, fields, api

class SupplierContract(models.Model):
    _name = "supplier.contract"
    _description = "Supplier Contract"

    name = fields.Char("Số Hợp đồng")
    partner_id = fields.Many2one("res.partner", string="Nhà cung cấp", required=True, domain=[("supplier_rank", ">", 0)])
    project_id = fields.Many2one("project.project", string="Dự án", required=True)
    interpretation = fields.Char("Diễn giải")
    contract_date = fields.Date("Ngày Hợp đồng")
    amount = fields.Monetary("Giá trị Hợp đồng", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    due_date = fields.Date("Ngày đến hạn",compute="_compute_due_date", store=True)
    create_date = fields.Datetime("Ngày tạo", default=fields.Datetime.now)
    total_invoices = fields.Monetary("Tổng giá trị hóa đơn", compute="_compute_total_invoices", store=True, currency_field="currency_id")
    total_settlements = fields.Monetary("Tổng giá trị hồ sơ quyết toán", compute="_compute_total_settlements", store=True, currency_field="currency_id")
    paid_amount = fields.Monetary("Tổng giá trị đã thanh toán", compute="_compute_paid_amount", store=True, currency_field="currency_id")
    residual_amount = fields.Monetary("Còn nợ", compute="_compute_residual", store=True, currency_field="currency_id")
    advance_amount = fields.Monetary("Số tiền đã tạm ứng/ chưa hóa đơn", compute="_compute_advance_amount", store=True, currency_field="currency_id")
    account_payment_request_ids = fields.One2many(
        "account.payment.request", 
        "supplier_contract_id", 
        string="Phiếu chi"
    )
    settlement_ids = fields.One2many("supplier.settlement", "contract_id", string="Hồ sơ quyết toán")
    invoice_ids = fields.One2many("supplier.invoice", "contract_id", string="Hóa đơn")
    @api.depends("invoice_ids.due_date")
    def _compute_due_date(self):
        for record in self:
            dates = [d for d in record.invoice_ids.mapped("due_date") if d]
            if dates:
                record.due_date = min(dates)  # hoặc max(dates) nếu muốn ngày muộn nhất
            else:
                record.due_date = False
    @api.depends("invoice_ids.amount")
    def _compute_total_invoices(self):
        for record in self:
            record.total_invoices = sum(record.invoice_ids.mapped("amount"))
    @api.depends("settlement_ids.amount")
    def _compute_total_settlements(self):
        for record in self:
            record.total_settlements = sum(record.settlement_ids.mapped("amount"))
    @api.depends("account_payment_request_ids.total", "account_payment_request_ids.state")
    def _compute_paid_amount(self):
        for record in self:
            record.paid_amount = sum(request.total for request in record.account_payment_request_ids if request.state == 'done')
    @api.depends("amount", "paid_amount", "account_payment_request_ids.total", "account_payment_request_ids.state", "invoice_ids.amount")
    def _compute_residual(self):
        for record in self:
            residual_amount = record.total_invoices - record.paid_amount
            if residual_amount < 0:
                residual_amount = 0
            record.residual_amount = residual_amount
    @api.depends("total_invoices", "paid_amount")
    def _compute_advance_amount(self):
        for record in self:
            advance_amount = record.paid_amount - record.total_invoices
            if advance_amount < 0:
                advance_amount = 0
            record.advance_amount = advance_amount
    @api.onchange("residual_amount")
    def _onchange_residual_amount(self):
        for record in self:
            if record.residual_amount == 0:
                record.due_date = False
    def action_open_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Hóa đơn NCC",
            "res_model": "supplier.invoice",
            "view_mode": "tree,form",
            "target": "current",
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_project_id": self.project_id.id,
            },
        }

    # Phiếu chi thuộc HĐ này (hoặc hóa đơn của HĐ này)
    def action_open_payment_requests(self):
        self.ensure_one()
        # nếu model account.payment.request có field invoice_id + supplier_contract_id như bạn dùng
        return {
            "type": "ir.actions.act_window",
            "name": "Phiếu chi",
            "res_model": "account.payment.request",
            "view_mode": "tree,form",
            "target": "current",
            "domain": ["|", ("supplier_contract_id", "=", self.id),
                             ("invoice_id.contract_id", "=", self.id)],
            "context": {
                "default_supplier_contract_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_project_id": self.project_id.id,
            },
        }

    # Hồ sơ quyết toán thuộc HĐ này
    def action_open_settlements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Hồ sơ quyết toán",
            "res_model": "supplier.settlement",
            "view_mode": "tree,form",
            "target": "current",
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
            },
        }

    # “Còn nợ”: mở danh sách hóa đơn chưa thanh toán (tùy bạn muốn mở invoices hay payment requests)
    def action_open_residual(self):
        self.ensure_one()
        # ví dụ mở hóa đơn của HĐ này (bạn có thể thêm điều kiện due_date/quá hạn tùy ý)
        return {
            "type": "ir.actions.act_window",
            "name": "Công nợ chưa thanh toán",
            "res_model": "supplier.invoice",
            "view_mode": "tree,form",
            "target": "current",
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
                "search_default_contract_id": 1,
            },
        }
class ResPartner(models.Model):
    _inherit = "res.partner"

    contract_ids = fields.One2many("supplier.contract", "partner_id", string="Hợp đồng nhà cung cấp")