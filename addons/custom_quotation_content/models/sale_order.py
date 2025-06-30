from odoo import fields, models,api
from datetime import datetime, timedelta
from collections import defaultdict
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
    is_show_chi_phi_nhan_cong = fields.Boolean(
        string="Hiển thị chi phí nhân công",
        default=False,
    )
    is_show_ma_sp = fields.Boolean(
        string="Hiển thị mã sản phẩm",
        default=False,
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
    string="Thời hạn báo giá (ngày)",default=15,
)
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain="[('customer_rank', '>', 0)]"
    )
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
    show_contact = fields.Boolean(compute="_compute_show_contact")
    @api.depends('partner_id.company_type')
    def _compute_show_contact(self):
        for order in self:
            order.show_contact = order.partner_id.company_type == 'company'

    x_project_name = fields.Text(
        string="Dự án",
        help="Tên dự án hoặc mô tả ngắn gọn về dự án liên quan đến đơn hàng này.",
    )
    x_tax_summary = fields.Html(string="Chi tiết thuế", compute="_compute_tax_summary", sanitize=False)
# viết lại tổng giá 
    @api.depends('order_line.tax_id', 'order_line.price_total', 'amount_untaxed', 'amount_tax', 'amount_total')
    def _compute_tax_summary(self):
        for order in self:
            tax_details = defaultdict(lambda: {'base': 0.0, 'amount': 0.0})
            currency = order.currency_id

            for line in order.order_line.filtered(lambda l: not l.display_type):
                # Giá sau chiết khấu
                price_unit = (line.price_unit or 0.0) * (1 - (line.discount or 0.0) / 100.0)
                # Cộng giá nhân công
                price_unit_with_nhan_cong = price_unit + (line.x_chi_phi_nhan_cong or 0.0)

                taxes = line.tax_id.compute_all(
                    price_unit_with_nhan_cong, currency, line.product_uom_qty,
                    product=line.product_id, partner=order.partner_id
                )

                for tax in taxes['taxes']:
                    tax_details[tax['name']]['base'] += tax['base']
                    tax_details[tax['name']]['amount'] += tax['amount']

            summary_lines = [
                "<table style='width:100%; table-layout:auto; border-collapse:collapse;'>"
            ]

            # Tổng chưa thuế
            summary_lines.append(
                f"<tr><td style='font-weight:bold; white-space:nowrap; padding:4px;'>Tổng chưa thuế:</td>"
                f"<td style='text-align:right; white-space:nowrap; padding:4px;'>{currency.format(order.amount_untaxed)}</td></tr>"
            )

            # Chi tiết thuế
            for tax_name, data in tax_details.items():
                summary_lines.append(
                    f"<tr><td style='white-space:nowrap; padding:4px;'>"
                    f"<b>Thuế {tax_name} trên {currency.format(data['base'])}:</b></td>"
                    f"<td style='text-align:right; white-space:nowrap; padding:4px;'>{currency.format(data['amount'])}</td></tr>"
                )

            # Tổng cộng
            summary_lines.append(
                f"<tr><td style='font-weight:bold; white-space:nowrap; padding:4px;'>Tổng cộng:</td>"
                f"<td style='text-align:right; font-weight:bold; white-space:nowrap; padding:4px;'>{currency.format(order.amount_total)}</td></tr>"
            )

            summary_lines.append("</table>")
            order.x_tax_summary = ''.join(summary_lines)
    is_including_testing = fields.Boolean(
    string="Đã bao gồm kiểm thử",
    help ="Chọn nếu báo giá đã bao gồm chi phí kiểm thử sản phẩm hoặc dịch vụ.",
    default=False)
    x_note = fields.Text(
        string="Ghi chú")






