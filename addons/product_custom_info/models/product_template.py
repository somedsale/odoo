from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_thong_so = fields.Char(string="Thông số")
    x_xuat_xu = fields.Char(string="Xuất xứ")
