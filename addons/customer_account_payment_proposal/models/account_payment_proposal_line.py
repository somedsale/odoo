from odoo import models, fields


class AccountPaymentProposalLine(models.Model):
    _name = "account.payment.proposal.line"
    _description = "Chi tiết chứng từ giải chi"
    _order = "sequence asc"

    sequence = fields.Integer(string="STT")
    date = fields.Date(string="Ngày tháng")
    content = fields.Text(string="Nội dung")
    amount = fields.Monetary(string="Số tiền", currency_field="currency_id")
    project = fields.Char(string="Dự án")
    note = fields.Char(string="Ghi chú")

    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )

    proposal_id = fields.Many2one("account.payment.proposal", string="Giấy đề nghị")
