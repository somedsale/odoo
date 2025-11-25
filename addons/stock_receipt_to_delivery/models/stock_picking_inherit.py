# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_incoming_done = fields.Boolean(
        string="Là phiếu nhập đã xong",
        compute="_compute_is_incoming_done",
        store=False,
        default=False
    )
    # Phiếu nhập này đã bấm "Xuất hàng" chưa
    is_delivery = fields.Boolean(
        string="Đã tạo xuất hàng",
        default=False,
        help="Bật khi phiếu nhập này đã tạo 1 phiếu giao hàng tương ứng."
    )
    def _compute_is_incoming_done(self):
        for p in self:
            p.is_incoming_done = (p.picking_type_id.code == 'incoming' and p.state == 'done')
    def _ml_done_qty(self, ml):
        """Trả về qty đã thực sự di chuyển của 1 move line, chịu nhiều phiên bản."""
        # Odoo 17 chuẩn có qty_done; môi trường bạn có thể không.
        if hasattr(ml, 'qty_done') and ml.qty_done is not None:
            return ml.qty_done
        # Ở phiếu đã 'done', product_uom_qty = qty thực tế (đa số build)
        if hasattr(ml, 'product_uom_qty') and ml.product_uom_qty is not None:
            return ml.product_uom_qty
        # fallback: số đã reserve (ít gặp)
        if hasattr(ml, 'reserved_uom_qty') and ml.reserved_uom_qty is not None:
            return ml.reserved_uom_qty
        return 0.0

    def action_create_delivery_from_receipt(self):
        """
        Tạo 1 Delivery (outgoing picking) từ Phiếu nhập đã hoàn tất.
        - Không truy cập qty_done (tránh khác biệt version/build).
        - Ưu tiên lấy số lượng từ move line -> product_uom_qty (sau khi Done thường = số thực nhập).
        - Nếu move line không có hoặc tổng = 0, fallback dùng product_uom_qty trên move.
        - Tạo moves cho Delivery theo (product, uom), confirm/assign (không auto-validate).
        - Mở form phiếu giao hàng vừa tạo.
        """
        self.ensure_one()
        picking = self

        # 1) Kiểm tra điều kiện
        if picking.picking_type_id.code != 'incoming' or picking.state != 'done':
            raise UserError(_("Chỉ thực hiện trên Phiếu nhập (incoming) đã hoàn tất."))

        wh = picking.picking_type_id.warehouse_id
        out_type = wh and wh.out_type_id or self.env['stock.picking.type'].search([
            ('warehouse_id', '=', wh.id if wh else False),
            ('code', '=', 'outgoing')
        ], limit=1)
        if not out_type:
            raise UserError(_("Không tìm thấy loại giao hàng (Outgoing) cho kho hiện tại."))

        # Nguồn/lịch xuất: ưu tiên cấu hình trên picking type
        src_loc = out_type.default_location_src_id or picking.location_dest_id
        dst_loc = out_type.default_location_dest_id
        if not (src_loc and dst_loc):
            raise UserError(_("Thiếu cấu hình vị trí nguồn/đích cho loại giao hàng (Outgoing)."))

        # 2) Gom số lượng đã nhập theo (product, uom)
        #    - Ưu tiên từ move line: product_uom_qty
        #    - Fallback: từ move: product_uom_qty
        grouped = {}

        # 2.1 Từ move line
        for mv in picking.move_ids_without_package:
            line_total = 0.0
            for ml in mv.move_line_ids:
                # product_uom_qty trên move line: số lượng dòng (ở phiếu Done thường chính là số đã nhập)
                q = getattr(ml, 'product_uom_qty', 0.0) or 0.0
                if q > 0 and ml.product_id and ml.product_uom_id:
                    key = (ml.product_id.id, ml.product_uom_id.id)
                    grouped[key] = grouped.get(key, 0.0) + q
                    line_total += q

            # 2.2 Nếu không có line hoặc line_total = 0 → fallback dùng qty trên move
            if line_total == 0.0:
                q_mv = getattr(mv, 'product_uom_qty', 0.0) or 0.0
                if q_mv > 0 and mv.product_id and mv.product_uom:
                    key = (mv.product_id.id, mv.product_uom.id)
                    grouped[key] = grouped.get(key, 0.0) + q_mv

        if not grouped:
            raise UserError(_("Phiếu nhập này không có số lượng đã nhập để xuất."))

        # 3) Chuẩn bị move values cho Delivery
        moves_vals = []
        for (prod_id, uom_id), qty in grouped.items():
            moves_vals.append((0, 0, {
                'name': picking.name,
                'product_id': prod_id,
                'product_uom': uom_id,
                'product_uom_qty': qty,
                'location_id': src_loc.id,
                'location_dest_id': dst_loc.id,
            }))

        # 4) Partner: nếu partner hiện tại là khách (customer_rank>0) thì dùng, ngược lại để trống
        partner_id = picking.partner_id.id if (picking.partner_id and picking.partner_id.customer_rank > 0) else False

        # 5) Tạo Delivery
        delivery = self.env['stock.picking'].create({
            'picking_type_id': out_type.id,
            'partner_id': partner_id,
            'origin': f"{picking.name} → Delivery",
            'location_id': src_loc.id,
            'location_dest_id': dst_loc.id,
            'move_ids_without_package': moves_vals,
        })

        # 6) Confirm/Assign (không auto-validate)
        if delivery.state == 'draft':
            delivery.action_confirm()
        if delivery.state in ('confirmed', 'waiting'):
            delivery.action_assign()
        # 👉 Đánh dấu phiếu nhập đã tạo xuất hàng
        picking.is_delivery = True
        # 7) Mở form Delivery vừa tạo
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        action.update({
            'views': [(False, 'form')],
            'res_id': delivery.id,
            'view_mode': 'form',
            'target': 'current',
        })
        return action
