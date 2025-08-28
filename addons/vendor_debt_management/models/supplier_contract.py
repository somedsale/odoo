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
    due_date = fields.Date("Ngày đến hạn")
    create_date = fields.Datetime("Ngày tạo", default=fields.Datetime.now)
    total_invoices = fields.Monetary("Tổng giá trị hóa đơn", compute="_compute_total_invoices", store=True, currency_field="currency_id")
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
    @api.depends("invoice_ids.amount")
    def _compute_total_invoices(self):
        for record in self:
            record.total_invoices = sum(record.invoice_ids.mapped("amount"))
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
class ResPartner(models.Model):
    _inherit = "res.partner"

    contract_ids = fields.One2many("supplier.contract", "partner_id", string="Hợp đồng nhà cung cấp")