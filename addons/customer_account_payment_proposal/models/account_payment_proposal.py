from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentProposal(models.Model):
    _name = "account.payment.proposal"
    _description = "Giấy đề nghị giải chi"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Số chứng từ", readonly=True, copy=False, default="/")
    date_request = fields.Date(string="Ngày đề nghị", default=fields.Date.context_today)
    partner_name = fields.Char(string="Họ và tên")
    department = fields.Char(string="Đơn vị công tác")
    document_ref = fields.Char(string="Chứng từ thanh toán")
    amount_advance = fields.Monetary(string="Số tiền tạm ứng", currency_field="currency_id")
    amount_refund = fields.Monetary(string="Số tiền hoàn ứng", currency_field="currency_id")
    amount_remain = fields.Monetary(string="Số tiền còn lại thanh toán", currency_field="currency_id")
    amount_in_words = fields.Char(string="Số tiền còn lại bằng chữ")
    purpose = fields.Text(string="Nội dung chi")

    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )

    line_ids = fields.One2many(
        "account.payment.proposal.line",
        "proposal_id",
        string="Chi tiết chứng từ"
    )

    note = fields.Text(string="Ghi chú thêm")

    state = fields.Selection([
        ("draft", "Nháp"),
        ("submitted", "Chờ duyệt"),
        ("approved", "Đã duyệt"),
        ("paid", "Đã chi"),
    ], default="draft", string="Trạng thái")

    @api.model
    def create(self, vals):
        if vals.get("name", "/") == "/":
            vals["name"] = self.env["ir.sequence"].next_by_code("account.payment.proposal")
        return super().create(vals)
    def action_submit(self):
            """Đưa phiếu từ Nháp sang Chờ duyệt"""
            for rec in self:
                if not rec.partner_name or not rec.amount_remain:
                    raise UserError(_("Vui lòng nhập đầy đủ họ tên và số tiền cần thanh toán."))
                rec.state = "submitted"
                rec.message_post(body=_("Đã gửi duyệt giải chi."))

    def action_approve(self):
            """Duyệt phiếu chi"""
            for rec in self:
                if rec.state not in ("submitted", "draft"):
                    raise UserError(_("Chỉ có thể duyệt phiếu ở trạng thái 'Nháp' hoặc 'Chờ duyệt'."))
                rec.state = "approved"
                rec.message_post(body=_("Phiếu giải chi đã được duyệt."))

    def action_paid(self):
            """Đánh dấu đã chi tiền"""
            for rec in self:
                if rec.state != "approved":
                    raise UserError(_("Chỉ đánh dấu 'Đã chi' sau khi phiếu được duyệt."))
                rec.state = "paid"
                rec.message_post(body=_("Đã chi tiền cho đề nghị này."))