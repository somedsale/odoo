from odoo import fields, models,api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    x_thongso = fields.Text(string='Thông số')  # ✅ Không related để cho phép chỉnh sửa
    x_xuatxu = fields.Char(string='Xuất xứ')
    x_hangsx = fields.Char(string='Hãng SX')
    default_code = fields.Char(
        string='MSP'
    )
    x_chi_phi_nhan_cong = fields.Monetary(string="Chi phí nhân công",currency_field='currency_id')
    @api.onchange('product_id')
    def _onchange_product_custom_fields(self):
        if self.product_id:
            tmpl = self.product_id.product_tmpl_id
            self.x_thongso = tmpl.x_thong_so
            self.x_xuatxu = tmpl.x_xuat_xu
            self.x_hangsx = tmpl.x_hang_sx
            self.default_code = tmpl.default_code
            self.x_chi_phi_nhan_cong = tmpl.x_gia_nhan_cong
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'x_chi_phi_nhan_cong')
    def _compute_amount(self):
        for line in self:
            # Giá sản phẩm đã trừ chiết khấu
            price_unit_discounted = (line.price_unit or 0.0) * (1 - (line.discount or 0.0) / 100.0)

            # Tính thuế dựa trên giá sản phẩm
            taxes = line.tax_id.compute_all(
                price_unit_discounted+line.x_chi_phi_nhan_cong,
                currency=line.currency_id,
                quantity=line.product_uom_qty,
                product=line.product_id,
                partner=line.order_id.partner_shipping_id
            )

            price_subtotal = taxes['total_excluded']
            price_tax = taxes['total_included'] - taxes['total_excluded']
            price_total = price_subtotal + price_tax

            line.update({
                'price_subtotal': price_subtotal,
                'price_tax': price_tax,
                'price_total': price_total,
            })
