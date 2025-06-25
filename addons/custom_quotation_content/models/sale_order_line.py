from odoo import fields, models,api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_thongso = fields.Text(string='Thông số', related='product_id.product_tmpl_id.x_thong_so', store=True, readonly=True)
    x_xuatxu = fields.Char(string='Xuất xứ', related='product_id.product_tmpl_id.x_xuat_xu', store=True, readonly=True)
    x_hangsx = fields.Char(string='Hãng SX', related='product_id.product_tmpl_id.x_hang_sx', store=True, readonly=True)
    default_code = fields.Char(
        string='Mã SP',
        related='product_id.product_tmpl_id.default_code',
        store=True, readonly=True
    )
    x_chi_phi_nhan_cong = fields.Monetary(
        string='Chi phí nhân công (trên 1 SP)',
        currency_field='currency_id'
    )

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
