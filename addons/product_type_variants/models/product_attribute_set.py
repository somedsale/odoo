# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductAttributeSet(models.Model):
    _name = "product.attribute.set"
    _description = "Bộ thuộc tính sản phẩm (Somed)"

    name = fields.Char("Tên bộ thuộc tính", required=True)
    attribute_ids = fields.Many2many(
        "product.attribute",
        "product_attribute_set_rel",
        "set_id",
        "attribute_id",
        string="Thuộc tính",
    )

    active = fields.Boolean(default=True)
