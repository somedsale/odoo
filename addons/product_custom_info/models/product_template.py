from odoo import models, fields, api
import re
def get_initials(text, count=2):
    words = re.findall(r'\b\w', text.upper())
    return ''.join(words)[:count] if words else ''
class ProductTemplate(models.Model):
    _inherit = 'product.template'
   
    x_thong_so = fields.Text(string="Thông số")
    x_xuat_xu = fields.Char(string="Xuất xứ")
    x_hang_sx = fields.Char(string="Hãng SX")

    @api.model
    def create(self, vals):
        if not vals.get('default_code') and vals.get('name'):
            # Lấy mã 2 ký tự đầu danh mục
            category_code = ''
            if vals.get('categ_id'):
                category = self.env['product.category'].browse(vals['categ_id'])
                category_code = get_initials(category.name, 2)

            # Lấy mã 2 ký tự đầu tên sản phẩm
            product_code = get_initials(vals['name'], 2)

            prefix = f"{category_code}{product_code}"

            # Kiểm tra mã đã có chưa, tìm số lớn nhất
            existing_codes = self.env['product.template'].search([
                ('default_code', 'like', f"{prefix}%")
            ])
            max_index = 0
            for prod in existing_codes:
                match = re.match(rf'^{prefix}(\d+)$', prod.default_code or '')
                if match:
                    num = int(match.group(1))
                    max_index = max(max_index, num)

            # Tạo mã mới
            next_index = max_index + 1
            vals['default_code'] = f"{prefix}{next_index:03d}"

        return super().create(vals)
