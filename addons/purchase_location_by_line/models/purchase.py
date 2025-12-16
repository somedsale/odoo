from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    location_dest_id = fields.Many2one(
        comodel_name="stock.location",
        string="Tên kho",
        domain=[("usage", "in", ["internal", "transit"])],
        ondelete="set null",
    )

    @api.model
    def _first_picking_copy_vals(self, key, lines):
        vals = super()._first_picking_copy_vals(key, lines)
        for key_element in key:
            if "location_dest_id" in key_element:
                vals["location_dest_id"] = key_element["location_dest_id"].id
        return vals

    @api.model
    def _get_group_keys(self, order, line, picking=False):
        key = super()._get_group_keys(order, line, picking=picking)
        default_loc = self.env["stock.location"].browse(
            order._get_destination_location()
        )
        location = line.location_dest_id or default_loc
        return key + ({"location_dest_id": location},)

    def _get_sorted_keys(self, line):
        keys = super()._get_sorted_keys(line)
        return keys + (line.location_dest_id.id or 0,)

    def _create_stock_moves(self, picking):
        # 1) Tạo move như bình thường (gồm cả logic tách phiếu theo ngày/location của OCA)
        moves = super()._create_stock_moves(picking)

        # 2) Gán location_dest_id cho từng move theo Tên kho trên dòng PO
        for line in self:
            default_picking_location_id = line.order_id._get_destination_location()
            default_picking_location = self.env["stock.location"].browse(
                default_picking_location_id
            )
            location = line.location_dest_id or default_picking_location
            if location:
                line.move_ids.filtered(lambda m: m.state != "done").write(
                    {"location_dest_id": location.id}
                )

        # 3) Đồng bộ lại header của từng picking:
        #    nếu tất cả move trong picking cùng 1 kho đích thì set luôn picking.location_dest_id
        for picking_rec in self.mapped("move_ids.picking_id"):
            dest_ids = picking_rec.move_ids.filtered(
                lambda m: m.state not in ("cancel",)
            ).mapped("location_dest_id").ids
            dest_ids = list(set(dest_ids))
            if len(dest_ids) == 1:
                picking_rec.location_dest_id = dest_ids[0]

        return moves
