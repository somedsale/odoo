# custom_sale_order_type/models/sale_order.py
from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = "sale.order"

    customer_type = fields.Selection(
        [
            ("online", "Online"),
            ("direct", "Trực tiếp"),
        ],
        string="Loại khách hàng",
        default="online",
        tracking=True,
        copy=True,
    )