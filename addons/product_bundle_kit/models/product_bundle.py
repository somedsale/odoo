from odoo import models, fields, api


class ProductBundle(models.Model):
    _name = "product.bundle"
    _description = "Sản phẩm cha - Sản phẩm con (Bundle)"

    name = fields.Char("Tên gói sản phẩm", required=True)
    product_id = fields.Many2one("product.product", string="Sản phẩm cha", required=True)

    line_ids = fields.One2many(
        "product.bundle.line",
        "bundle_id",
        string="Danh sách sản phẩm con"
    )


class ProductBundleLine(models.Model):
    _name = "product.bundle.line"
    _description = "Chi tiết sản phẩm con"

    bundle_id = fields.Many2one("product.bundle", string="Gói")
    product_id = fields.Many2one("product.product", string="Sản phẩm con", required=True)
    quantity = fields.Float("Số lượng", default=1.0)
    show_on_sale = fields.Boolean("Hiển thị trên báo giá", default=True)
