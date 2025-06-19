from odoo import fields, models # type: ignore

class SaleOrder(models.Model):
    _inherit = 'sale.order'  # Kế thừa model sale.order

    custom_reference = fields.Char(string='Custom Reference', help='A custom reference for this quotation')