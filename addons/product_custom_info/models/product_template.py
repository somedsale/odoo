from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'
   
    x_thong_so = fields.Text(string="Thông số")
    x_xuat_xu = fields.Char(string="Xuất xứ")
    x_hang_sx = fields.Char(string="Hãng SX")
