# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_incoming_done = fields.Boolean(
        string="Là phiếu nhập đã xong",
        compute="_compute_is_incoming_done",
        store=False,
    )

    def _compute_is_incoming_done(self):
        for p in self:
            p.is_incoming_done = (p.picking_type_id.code == 'incoming' and p.state == 'done')
    def action_create_delivery_from_receipt(self):
        """
        Create an outgoing Delivery picking from a finished incoming Receipt:
        - Collect qty_done from move lines (group by product/uom)
        - Build a new outgoing picking in the same warehouse
        - Confirm/Assign (do not auto-validate)
        - Open the delivery form
        """
        self.ensure_one()
        picking = self


        # Guard conditions
        if picking.picking_type_code != 'incoming' or picking.state != 'done':
            raise UserError(_("Chỉ thực hiện trên Phiếu nhập đã hoàn tất."))


        wh = picking.picking_type_id.warehouse_id
        out_type = wh and wh.out_type_id or self.env['stock.picking.type'].search([
        ('warehouse_id', '=', wh.id if wh else False),
        ('code', '=', 'outgoing')
        ], limit=1)
        if not out_type:
            raise UserError(_("Không tìm thấy loại giao hàng (Outgoing) cho kho hiện tại."))


        src_loc = out_type.default_location_src_id or picking.location_dest_id
        dst_loc = out_type.default_location_dest_id
        if not (src_loc and dst_loc):
            raise UserError(_("Thiếu cấu hình location cho loại giao hàng (Outgoing)."))


    # Aggregate qty_done from receipt's move lines
        lines = picking.move_line_ids.filtered(lambda l: l.product_id and l.qty_done > 0)
        if not lines:
            raise UserError(_("Phiếu nhập này không có số lượng đã nhập (qty_done) để xuất."))


        grouped = {}
        for ml in lines:
            key = (ml.product_id.id, ml.product_uom_id.id)
        grouped[key] = grouped.get(key, 0.0) + ml.qty_done


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


        partner_id = picking.partner_id.id if (picking.partner_id and picking.partner_id.customer_rank > 0) else False


        delivery = self.env['stock.picking'].create({
        'picking_type_id': out_type.id,
        'partner_id': partner_id,
        'origin': f"{picking.name} → Delivery",
        'location_id': src_loc.id,
        'location_dest_id': dst_loc.id,
        'move_ids_without_package': moves_vals,
        })


        if delivery.state == 'draft':
            delivery.action_confirm()
        if delivery.state in ('confirmed', 'waiting'):
            delivery.action_assign()


        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        action.update({
        'views': [(False, 'form')],
        'res_id': delivery.id,
        'view_mode': 'form',
        'target': 'current',
        })
        return action