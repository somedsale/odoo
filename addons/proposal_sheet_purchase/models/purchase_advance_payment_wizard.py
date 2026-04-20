from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class PurchaseAdvancePaymentWizard(models.TransientModel):
    _name = "purchase.advance.payment.wizard"
    _description = "Tạo phiếu chi tạm ứng cho PO"

    purchase_id = fields.Many2one("purchase.order", required=True, ondelete="cascade")
    currency_id = fields.Many2one("res.currency", default=lambda s: s.env.company.currency_id.id, readonly=True)
    amount = fields.Monetary(string="Số tiền tạm ứng", currency_field="currency_id", required=True)
    leftover = fields.Monetary(string="Số còn lại của PO", currency_field="currency_id", readonly=True)
    payment_type = fields.Selection([("cash", "Tiền mặt"), ("bank", "Chuyển khoản")], default="bank", required=True)
    journal_id = fields.Many2one("account.journal", domain="[('type','in',['cash','bank'])]")
    note = fields.Char()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        po = self.env["purchase.order"].browse(self.env.context.get("active_id"))
        if po:
            res["purchase_id"] = po.id
            res["currency_id"] = po.currency_id.id
            not_cancel = ("draft", "confirmed", "post", "done")
            requested = sum(po.payment_request_ids.filtered(lambda r: r.state in not_cancel).mapped("total")) or 0.0
            leftover = max((po.amount_total or 0.0) - requested, 0.0)
            res["leftover"] = leftover
            res["amount"] = min(leftover, (po.amount_total or 0.0) * 0.3) if leftover else 0.0
        return res

    def action_confirm(self):
        self.ensure_one()
        po = self.purchase_id
        if not po:
            raise UserError(_("Không tìm thấy Đơn mua hàng."))
        if self.amount <= 0:
            raise ValidationError(_("Số tiền tạm ứng phải > 0."))
        po.create_advance_payment_from_wizard(
            amount=self.amount,
            payment_type=self.payment_type,
            journal_id=self.journal_id.id if self.journal_id else False,
            note=self.note or _("Tạm ứng tạo từ đơn mua hàng %s") % po.name,
        )
        return po.action_view_payment_requests()
