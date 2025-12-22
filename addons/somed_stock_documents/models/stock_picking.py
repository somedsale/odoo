# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    lsx_count = fields.Integer(string="LSX", compute="_compute_lsx_count")
    contract_id = fields.Many2one(
        "contract.management",
        string="Hợp đồng",
        domain=[("stage", "in", ["executing", "completed"])],
    )
    purchase_order_count = fields.Integer(string="PO", compute="_compute_purchase_order_count")
    delivery_reason = fields.Text(string="Lý do xuất kho")
    def _get_related_purchase_orders(self):
        """Lấy PO từ purchase_line_id trên stock.move (chuẩn nhất).
        Fallback: nếu không có, thử match theo origin = tên PO."""
        self.ensure_one()
        moves = self.move_ids_without_package or self.move_ids
        pos = moves.mapped("purchase_line_id.order_id")

        # fallback theo origin (nếu bạn tự tạo picking không đi qua purchase flow)
        if not pos and self.origin:
            pos = self.env["purchase.order"].search([("name", "=", self.origin)])
        return pos

    def _compute_purchase_order_count(self):
        for picking in self:
            picking.purchase_order_count = len(picking._get_related_purchase_orders())

    def action_view_purchase_orders(self):
        self.ensure_one()
        pos = self._get_related_purchase_orders()

        action = {
            "type": "ir.actions.act_window",
            "name": _("Phiếu mua hàng"),
            "res_model": "purchase.order",
            "view_mode": "tree,form",
            "domain": [("id", "in", pos.ids)],
            "context": dict(self.env.context),
        }
        if len(pos) == 1:
            action.update({"view_mode": "form", "res_id": pos.id})
        return action
    @api.depends()
    def _compute_lsx_count(self):
        Order = self.env["multi.mrp.order"].sudo()
        for picking in self:
            picking.lsx_count = Order.search_count([
                "|",
                ("picking_raw_id", "=", picking.id),
                ("picking_finished_id", "=", picking.id),
            ])

    def action_view_lsx(self):
        self.ensure_one()
        Order = self.env["multi.mrp.order"].sudo()
        orders = Order.search([
            "|",
            ("picking_raw_id", "=", self.id),
            ("picking_finished_id", "=", self.id),
        ])

        action = {
            "type": "ir.actions.act_window",
            "name": _("Lệnh sản xuất"),
            "res_model": "multi.mrp.order",
            "view_mode": "tree,form",
            "domain": [("id", "in", orders.ids)],
            "context": dict(self.env.context),
        }
        if len(orders) == 1:
            action.update({
                "view_mode": "form",
                "res_id": orders.id,
            })
        return action