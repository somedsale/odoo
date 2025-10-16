from odoo import models, fields,api
import logging
_logger = logging.getLogger(__name__)

class AccountPaymentProposalLine(models.Model):
    _name = "account.payment.proposal.line"
    _description = "Chi tiết chứng từ giải chi"
    _order = "sequence asc"

    sequence = fields.Integer(string="STT")
    date = fields.Date(string="Ngày tháng")
    content = fields.Text(string="Nội dung chi")
    amount = fields.Monetary(string="Số tiền", currency_field="currency_id")
    project_id = fields.Many2one(
        "project.project",
        string="Dự án liên quan",
        help="Chọn dự án hoặc công trình liên quan đến khoản chi này"
    )
    note = fields.Char(string="Ghi chú")

    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )

    proposal_id = fields.Many2one("account.payment.proposal", string="Giấy đề nghị", ondelete="cascade")
    attachment_ids = fields.One2many(
        "ir.attachment", "res_id",
        domain=[("res_model", "=", "account.payment.proposal.line")],
        string="Tệp đính kèm"
    )
    @api.model
    def create(self, vals):
        # --- Sinh sequence ---
        if "sequence" not in vals or not vals["sequence"]:
            last = self.search([], order="sequence desc", limit=1)
            vals["sequence"] = (last.sequence or 0) + 1

        record = super().create(vals)
        return record

    
