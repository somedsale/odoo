from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup

class AccountPaymentProposalWizard(models.TransientModel):
    _name = "account.payment.proposal.wizard"
    _description = "Trình tạo phiếu thu / chi từ Giải chi"

    payment_proposal_id = fields.Many2one(
        "account.payment.proposal", string="Giải chi", required=True, readonly=True
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )

    # Hai lựa chọn chính
    create_receipt_advance = fields.Boolean(string="Tạo phiếu thu hoàn tạm ứng", default=True)
    amount_receipt_advance = fields.Monetary(
        string="Số tiền thu tạm ứng", currency_field="currency_id"
    )

    create_payment_request = fields.Boolean(string="Tạo phiếu chi thanh toán thực tế", default=True)
    amount_payment_request = fields.Monetary(
        string="Số tiền chi thực tế", currency_field="currency_id"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if active_id:
            proposal = self.env["account.payment.proposal"].browse(active_id)
            res["payment_proposal_id"] = proposal.id
            res["amount_receipt_advance"] = proposal.amount_advance
            res["amount_payment_request"] = proposal.total_amount
        return res

    @api.onchange("payment_proposal_id")
    def _onchange_proposal_id(self):
        if self.payment_proposal_id:
            prop = self.payment_proposal_id
            self.amount_receipt_advance = prop.amount_advance
            self.amount_payment_request = prop.total_amount

    def action_create_documents(self):
        """Tạo phiếu thu và phiếu chi thực tế"""
        self.ensure_one()
        rec = self.payment_proposal_id
        employee = rec.user_id.employee_id
        if not employee:
            raise UserError(_("Người tạo giấy đề nghị chưa gắn với nhân viên nào."))

        Receipt = self.env["account.receipt"]
        Payment = self.env["account.payment.request"]

        # 🔹 1. Phiếu thu hoàn tạm ứng
        if self.create_receipt_advance and self.amount_receipt_advance > 0:
            rec1 = Receipt.create({
                "partner_type": "employee",
                "employee_id": employee.id,
                "date": fields.Date.today(),
                "amount": self.amount_receipt_advance,
                "note": f"Thu hồi tạm ứng từ giấy đề nghị {rec.name}",
                "state": "draft",
                "is_advance_refund": True,
                "payment_proposal_id": rec.id,
            })
            rec.message_post(body=Markup(
                f"💰 Tạo phiếu thu hoàn tạm ứng "
                f"<a href='/web#id={rec1.id}&model=account.receipt&view_type=form'>{rec1.name}</a>."
            ))

        # 🔹 2. Phiếu chi chi phí thực tế
        if self.create_payment_request and self.amount_payment_request > 0:
            pay = Payment.create({
                "date": fields.Date.today(),
                "manual_total": self.amount_payment_request,
                "note": f"Thanh toán chi phí thực tế theo giấy đề nghị {rec.name}",
                "state": "draft",
                "payment_proposal_id": rec.id,
                "employee_id": employee.id,
            })
            rec.message_post(body=Markup(
                f"💸 Tạo phiếu chi thanh toán chi phí thực tế "
                f"<a href='/web#id={pay.id}&model=account.payment.request&view_type=form'>{pay.name}</a>."
            ))
