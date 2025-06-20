from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_thong_so = fields.Char(string="Thông số", readonly=True)
    x_xuat_xu = fields.Char(string="Xuất xứ", readonly=True)

    @api.onchange('product_id')
    def _onchange_product_id_custom_fields(self):
        if self.product_id:
            tmpl = self.product_id.product_tmpl_id
            self.x_thong_so = tmpl.x_thong_so
            self.x_xuat_xu = tmpl.x_xuat_xu 
        else:
            self.x_thong_so = 'abc'
            self.x_xuat_xu = 'abc'
