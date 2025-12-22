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
    contract_id = fields.Many2one(
        "contract.management",
        string="Hợp đồng",
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
        string="Loại phiếu xuất kho (outgoing)",
        domain=[("code", "=", "outgoing")],
        default=lambda self: self._default_picking_type_out_id(),
        help="Loại dịch chuyển dùng để tạo phiếu xuất kho (Delivery Order).",
    )
    # PNK: dùng loại dịch chuyển nhập (incoming) để không bị check tồn ở nguồn
    picking_type_in_id = fields.Many2one(
        "stock.picking.type",
        string="Loại dịch chuyển PNK (incoming)",
        domain=[("code", "=", "incoming")],
        default=lambda self: self._default_picking_type_in_id(),
        help="Loại dịch chuyển dùng để tạo phiếu nhập thành phẩm (nhập kho).",
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
    location_src_id = fields.Many2one(
        "stock.location",
        string="Kho NVL",
        domain=[("usage", "=", "internal")],
        default=lambda self: self._default_mo_src_location_id(),
        help="Kho xuất nguyên vật liệu (theo default của Lệnh sản xuất).",
    )

    location_production_id = fields.Many2one(
        "stock.location",
        string="Kho sản xuất",
        domain=[("usage", "=", "production")],
        default=lambda self: self._default_production_location_id(),
        help="Luôn là Virtual Locations/Production.",
    )

    location_dest_id = fields.Many2one(
        "stock.location",
        string="Kho thành phẩm",
        domain=[("usage", "=", "internal")],
        default=lambda self: self._default_mo_dest_location_id(),
        help="Kho nhập thành phẩm (theo default của Lệnh sản xuất).",
    )
    def _set_done_qty_full(self, picking):
        """
        Universal for Odoo 17 variants:
        - Tự dò field done qty trên stock.move.line (qty_done / quantity / quantity_done ...)
        - Không dùng stock.move.quantity_done (DB bạn không có)
        - Nếu chưa có move_line thì tạo move_line và set done qty
        """
        MoveLine = self.env["stock.move.line"]

        # dò field "done qty" thật sự đang tồn tại
        ml_fields = MoveLine._fields
        done_field = None
        for f in ("qty_done", "quantity", "quantity_done"):
            if f in ml_fields:
                done_field = f
                break
        if not done_field:
            raise UserError(_("Không tìm thấy field Done Qty trên stock.move.line (qty_done/quantity/quantity_done)."))

        # dò field reserved (có thì dùng cho đẹp)
        reserved_field = None
        for f in ("reserved_uom_qty", "reserved_qty", "product_uom_qty"):
            if f in ml_fields:
                reserved_field = f
                break

        def _get_done(ml):
            return getattr(ml, done_field) or 0.0

        def _set_done(ml, val):
            setattr(ml, done_field, val)

        def _get_reserved(ml):
            if not reserved_field:
                return 0.0
            return getattr(ml, reserved_field) or 0.0

        for mv in picking.move_ids_without_package:
            if not mv.product_id:
                continue

            demand = mv.product_uom_qty or 0.0

            existing_done = 0.0
            for ml in mv.move_line_ids:
                existing_done += _get_done(ml)

            need = demand - existing_done
            if need <= 0:
                continue

            # Nếu đã có line (thường có khi assign), bơm done vào line
            if mv.move_line_ids:
                for ml in mv.move_line_ids:
                    if need <= 0:
                        break

                    reserved = _get_reserved(ml)
                    add = reserved if reserved > 0 else need
                    if add <= 0:
                        continue

                    _set_done(ml, _get_done(ml) + add)
                    need -= add

            # Nếu vẫn thiếu hoặc chưa có line thì tạo line mới và set done
            if need > 0:
                vals = {
                    "picking_id": picking.id,
                    "move_id": mv.id,
                    "company_id": picking.company_id.id,
                    "product_id": mv.product_id.id,
                    "product_uom_id": mv.product_uom.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    done_field: need,
                }
                MoveLine.create(vals)


    def _auto_validate_picking(self, picking):
        """
        Auto done picking:
        - confirm (draft -> confirmed)
        - assign (nếu internal source)
        - set qty_done (universal)
        - validate, và cố bypass backorder wizard bằng context
        """
        if not picking or picking.state in ("done", "cancel"):
            return True

        if picking.state == "draft":
            picking.action_confirm()

        # assign để sinh reservation + move lines (đặc biệt với internal source)
        if picking.state in ("confirmed", "waiting"):
            picking.action_assign()

        # set done qty
        self._set_done_qty_full(picking)

        ctx = dict(self.env.context)
        ctx.update({
            "skip_backorder": True,
            "cancel_backorder": True,
            "force_no_backorder": True,
        })
        res = picking.with_context(ctx).button_validate()

        # Nếu validate trả về wizard dict thì stop ở đây (đỡ crash)
        # (Nếu bạn muốn auto xử wizard tiếp thì mình sẽ hook theo model wizard đúng tên trong DB bạn)
        if isinstance(res, dict):
            # để khỏi làm user “kẹt”: báo rõ
            raise UserError(_(
                "Hệ thống yêu cầu wizard khi hoàn tất phiếu kho (backorder/validation).\n"
                "Bạn cần mở phiếu kho và bấm Validate thủ công 1 lần, hoặc gửi mình dict res để mình auto xử lý wizard đúng model trong DB bạn."
            ))

        return True


    @api.model
    def _default_picking_type_out_id(self):
        company = self.env.company
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),   # <-- đổi internal -> outgoing
                ("company_id", "in", [company.id, False]),
            ],
            limit=1,
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
                if not order.location_src_id:
                    order.location_src_id = self.env["stock.location"].browse(order._default_mo_src_location_id())
                if not order.location_dest_id:
                    order.location_dest_id = self.env["stock.location"].browse(order._default_mo_dest_location_id())
                if not order.location_production_id:
                    order.location_production_id = self.env["stock.location"].browse(order._default_production_location_id())

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
            self.action_generate_pickings()
        self.write({"state": "confirmed"})
        return True

    def action_done(self):
        for order in self:
            # (1) Nếu còn MO con chưa done/cancel thì chặn như cũ
            # not_done = order.line_ids.mapped("mrp_production_id").filtered(
            #     lambda mo: mo.state not in ("done", "cancel")
            # )
            # if not_done:
            #     raise UserError(
            #         _(
            #             "Vẫn còn lệnh sản xuất chi tiết chưa hoàn tất hoặc bị hủy.\n"
            #             "Vui lòng kiểm tra lại."
            #         )
            #     )

            # (2) Tự hoàn tất PXK NVL
            if order.picking_raw_id and order.picking_raw_id.state not in ("done", "cancel"):
                order._auto_validate_picking(order.picking_raw_id)

            # (3) Tự hoàn tất PNK TP
            if order.picking_finished_id and order.picking_finished_id.state not in ("done", "cancel"):
                order._auto_validate_picking(order.picking_finished_id)

        self.write({"state": "done"})
        return True
    @api.onchange("picking_raw_id", "picking_finished_id")
    def _onchange_picking_ids(self):
        if self.picking_raw_id and self.picking_finished_id:
            if self.picking_raw_id.state == "done" or self.picking_finished_id.state == "done":
                self.write({"state": "done"})
    def _try_set_done_if_pickings_done(self):
        for order in self:
            if order.state in ("done", "cancel"):
                continue
            if not order.picking_raw_id or not order.picking_finished_id:
                continue
            if order.picking_raw_id.state != "done" or order.picking_finished_id.state != "done":
                continue

            # nếu bạn muốn BỎ check MO thì xóa đoạn này
            mos = order.line_ids.mapped("mrp_production_id")
            not_done = mos.filtered(lambda mo: mo.state not in ("done", "cancel"))
            if not_done:
                continue

            order.write({"state": "done"})


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
                if "contract_id" in MrpProduction._fields and order.contract_id:
                    mo_vals["contract_id"] = order.contract_id.id

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
                "contract_id": self.contract_id.id if self.contract_id else False,
                "location_id": order.location_src_id.id,
                "location_dest_id": order.location_production_id.id,
                "delivery_reason": _("Xuất kho sản xuất cho công trình: %s") % self.contract_id.num_contract if self.contract_id else '',
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
                "contract_id": self.contract_id.id if self.contract_id else False,
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
    @api.model
    def _default_location_src_id(self):
        """Kho NVL mặc định theo picking type internal."""
        pt = self.env["stock.picking.type"].browse(self._default_picking_type_out_id())
        if pt and pt.default_location_src_id:
            return pt.default_location_src_id.id
        # fallback: kho Stock của warehouse
        if pt and pt.warehouse_id and pt.warehouse_id.lot_stock_id:
            return pt.warehouse_id.lot_stock_id.id
        return False

    @api.model
    def _default_location_production_id(self):
        """Kho sản xuất (đích PXK) theo picking type internal."""
        pt = self.env["stock.picking.type"].browse(self._default_picking_type_out_id())
        if pt and pt.default_location_dest_id:
            return pt.default_location_dest_id.id

        # fallback: location Production của warehouse (nếu có)
        wh = pt.warehouse_id if pt else False
        prod_loc = getattr(wh, "wh_production_stock_loc_id", False) if wh else False
        if prod_loc:
            return prod_loc.id

        # fallback cuối: tìm 1 location usage=production trong công ty
        loc = self.env["stock.location"].search(
            [("usage", "=", "production"), ("company_id", "in", [self.env.company.id, False])],
            limit=1,
        )
        return loc.id or False

    @api.model
    def _default_location_dest_id(self):
        """Kho thành phẩm (đích PNK) theo picking type incoming."""
        pt = self.env["stock.picking.type"].browse(self._default_picking_type_in_id())
        if pt and pt.default_location_dest_id:
            return pt.default_location_dest_id.id
        # fallback: kho Stock của warehouse
        if pt and pt.warehouse_id and pt.warehouse_id.lot_stock_id:
            return pt.warehouse_id.lot_stock_id.id
        return False
    @api.onchange("picking_type_out_id")
    def _onchange_picking_type_out_id(self):
        for order in self:
            pt = order.picking_type_out_id
            if not pt:
                continue

            # chỉ fill source nếu đang trống
            if not order.location_src_id and pt.default_location_src_id:
                order.location_src_id = pt.default_location_src_id

            # QUAN TRỌNG:
            # outgoing thường có dest mặc định là Customer => KHÔNG được lấy làm "Kho sản xuất"
            # chỉ set nếu dest thực sự là production, còn không thì giữ location_production_id hiện tại
            if (
                not order.location_production_id
                and pt.default_location_dest_id
                and pt.default_location_dest_id.usage == "production"
            ):
                order.location_production_id = pt.default_location_dest_id


    @api.onchange("picking_type_in_id")
    def _onchange_picking_type_in_id(self):
        for order in self:
            pt = order.picking_type_in_id
            if not pt:
                continue

            # Đích PNK = default dest của incoming
            if not order.location_dest_id and pt.default_location_dest_id:
                order.location_dest_id = pt.default_location_dest_id
    @api.model
    def _get_mrp_operation_type(self):
        """Lấy Operation Type dùng cho Manufacturing (MO)."""
        company = self.env.company
        pt = self.env["stock.picking.type"].search(
            [("code", "=", "mrp_operation"), ("company_id", "in", [company.id, False])],
            limit=1,
        )
        # fallback: nếu DB bạn không có code mrp_operation (custom), thì trả False
        return pt

    @api.model
    def _default_production_location_id(self):
        """Virtual Locations/Production."""
        # ưu tiên external id chuẩn của stock
        loc = self.env.ref("stock.location_production", raise_if_not_found=False)
        if loc:
            return loc.id
        # fallback search
        company = self.env.company
        loc = self.env["stock.location"].search(
            [("usage", "=", "production"), ("company_id", "in", [company.id, False])],
            limit=1,
        )
        return loc.id or False

    @api.model
    def _default_mo_src_location_id(self):
        """Kho NVL theo default của MO (source)."""
        pt = self._get_mrp_operation_type()
        if pt and pt.default_location_src_id and pt.default_location_src_id.usage == "internal":
            return pt.default_location_src_id.id

        # fallback: lấy kho Stock của warehouse nếu có
        if pt and pt.warehouse_id and pt.warehouse_id.lot_stock_id:
            return pt.warehouse_id.lot_stock_id.id

        # fallback cuối: tìm 1 internal location
        company = self.env.company
        loc = self.env["stock.location"].search(
            [("usage", "=", "internal"), ("company_id", "in", [company.id, False])],
            limit=1,
        )
        return loc.id or False

    @api.model
    def _default_mo_dest_location_id(self):
        """Kho Thành phẩm theo default của MO (destination)."""
        pt = self._get_mrp_operation_type()
        if pt and pt.default_location_dest_id and pt.default_location_dest_id.usage == "internal":
            return pt.default_location_dest_id.id

        # fallback: kho Stock của warehouse
        if pt and pt.warehouse_id and pt.warehouse_id.lot_stock_id:
            return pt.warehouse_id.lot_stock_id.id

        company = self.env.company
        loc = self.env["stock.location"].search(
            [("usage", "=", "internal"), ("company_id", "in", [company.id, False])],
            limit=1,
        )
        return loc.id or False

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
