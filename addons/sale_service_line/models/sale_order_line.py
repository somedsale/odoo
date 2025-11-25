# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Field dịch vụ
    service_name = fields.Char(
        string="Dịch vụ",
        help="Nhập mô tả dịch vụ, ví dụ: Cung cấp & lắp đặt",
    )

    @api.depends("name", "product_id", "service_name", "order_id")
    def _compute_display_name(self):
        """
        Ghi đè cách tính display_name của sale.order.line

        - Nếu có service_name: "service_name - name"
          (hoặc product_id.display_name nếu name trống)
        - Nếu không có: dùng name (hoặc product_id.display_name)
        """
        for line in self:
            # tên gốc của dòng (Odoo thường set = mô tả sản phẩm)
            base_name = line.product_id.name or line.product_id.display_name or ""
            if line.service_name:
                line.display_name = f"{line.service_name} {base_name}"
            else:
                line.display_name = base_name
