# -*- coding: utf-8 -*-
from odoo import fields,api, models, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    project_id = fields.Many2one(
        "project.project",
        string="Dự án",
        store=True,
        index=True,
    )

    sale_product_ids = fields.Many2many(
        'product.product',
        string='Sản phẩm đơn bán',
        related='project_id.sale_product_ids',
        readonly=True
    )
    multi_mrp_order_raw_id = fields.Many2one(
        "multi.mrp.order",
        string="Lệnh SX nhiều TP (PXK)",
        index=True,
        ondelete="set null",
    )
    multi_mrp_order_finished_id = fields.Many2one(
        "multi.mrp.order",
        string="Lệnh SX nhiều TP (PNK)",
        index=True,
        ondelete="set null",
    )
    @api.onchange('project_id')
    def _onchange_project_id_set_product_domain(self):
        """Cập nhật domain cho product_id và bom_id khi chọn dự án."""
        domain = {}
        if self.project_id and self.project_id.sale_product_ids:
            product_ids = self.project_id.sale_product_ids.ids
            domain['product_id'] = [('id', 'in', product_ids)]
            domain['bom_id'] = [
                '|',
                ('product_tmpl_id.product_variant_ids', 'in', product_ids),
                ('product_id', 'in', product_ids),
            ]
            # Nếu product hiện tại không còn hợp lệ, xóa nó
            if self.product_id and self.product_id.id not in product_ids:
                self.product_id = False
        else:
            domain['product_id'] = [('id', '!=', False)]
            domain['bom_id'] = [('id', '!=', False)]
        return {'domain': domain}
    def action_reset_to_draft_from_done(self):
        Quant = self.env["stock.quant"]

        for picking in self:
            if picking.state != "done":
                raise UserError(_("Chỉ phiếu đã hoàn tất mới có thể trở lại nháp."))

            if any(move.scrapped for move in picking.move_ids):
                raise UserError(_("Không thể trở lại nháp với phiếu có dòng phế phẩm."))

            # Nếu anh có chạy valuation tự động thì nên chặn ở đây.
            # Bỏ đoạn này nếu anh vẫn muốn ép chạy.
            categories = picking.move_ids.mapped("product_id.categ_id")
            if any(c.property_valuation == "real_time" for c in categories):
                raise UserError(_(
                    "Phiếu này thuộc nhóm sản phẩm đang dùng định giá tồn kho tự động "
                    "(real_time). Không nên reset trực tiếp vì có thể lệch kế toán kho."
                ))

            # 1) ĐẢO LẠI TỒN KHO
            for ml in picking.move_line_ids:
                product = ml.product_id
                if product.type != "product":
                    continue

                qty = ml.quantity or 0.0
                if not qty:
                    continue

                # Đảo hướng lại:
                # đã done: source -> dest
                # reset: trừ ở dest, cộng lại source
                Quant._update_available_quantity(
                    product,
                    ml.location_dest_id,
                    -qty,
                    lot_id=ml.lot_id,
                    package_id=ml.package_id,
                    owner_id=ml.owner_id,
                    in_date=False,
                )
                Quant._update_available_quantity(
                    product,
                    ml.location_id,
                    qty,
                    lot_id=ml.lot_id,
                    package_id=ml.package_id,
                    owner_id=ml.owner_id,
                    in_date=False,
                )

            move_line_ids = picking.move_line_ids.ids
            move_ids = picking.move_ids.ids

            # 2) XÓA MOVE LINE BẰNG SQL
            # Odoo chặn unlink bằng ORM khi phiếu đã done, nên dùng SQL
            if move_line_ids:
                self.env.cr.execute("""
                    DELETE FROM stock_move_line
                    WHERE id IN %s
                """, [tuple(move_line_ids)])

            # 3) RESET STOCK MOVE
            if move_ids:
                # reset quantity_done / state
                # quantity_done có thể không phải field chuẩn trên mọi bản custom,
                # nên chỉ reset các field chắc chắn hơn.
                self.env.cr.execute("""
                    UPDATE stock_move
                    SET state = 'draft',
                        picked = FALSE
                    WHERE id IN %s
                """, [tuple(move_ids)])

            # 4) RESET PICKING
            vals_sql = """
                UPDATE stock_picking
                SET state = 'draft',
                    date_done = NULL,
                    is_locked = FALSE
                WHERE id = %s
            """
            self.env.cr.execute(vals_sql, [picking.id])

            # 5) clear cache để ORM đọc lại dữ liệu mới
            self.env.invalidate_all()

        return True