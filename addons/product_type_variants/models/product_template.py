# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_type_id = fields.Many2one(
        "product.type",
        string="Loại sản phẩm",
        help="Phân loại sản phẩm theo nhóm nội bộ (Cửa, Ống đồng, Bed-head, Rèm, ...).",
    )

    attribute_set_id = fields.Many2one(
        "product.attribute.set",
        string="Bộ thuộc tính sản phẩm",
        help="Bộ thuộc tính áp dụng cho sản phẩm này.",
    )

    @api.onchange("product_type_id")
    def _onchange_product_type_id(self):
        """Khi chọn Loại sản phẩm -> tự gán bộ thuộc tính & sinh attribute lines."""
        for template in self:
            if not template.product_type_id:
                continue

            # Gán bộ thuộc tính từ loại sản phẩm (nếu có)
            if template.product_type_id.attribute_set_id:
                template.attribute_set_id = template.product_type_id.attribute_set_id

            # Sinh attribute lines từ attribute_set_id
            if template.attribute_set_id:
                template._apply_attribute_set()

    @api.onchange("attribute_set_id")
    def _onchange_attribute_set_id(self):
        """Cho phép đổi bộ thuộc tính thủ công nếu cần."""
        for template in self:
            if template.attribute_set_id:
                template._apply_attribute_set()

    def _apply_attribute_set(self):
        """Hàm dùng chung: xoá attribute line cũ và gán theo attribute_set_id."""
        for template in self:
            if not template.attribute_set_id:
                continue

            # Xoá tất cả attribute lines hiện tại
            template.attribute_line_ids = [(5, 0, 0)]

            lines = []
            for attr in template.attribute_set_id.attribute_ids:
                lines.append((0, 0, {
                    "attribute_id": attr.id,
                    # Chưa chọn sẵn value_ids -> user sẽ chọn giá trị sau.
                }))

            if lines:
                template.attribute_line_ids = lines
