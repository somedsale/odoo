from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup

class AccountPaymentProposalWizard(models.TransientModel):
    _name = "account.payment.proposal.wizard"
    _description = "Trình tạo phiếu thu / chi từ Giải chi"

    payment_proposal_id = fields.Many2one("account.payment.proposal", string="Giải chi", required=True, readonly=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)

    # 3 lựa chọn
    create_receipt_advance = fields.Boolean(string="Tạo phiếu thu hoàn tạm ứng",default=False)
    amount_receipt_advance = fields.Monetary(string="Số tiền thu tạm ứng", currency_field="currency_id")

    create_receipt_refund = fields.Boolean(string="Tạo phiếu thu hoàn ứng thêm",default=False)
    amount_receipt_refund = fields.Monetary(string="Số tiền thu hoàn ứng thêm", currency_field="currency_id")

    create_payment_request = fields.Boolean(string="Tạo phiếu chi thanh toán",default=False)
    amount_payment_request = fields.Monetary(string="Số tiền chi thanh toán", currency_field="currency_id")
    show_receipt_advance = fields.Boolean(default=True)
    show_receipt_refund = fields.Boolean(default=True)
    show_payment_request = fields.Boolean(default=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if active_id:
            proposal = self.env["account.payment.proposal"].browse(active_id)
            res["payment_proposal_id"] = proposal.id
            res["amount_receipt_advance"] = proposal.amount_advance
            res["amount_receipt_refund"] = proposal.amount_refund
            res["amount_payment_request"] = proposal.amount_remain

            # Ẩn nhóm không có tiền
            res["show_receipt_advance"] = proposal.amount_advance > 0
            res["show_receipt_refund"] = proposal.amount_refund > 0
            res["show_payment_request"] = proposal.amount_remain > 0

        return res

    @api.onchange('payment_proposal_id')
    def _onchange_proposal_id(self):
        if self.payment_proposal_id:
            prop = self.payment_proposal_id
            self.amount_receipt_advance = prop.amount_advance
            self.amount_receipt_refund = prop.amount_refund
            self.amount_payment_request = prop.amount_remain

    def action_create_documents(self):
        """Tạo phiếu thu / chi tương ứng"""
        self.ensure_one()
        rec = self.payment_proposal_id
        partner_id = rec.user_id.partner_id.id if rec.user_id.partner_id else False

        if not (self.create_receipt_advance or self.create_receipt_refund or self.create_payment_request):
            raise UserError(_("Vui lòng chọn ít nhất một loại chứng từ để tạo."))

        Receipt = self.env["account.receipt"]
        Payment = self.env["account.payment.request"]

        # 🔹 Phiếu thu hoàn tạm ứng
        # 🔹 Phiếu thu hoàn tạm ứng
        if self.create_receipt_advance and self.amount_receipt_advance > 0:
            employee = rec.user_id.employee_id
            if not employee:
                raise UserError(_("Người tạo giấy đề nghị chưa gắn với nhân viên nào."))

            rec1 = Receipt.create({
                "partner_type": "employee",  # ✅ loại phiếu thu là nhân viên
                "employee_id": employee.id,
                "date": fields.Date.today(),
                "amount": self.amount_receipt_advance,
                "note": f"Thu hồi tạm ứng từ giấy đề nghị {rec.name}",
                "state": "draft",
                "payment_proposal_id": rec.id,
            })
            rec.message_post(body=Markup(
                f"💰 Tạo phiếu thu hoàn tạm ứng "
                f"<a href='/web#id={rec1.id}&model=account.receipt&view_type=form'>{rec1.name}</a>."
            ))

        # 🔹 Phiếu thu hoàn ứng thêm
        if self.create_receipt_refund and self.amount_receipt_refund > 0:
            employee = rec.user_id.employee_id
            if not employee:
                raise UserError(_("Người tạo giấy đề nghị chưa gắn với nhân viên nào."))

            rec2 = Receipt.create({
                "partner_type": "employee",  # ✅ loại phiếu thu là nhân viên
                "employee_id": employee.id,
                "date": fields.Date.today(),
                "amount": self.amount_receipt_refund,
                "note": f"Hoàn ứng giấy đề nghị {rec.name}",
                "state": "draft",
                "payment_proposal_id": rec.id,
            })
            rec.message_post(body=Markup(
                f"💵 Tạo phiếu thu hoàn ứng thêm "
                f"<a href='/web#id={rec2.id}&model=account.receipt&view_type=form'>{rec2.name}</a>."
            ))

        # 🔹 Phiếu chi thanh toán
        if self.create_payment_request and self.amount_payment_request > 0:
            # Tính tổng các phiếu chi đã có
            existing_total = sum(Payment.search([
                ("payment_proposal_id", "=", rec.id),
                ("state", "!=", "cancel")
            ]).mapped("total"))

            new_total = existing_total + self.amount_payment_request

            if new_total > rec.amount_remain + 1e-6:  # cộng chút dung sai số thực
                raise UserError(_(
                    f"Tổng số tiền chi ({new_total:,.0f}) vượt quá số tiền còn lại phải thanh toán ({rec.amount_remain:,.0f})."
                ))

            # Nếu hợp lệ, tạo phiếu chi mới
            pay = Payment.create({
                "date": fields.Date.today(),
                "total": self.amount_payment_request,
                "note": f"Thanh toán {self.amount_payment_request:,.0f} cho {rec.name}",
                "state": "draft",
                "payment_proposal_id": rec.id,
            })
            rec.message_post(body=Markup(
                f"💸 Tạo phiếu chi thanh toán "
                f"<a href='/web#id={pay.id}&model=account.payment.request&view_type=form'>{pay.name}</a>."
            ))

        # rec.state = "paid"
