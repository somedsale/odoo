from odoo import fields, models
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_including_transport = fields.Boolean(
    string="Đã bao gồm vận chuyển",
    default=False
)
    is_including_installation = fields.Boolean(
    string="Đã bao gồm lắp đặt",
    default=False
)
    x_estimated_delivery_time_id = fields.Many2one(
        'estimated.delivery.time', 
        string="Estimated Delivery Time"
    )
    x_warranty_duration_id = fields.Many2one(
        'warranty.duration',
        string="Warranty Duration"
    )
    x_custom_payment_terms = fields.Text(
    string="Điều khoản thanh toán tùy chỉnh",
    default="hehehehe")

    x_delivery_location = fields.Text(
        string="Địa điểm giao hàng"
    )





