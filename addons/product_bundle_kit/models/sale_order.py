from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_bundle_parent = fields.Boolean("Là sản phẩm cha?", default=False)
    parent_bundle_id = fields.Many2one("sale.order.line", string="Thuộc dòng cha")

    @api.onchange("product_id")
    def _onchange_product_id_bundle(self):
        if not self.product_id:
            return

        bundle = self.env["product.bundle"].search([("product_id", "=", self.product_id.id)], limit=1)
        if not bundle:
            return

        self.is_bundle_parent = True

        order = self.order_id
        for line in bundle.line_ids:
            order.order_line.create({
                "order_id": order.id,
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity,
                "price_unit": line.product_id.lst_price,
                "parent_bundle_id": self.id,
                "name": f"   ↳ {line.product_id.display_name}",
            })
