from odoo import models, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_products_from_context(self):
        products = self
        if not products:
            active_ids = self.env.context.get("active_ids", [])
            products = self.browse(active_ids)
        if not products:
            raise UserError(_("Vui lòng chọn ít nhất một sản phẩm."))
        return products

    def _force_update_product_type(self, target_type):
        products = self._get_products_from_context()
        ids = tuple(products.ids)
        if not ids:
            raise UserError(_("Không có sản phẩm hợp lệ để cập nhật."))

        # Odoo cũ / custom thường dùng type
        if "type" in self._fields:
            self.env.cr.execute("""
                UPDATE product_template
                   SET type = %s
                 WHERE id IN %s
            """, [target_type, ids])

        # Odoo 17 thường có detailed_type
        if "detailed_type" in self._fields:
            self.env.cr.execute("""
                UPDATE product_template
                   SET detailed_type = %s
                 WHERE id IN %s
            """, [target_type, ids])

        # Một số bản có field phụ để đánh dấu storable
        if "is_storable" in self._fields:
            self.env.cr.execute("""
                UPDATE product_template
                   SET is_storable = %s
                 WHERE id IN %s
            """, [target_type == "product", ids])

        self.env.invalidate_all()
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_force_convert_to_storable(self):
        return self._force_update_product_type("product")

    def action_force_convert_to_consumable(self):
        return self._force_update_product_type("consu")