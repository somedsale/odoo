from odoo import _, api, fields, models


class AccountingPaymentRequest(models.Model):
    _inherit = "account.payment.request"

    purchase_id = fields.Many2one(
        "purchase.order",
        string="Đơn mua hàng",
        index=True,
        ondelete="set null",
    )
    task_id = fields.Many2one("project.task", string="Nhiệm vụ", index=True)
    payment_kind = fields.Selection(
        [
            ("advance", "Tạm ứng"),
            ("full", "Thanh toán toàn bộ"),
        ],
        string="Kiểu thanh toán",
        default="advance",
        required=True,
    )
    purchase_order_count = fields.Integer(
        string="Số đơn hàng",
        compute="_compute_purchase_order_count",
    )

    @api.depends("purchase_id")
    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = 1 if rec.purchase_id else 0

    def action_view_purchase_order(self):
        self.ensure_one()
        if not self.purchase_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Đơn mua hàng"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": self.purchase_id.id,
            "target": "current",
        }
