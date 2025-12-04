# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        index=True,
        help='Gắn Lệnh sản xuất với một Dự án.'
    )

    sale_product_ids = fields.Many2many(
        'product.product',
        string='Sản phẩm đơn bán',
        related='project_id.sale_product_ids',
        readonly=True
    )
    sale_product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm từ đơn bán'
    )
    has_sale_products = fields.Boolean(
        string='Có sản phẩm đơn bán',
        compute='_compute_has_sale_products'
    )
    product_description = fields.Text(
        string="Diễn giải sản phẩm",
        related="product_id.description_sale",
        readonly=False,   # cho sửa thêm nếu muốn; để True nếu chỉ xem
    )
    @api.onchange("project_id")
    def _onchange_project_id(self):
        """Khi đổi dự án:
        - Xoá sản phẩm cũ
        - Set domain sale_product_id theo project_id.sale_product_ids
        """
        self.sale_product_id = False
        self.product_id = False

        domain = {}

        if self.project_id:
            # Ưu tiên dùng sale_product_ids như bạn yêu cầu
            product_ids = self.project_id.sale_product_ids.ids

            # Nếu vì lý do gì đó sale_product_ids rỗng mà vẫn có sale_order,
            # có thể fallback trực tiếp từ sale_order (an toàn thêm)
            if not product_ids and self.project_id.sale_order_id:
                product_ids = self.project_id.sale_order_id.order_line.mapped('product_id').ids

            # Nếu vẫn không có sản phẩm -> giới hạn domain về rỗng (id = 0)
            if product_ids:
                domain['sale_product_id'] = [('id', 'in', product_ids)]
            else:
                domain['sale_product_id'] = [('id', '=', 0)]
        else:
            # Không chọn dự án -> không cho chọn sản phẩm luôn (tuỳ bạn)
            domain['sale_product_id'] = [('id', '=', 0)]

        return {'domain': domain}

    @api.onchange("sale_product_id")
    def _onchange_sale_product_id(self):
        """Chọn sản phẩm từ đơn bán:
        - Gán sang product_id để sản xuất
        - Lấy luôn số lượng từ sale_order (product_qty)
        """
        for rec in self:
            if rec.sale_product_id:
                rec.product_id = rec.sale_product_id

                qty = 0.0
                # Lấy từ sale_order gắn với project (nếu có)
                sale_order = getattr(rec.project_id, "sale_order_id", False)
                if sale_order:
                    # lọc tất cả line có cùng product
                    lines = sale_order.order_line.filtered(
                        lambda l: l.product_id == rec.sale_product_id
                    )
                    # nếu có nhiều line thì cộng dồn
                    qty = sum(lines.mapped('product_uom_qty'))

                if qty:
                    rec.product_qty = qty
                # nếu không tìm được line thì để product_qty user tự nhập
    @api.depends('sale_product_ids')
    def _compute_has_sale_products(self):
        for rec in self:
            rec.has_sale_products = bool(rec.sale_product_ids)
    def action_confirm(self):
        """Chỉ cho xác nhận MO khi đủ hàng ở vị trí thành phần (Nguyên vật liệu)."""
        Quant = self.env['stock.quant']

        for production in self:
            # chỉ check nguyên vật liệu stockable, lấy từ kho nội bộ
            raw_moves = production.move_raw_ids.filtered(
                lambda m: m.product_id
                and m.product_id.type == 'product'
                and m.location_id
                and m.location_id.usage == 'internal'
            )

            for move in raw_moves:
                qty_needed = move.product_uom_qty or 0.0
                if not qty_needed:
                    continue  # dòng này không dùng gì thì bỏ qua

                # tồn & reserved tại đúng location thành phần (và location con)
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
                free = qty - reserved  # tồn có thể dùng

                if free < qty_needed:
                    # Thiếu -> không cho xác nhận
                    raise UserError(_(
                        "Không đủ tồn kho để xác nhận lệnh sản xuất.\n\n"
                        "Sản phẩm: %(product)s\n"
                        "Vị trí: %(location)s\n"
                        "Tồn có thể dùng: %(free).2f\n"
                        "Cần dùng: %(need).2f"
                    ) % {
                        'product': move.product_id.display_name,
                        'location': move.location_id.display_name,
                        'free': free,
                        'need': qty_needed,
                    })

        # Nếu tất cả đủ hàng -> cho xác nhận như bình thường
        res = super().action_confirm()

        # Nếu bạn đang dùng logic "không reserve NVL" thì vẫn có thể unreserve lại ở đây:
        # self.mapped('move_raw_ids')._do_unreserve()

        return res
    def write(self, vals):
        res = super().write(vals)
        # Khi đổi số lượng thành phẩm hoặc BOM -> bỏ reserve NVL (nếu có)
        if any(field in vals for field in ['product_qty', 'bom_id']):
            self.mapped('move_raw_ids')._do_unreserve()
        return res
        