from odoo import fields, models,api
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
        string="Thời gian giao hàng dự tính"
    )
    x_warranty_duration_id = fields.Many2one(
        'warranty.duration',
        string="Thời gian bảo hành"
    )
    x_custom_payment_terms = fields.Text(
    string="Điều khoản thanh toán tùy chỉnh",
    default="+ Tạm ứng 50% ngay sau khi xác nhận đặt hàng\n"
            "+ Thanh toán tới 70% sau khi nghiệm thu vật tư đầu vào\n"
            "+ Thanh toán đủ 100% sau khi nghiệm thu hoàn thành lắp đặt."
)

    x_delivery_location = fields.Text(
        string="Địa điểm giao hàng"
    )
    x_payment_method_id = fields.Many2one(
        comodel_name='payment.method',
        string='Phương thức thanh toán'
    )
    x_quote_valid_until = fields.Integer(
    string="Thời hạn báo giá (ngày)"
)






