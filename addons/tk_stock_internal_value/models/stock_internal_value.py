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
        string="Đơn giá",
        currency_field="company_currency_id",
        help="Đơn giá nhập/xuất nội bộ, không liên quan tới kế toán.",
    )
    tax_ids = fields.Many2many(
        "account.tax",
        string="Thuế",
        help="Thuế áp dụng cho giá trị kho của dòng này.",
    )
    # ✅ Giá trị kho = Đơn giá * Số lượng
    value_amount = fields.Monetary(
        string="Giá trị",
        currency_field="company_currency_id",
        compute="_compute_value_amount",
        store=True,
        help="Thành tiền nội bộ = Đơn giá nhập kho * Số lượng.",
    )
    price_subtotal = fields.Monetary(
        string="Thành tiền (chưa thuế)",
        currency_field="company_currency_id",
        compute="_compute_price_total",
        store=True,
    )
    price_tax = fields.Monetary(
        string="Tiền thuế",
        currency_field="company_currency_id",
        compute="_compute_price_total",
        store=True,
    )
    price_total = fields.Monetary(
        string="Thành tiền (có thuế)",
        currency_field="company_currency_id",
        compute="_compute_price_total",
        store=True,
    )
    @api.depends("unit_cost", "quantity", "product_uom_qty", "tax_ids", "product_id", "company_id")
    def _compute_price_total(self):
        """
        Tính tổng tiền theo thuế giống sale/purchase:
        - price_subtotal: total_excluded
        - price_total: total_included
        """
        for move in self:
            qty = move.quantity or move.product_uom_qty or 0.0
            price_unit = move.unit_cost or 0.0

            partner = move.picking_id.partner_id if move.picking_id and move.picking_id.partner_id else False
            currency = move.company_currency_id

            if move.tax_ids:
                res = move.tax_ids.compute_all(
                    price_unit,
                    currency=currency,
                    quantity=qty,
                    product=move.product_id,
                    partner=partner,
                )
                total_excl = res.get("total_excluded", 0.0)
                total_incl = res.get("total_included", 0.0)
            else:
                total_excl = price_unit * qty
                total_incl = total_excl

            move.price_subtotal = total_excl
            move.price_total = total_incl
            move.price_tax = total_incl - total_excl
    @api.depends("unit_cost", "quantity", "product_uom_qty","tax_ids")
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
                move.tax_ids = move.purchase_line_id.taxes_id

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
                move.tax_ids = move.purchase_line_id.taxes_id


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
        string="Tổng giá trị",
        currency_field="company_currency_id",
        compute="_compute_amount_total_value",
        store=True,
    )

    @api.depends("move_ids_without_package.price_total")
    def _compute_amount_total_value(self):
        for picking in self:
            picking.amount_total_value = sum(
                picking.move_ids_without_package.mapped("price_total")
            )
    amount_untaxed = fields.Monetary(
        string="Tổng trước thuế",
        currency_field="company_currency_id",
        compute="_compute_amounts",
        store=True,
    )
    amount_tax = fields.Monetary(
        string="Tổng thuế",
        currency_field="company_currency_id",
        compute="_compute_amounts",
        store=True,
    )
    amount_total = fields.Monetary(
        string="Tổng sau thuế",
        currency_field="company_currency_id",
        compute="_compute_amounts",
        store=True,
    )

    @api.depends(
        "move_ids_without_package.price_subtotal",
        "move_ids_without_package.price_tax",
        "move_ids_without_package.price_total",
    )
    def _compute_amounts(self):
        for picking in self:
            moves = picking.move_ids_without_package
            picking.amount_untaxed = sum(moves.mapped("price_subtotal"))
            picking.amount_tax = sum(moves.mapped("price_tax"))
            picking.amount_total = sum(moves.mapped("price_total"))

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
    tax_ids = fields.Many2many(
        "account.tax",
        related="move_id.tax_ids",
        readonly=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="move_id.company_currency_id",
        readonly=True,
    )

    price_subtotal = fields.Monetary(
        string="Thành tiền (chưa thuế)",
        currency_field="company_currency_id",
        compute="_compute_line_prices",
        store=True,
    )
    price_tax = fields.Monetary(
        string="Thuế",
        currency_field="company_currency_id",
        compute="_compute_line_prices",
        store=True,
    )
    price_total = fields.Monetary(
        string="Thành tiền (có thuế)",
        currency_field="company_currency_id",
        compute="_compute_line_prices",
        store=True,
    )

    @api.depends(
        "move_id.unit_cost",
        "quantity",                 # ✅ Odoo 17
        "move_id.tax_ids",
        "move_id.product_id",
        "move_id.picking_id.partner_id",
        "company_id",
    )
    def _compute_line_prices(self):
        for line in self:
            qty = line.quantity or 0.0               # ✅ done qty của move line
            price_unit = line.move_id.unit_cost or 0.0
            taxes = line.move_id.tax_ids
            currency = line.move_id.company_currency_id
            product = line.move_id.product_id
            partner = line.move_id.picking_id.partner_id if line.move_id.picking_id else False

            if taxes:
                res = taxes.compute_all(
                    price_unit,
                    currency=currency,
                    quantity=qty,
                    product=product,
                    partner=partner,
                )
                total_excl = res.get("total_excluded", 0.0)
                total_incl = res.get("total_included", 0.0)
            else:
                total_excl = price_unit * qty
                total_incl = total_excl

            line.price_subtotal = total_excl
            line.price_total = total_incl
            line.price_tax = total_incl - total_excl