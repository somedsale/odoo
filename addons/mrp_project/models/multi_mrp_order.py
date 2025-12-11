# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MultiMrpOrder(models.Model):
    _name = "multi.mrp.order"
    _description = "Lệnh sản xuất nhiều thành phẩm"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    # ===== Thông tin chung =====
    name = fields.Char(
        string="Số lệnh",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )
    date = fields.Date(
        string="Ngày lệnh",
        default=fields.Date.context_today,
        tracking=True,
    )
    origin = fields.Char(
        string="Diễn giải / Tham chiếu",
        tracking=True,
    )
    sale_id = fields.Many2one(
        "sale.order",
        string="Đơn bán",
        tracking=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Dự án",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("confirmed", "Đã xác nhận"),
            ("done", "Hoàn tất"),
            ("cancel", "Hủy"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
    )

    line_ids = fields.One2many(
        "multi.mrp.order.line",
        "order_id",
        string="Thành phẩm",
    )
    production_count = fields.Integer(
        string="Số lệnh SX",
        compute="_compute_production_count",
    )
    note = fields.Text(string="Ghi chú")

    # ===== Cấu hình kho + phiếu xuất / nhập =====
    # PXK: dùng loại dịch chuyển nội bộ (internal)
    picking_type_out_id = fields.Many2one(
        "stock.picking.type",
        string="Loại dịch chuyển PXK (internal)",
        domain=[("code", "=", "internal")],
        default=lambda self: self._default_picking_type_out_id(),
        help="Loại dịch chuyển dùng để tạo phiếu xuất NVL (nội bộ).",
    )
    # PNK: dùng loại dịch chuyển nhập (incoming) để không bị check tồn ở nguồn
    picking_type_in_id = fields.Many2one(
        "stock.picking.type",
        string="Loại dịch chuyển PNK (incoming)",
        domain=[("code", "=", "incoming")],
        default=lambda self: self._default_picking_type_in_id(),
        help="Loại dịch chuyển dùng để tạo phiếu nhập thành phẩm (nhập kho).",
    )

    location_src_id = fields.Many2one(
        "stock.location",
        string="Kho NVL",
        domain=[("usage", "=", "internal")],
        help="Kho xuất nguyên vật liệu (nguồn của PXK).",
    )
    location_production_id = fields.Many2one(
        "stock.location",
        string="Kho sản xuất",
        domain=[("usage", "in", ["internal", "production"])],
        help="Kho/địa điểm sản xuất (đích PXK, chỉ để theo dõi).",
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Kho thành phẩm",
        domain=[("usage", "=", "internal")],
        help="Kho nhập thành phẩm (đích PNK).",
    )

    picking_raw_id = fields.Many2one(
        "stock.picking",
        string="Phiếu xuất NVL",
        readonly=True,
    )
    picking_finished_id = fields.Many2one(
        "stock.picking",
        string="Phiếu nhập TP",
        readonly=True,
    )

    @api.model
    def _default_picking_type_out_id(self):
        company = self.env.company
        picking_type = (
            self.env["stock.picking.type"]
            .search(
                [
                    ("code", "=", "internal"),
                    ("company_id", "in", [company.id, False]),
                ],
                limit=1,
            )
        )
        return picking_type.id

    @api.model
    def _default_picking_type_in_id(self):
        company = self.env.company
        picking_type = (
            self.env["stock.picking.type"]
            .search(
                [
                    ("code", "=", "incoming"),
                    ("company_id", "in", [company.id, False]),
                ],
                limit=1,
            )
        )
        return picking_type.id

    @api.onchange("company_id")
    def _onchange_company_id(self):
        for order in self:
            if order.company_id:
                if not order.picking_type_out_id:
                    order.picking_type_out_id = order._default_picking_type_out_id()
                if not order.picking_type_in_id:
                    order.picking_type_in_id = order._default_picking_type_in_id()

    _sql_constraints = [
        (
            "name_company_uniq",
            "unique(name, company_id)",
            "Số lệnh phải là duy nhất trong mỗi công ty.",
        )
    ]

    def _compute_production_count(self):
        for order in self:
            order.production_count = len(order.line_ids.mapped("mrp_production_id"))

    @api.model
    def create(self, vals):
        if vals.get("name", "New") in ("New", "/", False):
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("multi.mrp.order") or "/"
            )
        return super().create(vals)

    # ======= Actions / Buttons =======

    def action_confirm(self):
        for order in self:
            if not order.line_ids:
                raise UserError(
                    _("Vui lòng thêm ít nhất 1 dòng thành phẩm trước khi xác nhận.")
                )
        self.write({"state": "confirmed"})
        return True

    def action_done(self):
        for order in self:
            # Nếu còn MO con chưa done/cancel thì không cho complete
            not_done = order.line_ids.mapped("mrp_production_id").filtered(
                lambda mo: mo.state not in ("done", "cancel")
            )
            if not_done:
                raise UserError(
                    _(
                        "Vẫn còn lệnh sản xuất chi tiết chưa hoàn tất hoặc bị hủy.\n"
                        "Vui lòng kiểm tra lại."
                    )
                )
        self.write({"state": "done"})
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    def action_reset_to_draft(self):
        self.write({"state": "draft"})
        return True

    def action_generate_mo(self):
        """
        Tạo mrp.production cho từng dòng thành phẩm chưa có MO.
        MO lúc này chủ yếu là 'kế hoạch' (planning).
        """
        MrpProduction = self.env["mrp.production"]
        Bom = self.env["mrp.bom"]

        for order in self:
            if not order.line_ids:
                raise UserError(
                    _("Không có dòng thành phẩm nào để tạo lệnh sản xuất.")
                )

            for line in order.line_ids:
                if line.mrp_production_id:
                    continue

                if not line.product_id or not line.product_qty:
                    raise UserError(
                        _("Dòng thành phẩm '%s' thiếu sản phẩm hoặc số lượng.")
                        % (line.display_name,)
                    )

                bom = line.bom_id
                if not bom and line.product_tmpl_id:
                    bom = Bom.search(
                        [
                            ("product_tmpl_id", "=", line.product_tmpl_id.id),
                            ("company_id", "in", [order.company_id.id, False]),
                            ("type", "=", "normal"),
                        ],
                        limit=1,
                    )

                mo_vals = {
                    "product_id": line.product_id.id,
                    "product_uom_id": line.product_uom_id.id,
                    "product_qty": line.product_qty,
                    "company_id": order.company_id.id,
                    "origin": order.name,
                    "bom_id": bom.id if bom else False,
                }

                if "project_id" in MrpProduction._fields and order.project_id:
                    mo_vals["project_id"] = order.project_id.id
                if "sale_id" in MrpProduction._fields and order.sale_id:
                    mo_vals["sale_id"] = order.sale_id.id

                mo = MrpProduction.create(mo_vals)
                line.mrp_production_id = mo.id

        return True

    def action_generate_pickings(self):
        """
        CÁCH B (MISA style):

        - Phiếu xuất NVL (PXK): từ Kho NVL (internal) -> Kho sản xuất (internal)
          dùng picking_type_out_id (code = 'internal').

        - Phiếu nhập TP (PNK): từ location nguồn ảo (Vendors / default src của picking_type_in_id)
          -> Kho thành phẩm (internal), dùng picking_type_in_id (code = 'incoming').

        => PNK sẽ KHÔNG bị check "không đủ hàng ở kho nguồn" nữa, vì nguồn là kho Supplier.
        """
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        Bom = self.env["mrp.bom"]

        for order in self:
            if order.picking_raw_id or order.picking_finished_id:
                raise UserError(
                    _("Lệnh %s đã có phiếu xuất/nhập kho, không thể tạo thêm.")
                    % order.name
                )

            if not order.picking_type_out_id:
                raise UserError(
                    _("Vui lòng cấu hình 'Loại dịch chuyển PXK (internal)' trước.")
                )
            if not order.picking_type_in_id:
                raise UserError(
                    _("Vui lòng cấu hình 'Loại dịch chuyển PNK (incoming)' trước.")
                )
            if not order.location_src_id:
                raise UserError(_("Vui lòng cấu hình 'Kho NVL' trước."))
            if not order.location_dest_id:
                raise UserError(_("Vui lòng cấu hình 'Kho thành phẩm' trước."))

            # ===== 1. Gom NVL từ tất cả BoM của các dòng thành phẩm =====
            components = {}  # key: (product_id, uom_id) -> qty
            missing_bom_products = []

            for line in order.line_ids:
                if not line.product_id or not line.product_qty:
                    continue

                # Ưu tiên BoM đã chọn trên dòng, nếu không có thì tự tìm
                bom = line.bom_id
                if not bom and line.product_tmpl_id:
                    bom = Bom.search(
                        [
                            ("product_tmpl_id", "=", line.product_tmpl_id.id),
                            ("company_id", "in", [order.company_id.id, False]),
                            ("type", "=", "normal"),
                        ],
                        limit=1,
                    )

                if not bom:
                    missing_bom_products.append(
                        line.product_id.display_name or line.product_id.name
                    )
                    continue

                factor = line.product_qty / (bom.product_qty or 1.0)

                for bom_line in bom.bom_line_ids:
                    if getattr(bom_line, "display_type", False):
                        continue

                    prod = bom_line.product_id
                    if not prod:
                        continue

                    line_qty = (bom_line.product_qty or 0.0) * factor
                    if line_qty <= 0:
                        continue

                    uom = getattr(bom_line, "product_uom_id", False) or prod.uom_id
                    key = (prod.id, uom.id)
                    components[key] = components.get(key, 0.0) + line_qty

            if missing_bom_products:
                raise UserError(
                    _("Không tìm thấy BoM cho các thành phẩm:\n%s")
                    % ("\n".join(missing_bom_products))
                )

            if not components:
                raise UserError(
                    _("Không tính được NVL từ BoM. Vui lòng kiểm tra lại dữ liệu.")
                )

            # ===== 2. Tạo phiếu xuất NVL (PXK) + dòng NVL =====
            if not order.location_production_id:
                raise UserError(_("Vui lòng cấu hình 'Kho sản xuất' trước (đích PXK)."))

            raw_vals = {
                "picking_type_id": order.picking_type_out_id.id,
                "company_id": order.company_id.id,
                "origin": order.name,
                "location_id": order.location_src_id.id,
                "location_dest_id": order.location_production_id.id,
            }
            raw_picking = Picking.create(raw_vals)

            for (prod_id, uom_id), qty in components.items():
                Move.create(
                    {
                        "name": self.env["product.product"]
                        .browse(prod_id)
                        .display_name,
                        "product_id": prod_id,
                        "product_uom": uom_id,
                        "product_uom_qty": qty,
                        "company_id": order.company_id.id,
                        "picking_id": raw_picking.id,
                        "location_id": order.location_src_id.id,
                        "location_dest_id": order.location_production_id.id,
                    }
                )

            # ===== 3. Tạo phiếu nhập TP (PNK) + dòng TP =====
            # Nguồn PNK: dùng default_location_src_id của picking_type_in (thường là Vendors)
            src_in = (
                order.picking_type_in_id.default_location_src_id
                or order.picking_type_in_id.warehouse_id and order.picking_type_in_id.warehouse_id.wh_input_stock_loc_id
            )
            if not src_in:
                raise UserError(
                    _(
                        "Loại dịch chuyển PNK (incoming) không có kho nguồn mặc định.\n"
                        "Vui lòng cấu hình default source location cho loại dịch chuyển nhập."
                    )
                )

            dest_in = order.location_dest_id

            finished_vals = {
                "picking_type_id": order.picking_type_in_id.id,
                "company_id": order.company_id.id,
                "origin": order.name,
                "location_id": src_in.id,
                "location_dest_id": dest_in.id,
            }
            finished_picking = Picking.create(finished_vals)

            for line in order.line_ids:
                if not line.product_id or not line.product_qty:
                    continue
                Move.create(
                    {
                        "name": line.product_id.display_name or line.product_id.name,
                        "product_id": line.product_id.id,
                        "product_uom": line.product_uom_id.id,
                        "product_uom_qty": line.product_qty,
                        "company_id": order.company_id.id,
                        "picking_id": finished_picking.id,
                        "location_id": src_in.id,
                        "location_dest_id": dest_in.id,
                    }
                )

            order.picking_raw_id = raw_picking.id
            order.picking_finished_id = finished_picking.id

        return True

    def action_view_productions(self):
        self.ensure_one()
        prods = self.line_ids.mapped("mrp_production_id")
        action = self.env.ref("mrp.mrp_production_action").read()[0]
        action["domain"] = [("id", "in", prods.ids)]
        return action

    def action_view_raw_picking(self):
        self.ensure_one()
        if not self.picking_raw_id:
            return False
        return {
            "name": _("Phiếu xuất NVL"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "view_id": self.env.ref("stock.view_picking_form").id,
            "res_id": self.picking_raw_id.id,
            "target": "current",
        }

    def action_view_finished_picking(self):
        self.ensure_one()
        if not self.picking_finished_id:
            return False
        return {
            "name": _("Phiếu nhập TP"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "view_id": self.env.ref("stock.view_picking_form").id,
            "res_id": self.picking_finished_id.id,
            "target": "current",
        }

    def action_produce_all(self):
        """
        MISA style:
        - Đánh dấu tất cả các lệnh sản xuất con (mrp.production) là 'Hoàn tất'.
        - CHỈ đổi trạng thái, KHÔNG gọi button_mark_done để tránh sinh thêm
          nhập/xuất kho (vì mình đã dùng PXK/PNK là chứng từ chính).
        """
        MrpProduction = self.env["mrp.production"]

        for order in self:
            mos = order.line_ids.mapped("mrp_production_id")
            if not mos:
                # Không có MO nào, bỏ qua lệnh này
                continue

            mos_to_close = mos.filtered(lambda m: m.state not in ("done", "cancel"))
            if not mos_to_close:
                continue

            # Đổi trực tiếp state -> done (MO làm chứng từ kế hoạch)
            mos_to_close.write({"state": "done"})

        return True

class MultiMrpOrderLine(models.Model):
    _name = "multi.mrp.order.line"
    _description = "Dòng thành phẩm của lệnh sản xuất nhiều thành phẩm"
    _order = "order_id, id"

    order_id = fields.Many2one(
        "multi.mrp.order",
        string="Lệnh sản xuất",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        related="order_id.company_id",
        store=True,
        readonly=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Thành phẩm",
        required=True,
        domain=[("type", "!=", "service")],
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Mẫu sản phẩm",
        related="product_id.product_tmpl_id",
        store=True,
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="Đơn vị tính",
        required=True,
    )
    product_qty = fields.Float(
        string="Số lượng",
        default=1.0,
    )

    bom_id = fields.Many2one(
        "mrp.bom",
        string="Định mức NVL",
        domain="[('product_tmpl_id', '=', product_tmpl_id),"
        "  ('company_id', 'in', [company_id, False])]",
    )

    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Dòng đơn bán",
        domain="[('order_id', '=', parent.sale_id)]",
    )

    mrp_production_id = fields.Many2one(
        "mrp.production",
        string="Lệnh sản xuất chi tiết",
        readonly=True,
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        Bom = self.env["mrp.bom"]
        for line in self:
            if not line.product_id:
                line.product_uom_id = False
                line.bom_id = False
                continue

            line.product_uom_id = line.product_id.uom_id

            if not line.bom_id and line.product_tmpl_id:
                bom = Bom.search(
                    [
                        ("product_tmpl_id", "=", line.product_tmpl_id.id),
                        ("company_id", "in", [line.company_id.id, False]),
                        ("type", "=", "normal"),
                    ],
                    limit=1,
                )
                line.bom_id = bom
