# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = "stock.move"

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    unit_cost = fields.Monetary(
        string="Đơn giá",
        currency_field="company_currency_id",
        help="Đơn giá mặc định lấy từ lần mua gần nhất.",
    )

    tax_ids = fields.Many2many(
        "account.tax",
        string="Thuế",
        help="Thuế mặc định lấy từ lần mua gần nhất hoặc thuế NCC của sản phẩm.",
    )

    value_amount = fields.Monetary(
        string="Giá trị",
        currency_field="company_currency_id",
        compute="_compute_value_amount",
        store=True,
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

    def _get_last_purchase_line(self):
        self.ensure_one()
        PurchaseLine = self.env["purchase.order.line"].sudo()

        if not self.product_id:
            return PurchaseLine.browse()

        partner = self.picking_id.partner_id if self.picking_id else False

        def _line_dt(line):
            return line.order_id.date_approve or line.order_id.date_order or line.create_date or fields.Datetime.now()

        def _best_line(lines):
            if not lines:
                return PurchaseLine.browse()
            return lines.sorted(
                key=lambda l: (_line_dt(l), l.id),
                reverse=True,
            )[:1]

        base_domain = [
            ("product_id", "=", self.product_id.id),
            ("order_id.state", "in", ["purchase", "done"]),
        ]

        # lọc công ty theo PO, không lọc trên line nếu DB custom khác chuẩn
        if self.company_id:
            base_domain.append(("order_id.company_id", "=", self.company_id.id))

        # 1) ưu tiên đúng nhà cung cấp trên phiếu
        if partner:
            lines = PurchaseLine.search(base_domain + [("order_id.partner_id", "=", partner.id)])
            line = _best_line(lines)
            if line:
                return line

        # 2) fallback: lần mua gần nhất của sản phẩm, bất kể NCC
        lines = PurchaseLine.search(base_domain)
        return _best_line(lines)

    def _get_fallback_supplierinfo_price(self):
        self.ensure_one()
        product = self.product_id
        if not product:
            return 0.0

        partner = self.picking_id.partner_id if self.picking_id else False
        sellers = product.seller_ids.sorted(
            key=lambda s: (
                0 if partner and s.partner_id == partner else 1,
                s.sequence,
                s.min_qty or 0.0,
                s.id,
            )
        )

        seller = False
        if partner:
            seller = sellers.filtered(lambda s: s.partner_id == partner)[:1]
        if not seller:
            seller = sellers[:1]

        return seller.price if seller else 0.0

    def _get_default_supplier_price(self):
        self.ensure_one()

        # Ưu tiên PO line gần nhất
        last_po_line = self._get_last_purchase_line()
        if last_po_line:
            return last_po_line.price_unit or 0.0

        # Fallback supplierinfo
        return self._get_fallback_supplierinfo_price()

    def _get_default_supplier_taxes(self):
        self.ensure_one()

        # Ưu tiên thuế của PO line gần nhất
        last_po_line = self._get_last_purchase_line()
        if last_po_line and last_po_line.taxes_id:
            return last_po_line.taxes_id

        # Fallback thuế NCC trên sản phẩm
        if not self.product_id:
            return self.env["account.tax"]

        return self.product_id.supplier_taxes_id.filtered(
            lambda t: not self.company_id or t.company_id == self.company_id
        )

    def _apply_default_purchase_values(self):
        for move in self:
            if not move.product_id:
                continue

            # Nếu move đã gắn purchase_line_id thì ưu tiên tuyệt đối theo dòng đó
            if move.purchase_line_id:
                move.unit_cost = move.purchase_line_id.price_unit or 0.0
                move.tax_ids = move.purchase_line_id.taxes_id
                continue

            move.unit_cost = move._get_default_supplier_price()
            move.tax_ids = move._get_default_supplier_taxes()

    @api.depends("unit_cost", "quantity", "product_uom_qty", "tax_ids", "product_id", "company_id")
    def _compute_price_total(self):
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

    @api.depends("unit_cost", "quantity", "product_uom_qty", "tax_ids")
    def _compute_value_amount(self):
        for move in self:
            qty = move.quantity or move.product_uom_qty or 0.0
            move.value_amount = (move.unit_cost or 0.0) * qty

    @api.onchange("product_id", "picking_id", "company_id")
    def _onchange_product_id_set_purchase_defaults(self):
        for move in self:
            if not move.product_id:
                move.unit_cost = 0.0
                move.tax_ids = [(5, 0, 0)]
                continue
            move._apply_default_purchase_values()

    @api.onchange("purchase_line_id")
    def _onchange_purchase_line_set_unit_cost(self):
        for move in self:
            if move.purchase_line_id:
                move.unit_cost = move.purchase_line_id.price_unit or 0.0
                move.tax_ids = move.purchase_line_id.taxes_id
            elif move.product_id:
                move._apply_default_purchase_values()

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)

        for move in moves:
            if move.purchase_line_id:
                move.unit_cost = move.purchase_line_id.price_unit or 0.0
                move.tax_ids = move.purchase_line_id.taxes_id
                continue

            vals = {}
            if not move.unit_cost and move.product_id:
                vals["unit_cost"] = move._get_default_supplier_price()
            if not move.tax_ids and move.product_id:
                vals["tax_ids"] = [(6, 0, move._get_default_supplier_taxes().ids)]
            if vals:
                move.write(vals)

        return moves


class StockPicking(models.Model):
    _inherit = "stock.picking"

    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    amount_total_value = fields.Monetary(
        string="Tổng giá trị",
        currency_field="company_currency_id",
        compute="_compute_amount_total_value",
        store=True,
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

    @api.depends("move_ids_without_package.price_total")
    def _compute_amount_total_value(self):
        for picking in self:
            picking.amount_total_value = sum(picking.move_ids_without_package.mapped("price_total"))

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

    @api.depends("move_id.unit_cost", "quantity")
    def _compute_line_value_amount(self):
        for line in self:
            qty = line.quantity or 0.0
            line.value_amount = (line.move_id.unit_cost or 0.0) * qty

    @api.depends(
        "move_id.unit_cost",
        "quantity",
        "move_id.tax_ids",
        "move_id.product_id",
        "move_id.picking_id.partner_id",
        "company_id",
    )
    def _compute_line_prices(self):
        for line in self:
            qty = line.quantity or 0.0
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