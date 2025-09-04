from odoo import fields, models

class SaleOrder(models.Model):
    _inherit = "sale.order"

    salesperson_signature = fields.Binary("Salesperson Signature")
