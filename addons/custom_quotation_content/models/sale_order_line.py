from odoo import fields, models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_thongso = fields.Text(string='Thông số', related='product_id.product_tmpl_id.x_thong_so', store=True, readonly=True)
    x_xuatxu = fields.Char(string='Xuất xứ', related='product_id.product_tmpl_id.x_xuat_xu', store=True, readonly=True)