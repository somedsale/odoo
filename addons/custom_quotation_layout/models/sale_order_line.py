from odoo import models, fields, api
from odoo.tools import format_amount

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    formatted_price = fields.Char(string='Formatted Price', compute='_compute_formatted_price')

    @api.depends('price_unit')
    def _compute_formatted_price(self):
        for record in self:
            # Định dạng giá trị thành chuỗi, ví dụ: 563.000 đ
            record.formatted_price = '{:,.0f} đ'.format(record.price_unit).replace(',', '.')