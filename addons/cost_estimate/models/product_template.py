from odoo import models
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def name_get(self):
        result = []
        for record in self:
            # Lấy default_code từ product.product đầu tiên
            default_code = record.default_code or ''
            if self.env.context.get('no_default_code'):
                name = record.name
            else:
                name = f"[{default_code}] {record.name}" if default_code else record.name
            result.append((record.id, name))
        return result