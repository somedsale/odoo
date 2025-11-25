# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sale_history_ids = fields.One2many(
        "sale.order.line",
        compute="_compute_sale_history",
        string="Lịch sử bán hàng",
        readonly=True,
    )
    sale_history_count = fields.Integer(
        compute="_compute_sale_history",
        string="Số lần bán",
        readonly=True,
    )

    @api.depends("product_id", "order_id.partner_id")
    def _compute_sale_history(self):
        """Tính danh sách lịch sử bán hàng (draft/sent/sale/done) cùng sản phẩm
        và (tuỳ chọn) cùng khách hàng. Lấy 10 dòng gần nhất."""
        SaleLine = self.env["sale.order.line"]
        valid_states = ["draft", "sent", "sale", "done"]
        for line in self:
            if not line.product_id:
                line.sale_history_ids = SaleLine
                line.sale_history_count = 0
                continue
            domain = [
                ("product_id", "=", line.product_id.id),
                ("id", "!=", line.id),
                ("state", "in", valid_states),
            ]
            # Nếu chỉ muốn lịch sử theo cùng khách hàng, giữ điều kiện này
            # if line.order_id.partner_id:
            #     domain.append(("order_partner_id", "=", line.order_id.partner_id.id))

            history = SaleLine.search(domain, order="create_date desc", limit=10)
            line.sale_history_ids = history
            line.sale_history_count = len(history)

    def action_view_sale_history(self):
        """Mở popup lịch sử bán hàng (tree, read-only)."""
        self.ensure_one()
        view = self.env.ref("sale_price_history.view_sale_order_line_history_tree")
        return {
            "name": f"Lịch sử bán hàng: {self.product_id.display_name}",
            "type": "ir.actions.act_window",
            "res_model": "sale.order.line",
            "view_mode": "tree",
            "views": [(view.id, "tree")],
            "target": "new",
            "domain": [("id", "in", self.sale_history_ids.ids)],
            "context": {
                # truyền dòng hiện tại để method áp dụng biết target
                "active_model": "sale.order.line",
                "active_id": self.id,
                "active_ids": [self.id],
            },
        }

    def action_apply_history_price(self):
        """Áp dụng lại giá cũ từ dòng lịch sử (self là dòng lịch sử được click)."""
        self.ensure_one()
        target_line_id = self.env.context.get("active_id") \
                        or self.env.context.get("default_apply_to_line_id")
        if not target_line_id:
            return False

        target_line = self.env["sale.order.line"].browse(target_line_id)
        if not target_line.exists():
            return False

        # Áp dụng giá
        target_line.price_unit = self.price_unit
        target_line.tax_id = self.tax_id
        # Trả về thông báo + đóng popup
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Áp dụng giá thành công",
                "message": f"Đã áp dụng giá {self.price_unit:,.0f} cho {target_line.product_id.display_name}",
                "type": "success",
                "sticky": False,
                # Sau khi hiện thông báo, đóng popup lịch sử
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

