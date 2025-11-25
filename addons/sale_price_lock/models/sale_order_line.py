# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    lock_price = fields.Boolean(
        string="Khóa giá",
        help="Nếu bật, thay đổi số lượng/đơn vị sẽ không làm cập nhật lại đơn giá theo Pricelist.",
    )
    manual_price_unit = fields.Monetary(
        string="Đơn giá (khóa)",
        help="Giá người dùng nhập tay để giữ lại khi thay đổi số lượng/đơn vị.",
        currency_field="currency_id",
    )

    # Khi người dùng sửa tay price_unit thì tự bật khóa & lưu giá
    @api.onchange("price_unit")
    def _onchange_price_unit_lock(self):
        for line in self:
            if line.price_unit:
                # Nếu người dùng gõ tay, ta bật khóa và lưu giá
                line.lock_price = True
                line.manual_price_unit = line.price_unit

    # Khi đổi sản phẩm / Pricelist -> bỏ khóa để hệ thống tính lại bình thường
    @api.onchange("product_id", "order_id.pricelist_id")
    def _onchange_reset_lock_on_product_or_pricelist(self):
        for line in self:
            # Chỉ reset khi vừa đổi sản phẩm hoặc Pricelist,
            # không can thiệp lúc người ta chỉ sửa số lượng
            line.lock_price = False
            line.manual_price_unit = False

    # Khi đổi số lượng/đơn vị/chiết khấu -> nếu đang khóa giá, set lại đơn giá đã lưu
    @api.onchange("product_uom_qty", "product_uom", "discount")
    def _onchange_qty_keep_locked_price(self):
        for line in self:
            # Không đụng các dòng hiển thị tiêu đề/ghi chú
            if line.display_type:
                continue
            if line.lock_price and line.manual_price_unit:
                # Odoo có thể đã tính lại price_unit theo Pricelist ở các onchange gốc,
                # ta set lại giá đã khóa để bảo toàn
                line.price_unit = line.manual_price_unit
