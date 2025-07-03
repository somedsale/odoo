from odoo import models, fields, api
from odoo.tools import format_amount

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_display_price(self, product):
        # Override phương thức để định dạng giá trị price_unit với ký hiệu ₫
        price = super(SaleOrderLine, self)._get_display_price(product)
        # Định dạng số với dấu chấm phân cách hàng nghìn và ký hiệu ₫
        return format_amount(
            self.env,
            price,
            'VND',
            decimal_precision=0,  # Không hiển thị số thập phân
            thousands_sep='.',    # Dấu phân cách hàng nghìn
            decimal_sep='',       # Không sử dụng dấu phân cách thập phân
            symbol='₫',          # Ký hiệu tiền tệ
            symbol_position='after'  # Đặt ký hiệu sau số
        )

    price_unit = fields.Float(
        string='Unit Price',
        digits=(16, 0),  # Loại bỏ số thập phân
        required=True,
        default=0.0,
        compute='_compute_price_unit',
        store=True,
        readonly=False
    )

    @api.depends('product_id', 'product_uom_qty', 'order_id.pricelist_id')
    def _compute_price_unit(self):
        # Kế thừa và giữ nguyên logic tính toán price_unit
        for line in self:
            if not line.product_id or not line.order_id.pricelist_id:
                line.price_unit = 0.0
                continue
            line.price_unit = line._get_display_price(line.product_id)