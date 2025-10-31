from odoo import models, api, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_thongso = fields.Text(string='Thông số')
    x_xuatxu = fields.Char(string='Xuất xứ')


