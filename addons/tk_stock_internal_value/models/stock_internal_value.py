# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = "stock.move"

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    # ✅ Đơn giá kho – nhập tay, hoặc lấy từ Đơn mua
    unit_cost = fields.Monetary(
        string="Đơn giá nhập kho",
        currency_field="company_currency_id",
        help="Đơn giá nhập/xuất nội bộ, không liên quan tới kế toán.",
    )

    # ✅ Giá trị kho = Đơn giá * Số lượng
    value_amount = fields.Monetary(
        string="Giá trị nhập kho",
        currency_field="company_currency_id",
        compute="_compute_value_amount",
        store=True,
        help="Thành tiền nội bộ = Đơn giá nhập kho * Số lượng.",
    )

    @api.depends("unit_cost", "quantity", "product_uom_qty")
    def _compute_value_amount(self):
        """
        Odoo 17: 'quantity' là số lượng thực tế (done).
        Nếu chưa có quantity thì fallback product_uom_qty.
        """
        for move in self:
            qty = move.quantity or move.product_uom_qty or 0.0
            move.value_amount = (move.unit_cost or 0.0) * qty

    # 🔹 Chỉ xử lý khi có dòng Đơn mua
    @api.onchange("purchase_line_id")
    def _onchange_purchase_line_set_unit_cost(self):
        """
        Nếu dòng move được tạo từ Đơn mua (purchase.order.line),
        thì ưu tiên lấy giá từ PO.
        """
        for move in self:
            if move.purchase_line_id:
                move.unit_cost = move.purchase_line_id.price_unit or 0.0

    @api.model
    def create(self, vals_list):
        single = isinstance(vals_list, dict)
        if single:
            vals_list = [vals_list]

        moves = super().create(vals_list)

        for move in moves:
            # Nếu chưa có unit_cost mà có purchase_line_id → set theo PO
            if not move.unit_cost and move.purchase_line_id:
                move.unit_cost = move.purchase_line_id.price_unit or 0.0

        return moves[0] if single else moves


class StockPicking(models.Model):
    _inherit = "stock.picking"

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    # ✅ Tổng giá trị nội bộ của cả phiếu kho
    amount_total_value = fields.Monetary(
        string="Tổng giá trị nhập kho",
        currency_field="company_currency_id",
        compute="_compute_amount_total_value",
        store=True,
    )

    @api.depends("move_ids_without_package.value_amount")
    def _compute_amount_total_value(self):
        for picking in self:
            picking.amount_total_value = sum(
                picking.move_ids_without_package.mapped("value_amount")
            )


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    company_currency_id = fields.Many2one(
        "res.currency",
        related="move_id.company_currency_id",
        readonly=True,
    )

    unit_cost = fields.Monetary(
        string="Đơn giá kho",
        currency_field="company_currency_id",
        related="move_id.unit_cost",
        readonly=True,
    )

    value_amount = fields.Monetary(
        string="Giá trị dòng",
        currency_field="company_currency_id",
        compute="_compute_line_value_amount",
        store=True,
    )

    @api.depends("unit_cost", "quantity")
    def _compute_line_value_amount(self):
        for line in self:
            qty = getattr(line, "quantity", 0.0) or line.product_uom_qty or 0.0
            line.value_amount = (line.unit_cost or 0.0) * qty
