from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = "product.product"

    spec_description = fields.Text(
        string="Thông số",
        compute="_compute_spec_description",
        inverse="_inverse_spec_description",
        store=True,
        help="Tên sản phẩm + các cặp thuộc tính + x_thong_so của template."
    )

    @api.depends(
        'name',
        'product_tmpl_id.name',
        'product_tmpl_id.x_thong_so',
        'product_template_attribute_value_ids',
    )
    def _compute_spec_description(self):
        for product in self:
            lines = []

            # 1) Tên sản phẩm
            name = product.name or product.product_tmpl_id.name or ""
            if name:
                lines.append(name)

            # 2) Các dòng thuộc tính: "- Màu: Xanh"
            for ptav in product.product_template_attribute_value_ids:
                attr_name = ptav.attribute_id.name or ""
                value_name = ptav.name or (
                    ptav.product_attribute_value_id
                    and ptav.product_attribute_value_id.name
                ) or ""
                if attr_name and value_name:
                    lines.append(f"- {attr_name}: {value_name}")
                elif value_name:
                    lines.append(f"- {value_name}")

            # 3) Dòng / đoạn x_thong_so ở dưới cùng
            base_spec = (product.product_tmpl_id.x_thong_so or "").strip()
            if base_spec:
                lines.append(base_spec)

            product.spec_description = "\n".join(lines)

    def _inverse_spec_description(self):
        """
        Cho phép user sửa phần THÔNG SỐ (x_thong_so) trực tiếp trong spec_description.

        Quy ước:
        - Dòng 1: tên sản phẩm  -> bỏ qua, không ghi ngược
        - Các dòng bắt đầu bằng '- ' -> thuộc tính -> bỏ qua
        - Các dòng còn lại phía dưới -> ghép lại thành x_thong_so
        """
        for product in self:
            text = (product.spec_description or "").splitlines()
            if not text:
                # Nếu user xóa hết -> x_thong_so rỗng
                product.product_tmpl_id.x_thong_so = False
                continue

            # Bỏ dòng 1 (tên sản phẩm)
            remaining = text[1:]

            # Bỏ các dòng thuộc tính (bắt đầu bằng "- ")
            info_lines = [line for line in remaining if not line.lstrip().startswith("- ")]

            # Phần còn lại -> x_thong_so
            new_base_spec = "\n".join(info_lines).strip()

            product.product_tmpl_id.x_thong_so = new_base_spec
