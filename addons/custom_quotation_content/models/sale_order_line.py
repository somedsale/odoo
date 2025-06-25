from odoo import fields, models,api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    is_manual_price = fields.Boolean(string='Tự nhập giá', default=False)
    x_thongso = fields.Text(string='Thông số')  # ✅ Không related để cho phép chỉnh sửa
    x_xuatxu = fields.Char(string='Xuất xứ')
    x_hangsx = fields.Char(string='Hãng SX')
    default_code = fields.Char(
        string='MSP'
    )
    x_chi_phi_nhan_cong = fields.Monetary(
        string='Chi phí nhân công (trên 1 SP)',
        currency_field='currency_id'
    )
    @api.onchange('product_id')
    def _onchange_product_custom_fields(self):
        if self.product_id:
            tmpl = self.product_id.product_tmpl_id
            self.x_thongso = tmpl.x_thong_so
            self.x_xuatxu = tmpl.x_xuat_xu
            self.x_hangsx = tmpl.x_hang_sx
            self.default_code = tmpl.default_code

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'x_chi_phi_nhan_cong')
    def _compute_amount(self):
        for line in self:
            # Giá sau giảm giá
            price_unit_discounted = line.price_unit * (1 - (line.discount or 0.0) / 100.0)

            # Tính thuế phần sản phẩm
            taxes = line.tax_id.compute_all(
                price_unit_discounted,
                line.currency_id,
                line.product_uom_qty,
                product=line.product_id,
                partner=line.order_id.partner_shipping_id
            )

            # Chi phí nhân công
            nhan_cong = (line.x_chi_phi_nhan_cong or 0.0) * line.product_uom_qty

            # Tổng chưa thuế = sản phẩm + nhân công
            subtotal = taxes['total_excluded'] + nhan_cong
            total = taxes['total_included'] + nhan_cong

            line.update({
                'price_tax': total - subtotal,
                'price_subtotal': subtotal,
                'price_total': total,
            })
    @api.onchange('price_unit')
    def _onchange_price_unit_flag(self):
        """Nếu người dùng sửa giá -> đánh dấu là đã sửa tay"""
        if self.price_unit:
            self.is_manual_price = True
    # @api.onchange('product_id', 'product_uom', 'product_uom_qty', 'order_id.partner_id')

    @api.onchange('product_id', 'order_id.partner_id')
    def _onchange_product_custom(self):
        if not self.is_manual_price and self.product_id:
            # Chỉ cập nhật giá nếu không phải giá nhập tay
            self.price_unit = self._get_display_price() or 0.0

    def product_id_change(self):
        """Override để giữ giá nhập tay khi thay đổi sản phẩm hoặc số lượng"""
        res = super(SaleOrderLine, self).product_id_change()
        if self.is_manual_price:
            # Giữ nguyên giá nhập tay
            res['value']['price_unit'] = self.price_unit
        return res
