from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    move_line_image = fields.Binary(
        string="Hình ảnh",
        related="product_id.image_1920",
        help="Hình ảnh sản phẩm",
    )




