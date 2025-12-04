# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductType(models.Model):
    _name = "product.type"
    _description = "Loại sản phẩm Somed"

    name = fields.Char("Tên loại sản phẩm", required=True)
    code = fields.Char("Mã loại")
    attribute_set_id = fields.Many2one(
        "product.attribute.set",
        string="Bộ thuộc tính mặc định",
        help="Khi chọn loại sản phẩm này trên sản phẩm, hệ thống sẽ áp bộ thuộc tính này.",
    )
    active = fields.Boolean(default=True)
