from odoo import fields, models,api
from datetime import datetime, timedelta
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
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain="[('customer_rank', '>', 0)]"
    )
    @api.depends('order_line.price_subtotal', 'order_line.price_tax')
    def _amount_all(self):
        for order in self:
            amount_untaxed = sum(line.price_subtotal for line in order.order_line)
            amount_tax = sum(line.price_tax for line in order.order_line)
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })
    @api.onchange('x_quote_valid_until', 'date_order')
    def _onchange_quote_valid_until(self):
        for order in self:
            if order.x_quote_valid_until and order.date_order:
                order.validity_date = fields.Date.to_string(
                    fields.Date.from_string(order.date_order) + timedelta(days=order.x_quote_valid_until)
                )
    @api.model
    def create(self, vals):
        if vals.get('x_quote_valid_until') and vals.get('date_order'):
            vals['validity_date'] = fields.Datetime.to_datetime(vals['date_order']) + timedelta(
                days=vals['x_quote_valid_until'])
        return super().create(vals)

    def write(self, vals):
        if 'x_quote_valid_until' in vals or 'date_order' in vals:
            x_quote_valid_until = vals.get('x_quote_valid_until', self.x_quote_valid_until)
            date_order = fields.Datetime.to_datetime(vals.get('date_order', self.date_order))
            vals['validity_date'] = date_order + timedelta(days=x_quote_valid_until)
        return super().write(vals)
    
    partner_contact_id = fields.Many2one(
        'res.partner',
        string='Người đại diện',
        domain="[('id', 'child_of', partner_id), ('id', '!=', partner_id)]",
        help='Người đại diện hoặc liên hệ con của khách hàng.'
        
    )

    @api.onchange('partner_id')
    def _onchange_partner_clear_contact(self):
        self.partner_contact_id = False
    partner_contact_phone = fields.Char(
        string="SĐT Người đại diện",
        compute="_compute_partner_contact_phone",
    )
   
    @api.depends('partner_contact_id')
    def _compute_partner_contact_phone(self):
        for order in self:
            phone = order.partner_contact_id.phone or order.partner_contact_id.mobile
            order.partner_contact_phone = phone or ''






