from odoo import models, fields, api

class ProjectMaterial(models.Model):
    _name = 'project.material'
    _description = 'Vật tư dự án'

    name = fields.Char(string='Tên vật tư', required=True)
    code = fields.Char(string='Mã vật tư')
    description = fields.Text(string='Mô tả')
    tax_id = fields.Many2one('account.tax', string='Thuế VAT', domain=[('type_tax_use', '=', 'purchase')])
    unit = fields.Many2one('uom.uom', string='Đơn vị', required=True)
    category_id = fields.Many2one('material.category', string='Danh mục')
    price_unit = fields.Float(string='Đơn giá', digits=(16, 0), default=0.0)
    vendor_id = fields.Many2one(
    'res.partner',
    string='Nhà Cung Cấp',
    domain=[('supplier_rank', '>', 0)]
)
    product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm liên kết',
        readonly=True,
        ondelete='set null'
    )

    @api.model
    def create(self, vals):
        if not vals.get('code'):
            # Lấy mã danh mục từ category_id
            category = self.env['material.category'].browse(vals.get('category_id'))
            category_code = category.code if category else 'UNK'
            # Lấy số sequence
            sequence = self.env['ir.sequence'].next_by_code('project.material.code') or '000'
            # Tạo mã theo quy tắc: Mã danh mục + Số sequence
            vals['code'] = f"{category_code}{sequence}"
        vendor_id = vals.get('vendor_id')
        if vendor_id:
            vendor = self.env['res.partner'].browse(vendor_id)
            if vendor and vendor.supplier_rank == 0:
                vendor.supplier_rank = 1  
        material = super(ProjectMaterial, self).create(vals)
        material_category = self.env['product.category'].search([('name', '=', 'Vật tư')], limit=1)
        if not material_category:
            material_category = self.env['product.category'].create({'name': 'Vật tư'})
        imd = self.env['ir.model.data'].sudo()
        xml = imd.search([
            ('module', '=', 'project_material'),          # <-- đổi 'tk_project' = technical name module của bạn
            ('name', '=', 'product_category_vattu'),
        ], limit=1)
        if not xml:
            imd.create({
                'module': 'project_material',             # <-- đổi giống dòng trên
                'name': 'product_category_vattu',
                'model': 'product.category',
                'res_id': material_category.id,
                'noupdate': True,
            })
        product_vals = {
            'name': material.name,
            # 'default_code': material.code,
            'uom_id': material.unit.id,
            'uom_po_id': material.unit.id,
            'type': 'product',  # hoặc 'consu'
            'purchase_ok': True,
            'sale_ok': False,
            'categ_id': material_category.id,
            'supplier_taxes_id': [(6, 0, material.tax_id.ids)],
            'list_price': material.price_unit,   # Giá bán (nếu có)
        }
        product = self.env['product.product'].create(product_vals)

        # Link lại
        material.product_id = product.id
        return material
    def write(self, vals):
        res = super(ProjectMaterial, self).write(vals)
        for material in self:
            if material.product_id:
                product_vals = {}
                if 'name' in vals:
                    product_vals['name'] = material.name
                if 'unit' in vals:
                    product_vals['uom_id'] = material.unit.id
                    product_vals['uom_po_id'] = material.unit.id
                if 'price_unit' in vals:
                    product_vals['list_price'] = material.price_unit
                if 'tax_id' in vals:
                    product_vals['supplier_taxes_id'] = [(6, 0, material.tax_id.ids)]
                if product_vals:
                    material.product_id.write(product_vals)
        return res
    def init(self):
        """Auto-create product.category 'Vật tư' + XMLID khi module được load/install/update."""
        # self.env có sẵn ở đây
        imd = self.env['ir.model.data'].sudo()

        # Nếu đã có XMLID thì thôi (đảm bảo không tạo lặp)
        xml = imd.search([
            ('module', '=', 'project_material'),
            ('name', '=', 'product_category_vattu'),
        ], limit=1)
        if xml:
            return

        categ = self.env['product.category'].sudo().search([('name', '=', 'Vật tư')], limit=1)
        if not categ:
            categ = self.env['product.category'].sudo().create({'name': 'Vật tư'})

        imd.create({
            'module': 'project_material',
            'name': 'product_category_vattu',
            'model': 'product.category',
            'res_id': categ.id,
            'noupdate': True,
        })
