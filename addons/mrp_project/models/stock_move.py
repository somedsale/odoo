# -*- coding: utf-8 -*-
from odoo import models, fields, api , _
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'


    # Project propagated from related MO (finished or raw material moves)
    project_id = fields.Many2one('project.project', string='Dự án',
    compute='_compute_project_id', store=True, index=True)
    mrp_location_state = fields.Selection(
        [
            ('enough', 'Có hàng'),
            ('partial', 'Thiếu một phần'),
            ('none', 'Không có hàng'),
        ],
        string="Tồn tại vị trí",
        compute="_compute_mrp_location_state",
        store=False,
    )

    # Tồn thực tế tại vị trí (location_id) của dòng này
    mrp_qty_on_hand_location = fields.Float(
        string="Tồn tại vị trí",
        compute="_compute_mrp_qty_on_hand_location",
        help="Tồn vật lý tại vị trí thành phần (bao gồm cả phần đã đặt trước).",
    )
    @api.depends('production_id', 'raw_material_production_id',
    'production_id.project_id', 'raw_material_production_id.project_id')
    def _compute_project_id(self):
        for m in self:
            proj = m.production_id.project_id or m.raw_material_production_id.project_id
            m.project_id = proj.id if proj else False


    @api.onchange('project_id')
    def _onchange_project_product_domain(self):
        domain = {}
        if self.project_id and self.project_id.sale_product_ids:
            domain['product_id'] = [('id', 'in', self.project_id.sale_product_ids.ids)]
        return {'domain': domain}
    def _action_assign(self, *args, **kwargs):
        """Không reserve cho move nguyên vật liệu của lệnh sản xuất.

        - move.raw_material_production_id != False  -> NVL của MO
        - các move khác (delivery, receipt, thành phẩm...) vẫn assign bình thường
        """
        mrp_raw_moves = self.filtered(lambda m: m.raw_material_production_id)
        other_moves = self - mrp_raw_moves

        # Mặc định recordset rỗng
        res = self.env['stock.move']

        # Chỉ gọi super cho các move không phải NVL sản xuất
        if other_moves:
            res_super = super(StockMove, other_moves)._action_assign(*args, **kwargs)
            # core đôi khi trả None, nên phải bảo vệ
            if res_super is not None:
                res = res_super

        # Không assign cho mrp_raw_moves, nhưng vẫn trả về cùng recordset
        return res | mrp_raw_moves
    def _action_done(self, cancel_backorder=False):
        """
        Chặn xuất âm khi tiêu thụ NGUYÊN VẬT LIỆU cho lệnh sản xuất.
        - Chỉ check các move nguyên vật liệu (raw_material_production_id != False)
        - Chỉ check sản phẩm stockable (type = 'product') ở vị trí nội bộ.
        """
        Quant = self.env['stock.quant']

        for move in self.filtered(
            lambda m: m.raw_material_production_id
            and m.product_id.type == 'product'
            and m.location_id.usage == 'internal'
        ):
            # Xác định số lượng thực sự sẽ tiêu thụ cho move này
            if 'quantity' in move._fields:
                qty_to_consume = move.quantity
            else:
                # fallback: dùng số lượng kế hoạch
                qty_to_consume = move.product_uom_qty

            if not qty_to_consume:
                # không tiêu thụ gì thì bỏ qua
                continue

            # Lấy tồn kho hiện tại tại đúng location thành phần (và các location con)
            domain = [
                ('product_id', '=', move.product_id.id),
                ('location_id', 'child_of', move.location_id.id),
            ]
            data = Quant.read_group(
                domain,
                ['quantity:sum', 'reserved_quantity:sum'],
                ['product_id'],
            )

            qty = data[0]['quantity'] or 0.0 if data else 0.0
            reserved = data[0]['reserved_quantity'] or 0.0 if data else 0.0

            # tồn có thể dùng = tồn - đã dự trữ
            free = qty - reserved

            if free < qty_to_consume:
                # Không đủ tồn -> không cho Done, tránh xuất âm
                raise UserError(_(
                    "Không đủ tồn kho cho sản phẩm %(product)s tại vị trí %(location)s.\n"
                    "Tồn có thể dùng: %(free).2f, cần dùng: %(need).2f."
                ) % {
                    'product': move.product_id.display_name,
                    'location': move.location_id.display_name,
                    'free': free,
                    'need': qty_to_consume,
                })

        # Nếu mọi thứ ok thì gọi logic chuẩn
        return super()._action_done(cancel_backorder=cancel_backorder)
    @api.depends('product_id', 'product_uom_qty', 'location_id', 'raw_material_production_id')
    def _compute_mrp_location_state(self):
        Quant = self.env['stock.quant']
        for move in self:
            # Chỉ check cho NVL của lệnh sản xuất, ở kho nội bộ
            if (
                not move.raw_material_production_id
                or not move.product_id
                or move.location_id.usage != 'internal'
            ):
                move.mrp_location_state = False
                continue

            # Lấy tồn tại đúng Location thành phần (và con)
            domain = [
                ('product_id', '=', move.product_id.id),
                ('location_id', 'child_of', move.location_id.id),
            ]
            data = Quant.read_group(
                domain,
                ['quantity:sum', 'reserved_quantity:sum'],
                ['product_id'],
            )
            qty = data[0]['quantity'] or 0.0 if data else 0.0
            reserved = data[0]['reserved_quantity'] or 0.0 if data else 0.0

            # Bạn muốn chỉ check tồn thực tế, có thể:
            free = qty  # nếu bỏ qua phần reserved
            # hoặc: free = qty - reserved  nếu bạn vẫn muốn trừ phần đã đặt chỗ

            if free <= 0:
                move.mrp_location_state = 'none'
            elif free < move.product_uom_qty:
                move.mrp_location_state = 'partial'
            else:
                move.mrp_location_state = 'enough'
    @api.depends('product_id', 'location_id')
    def _compute_mrp_qty_on_hand_location(self):
        Quant = self.env['stock.quant']
        for move in self:
            if not move.product_id or not move.location_id or move.location_id.usage != 'internal':
                move.mrp_qty_on_hand_location = 0.0
                continue

            data = Quant.read_group(
                [
                    ('product_id', '=', move.product_id.id),
                    ('location_id', 'child_of', move.location_id.id),
                ],
                ['quantity:sum', 'reserved_quantity:sum'],
                ['product_id'],
            )
            if data:
                qty = data[0]['quantity'] or 0.0
                reserved = data[0]['reserved_quantity'] or 0.0
                # 👉 Tồn có thể dùng = tồn - đã đặt trước
                move.mrp_qty_on_hand_location = qty - reserved
            else:
                move.mrp_qty_on_hand_location = 0.0