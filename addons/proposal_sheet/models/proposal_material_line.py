from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProposalMaterialLine(models.Model):
    _name = 'proposal.material.line'
    _description = 'Chi Tiết Vật Tư'
    _inherit = ['mail.thread']

    active = fields.Boolean(string='Active', default=True)

    sheet_id = fields.Many2one(
        'proposal.sheet',
        string='Phiếu Đề Xuất',
        required=True,
        ondelete='cascade',
    )

    # Vật tư gốc (đang dùng)
    material_id = fields.Many2one(
        'project.material',
        string='Vật Tư',
    )

    # Thêm sản phẩm để link qua product.product, dùng cho PO/stock...
    product_id = fields.Many2one(
        'product.product',
        string='Sản Phẩm',
        tracking=True,
    )

    quantity = fields.Float(
        string='Số Lượng',
        default=1.0,
        digits=(16, 4),
    )
    unit = fields.Many2one(
        'uom.uom',
        string='Đơn Vị',
        required=True,
    )
    price_unit = fields.Float(
        string='Đơn Giá',
        digits='Product Price',
    )
    price_total = fields.Float(
        string='Thành tiền',
        compute='_compute_price_total',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    vendor_id = fields.Many2one(
        'res.partner',
        string='Nhà Cung Cấp Đề Xuất',
        domain=[('supplier_rank', '>', 0)],
    )

    estimate_price_unit = fields.Float(
        string='Giá Dự Toán',
        compute='_compute_estimate_price_unit',
        store=False,
        readonly=True,
    )
    estimate_price_total = fields.Float(
        string='Giá Dự Toán',
        compute='_compute_estimate_price_total',
        store=False,
        readonly=True,
    )

    description = fields.Text(string='Ghi Chú')

    type = fields.Selection(
        [('material', 'Vật Tư')],
        default='material',
        required=True,
        readonly=True,
    )

    tax_id = fields.Many2one(
        'account.tax',
        string='Thuế áp dụng',
        compute='_compute_tax_material',
        inverse='_inverse_tax_material',
        store=True,
        readonly=False,
        domain="[('type_tax_use', '=', 'purchase')]",
    )
    price_unit_taxed = fields.Float(
        string='Đơn giá (sau thuế)',
        compute='_compute_price_taxed',
        store=True,
    )
    price_total_taxed = fields.Float(
        string='Thành tiền (sau thuế)',
        compute='_compute_price_taxed',
        store=True,
    )
    # ========== COMPUTE ==========


    @api.depends('material_id', 'product_id')
    def _compute_tax_material(self):
        """
        Ưu tiên:
        - Nếu material_id có tax_id -> dùng thuế này
        - Nếu không, mà product_id có supplier_taxes_id -> dùng thuế đó
        """
        for line in self:
            tax = False
            if line.material_id and getattr(line.material_id, 'tax_id', False):
                tax = line.material_id.tax_id
            elif line.product_id and line.product_id.supplier_taxes_id:
                tax = line.product_id.supplier_taxes_id[:1]
            line.tax_id = tax
    def _inverse_tax_material(self):
        """Cho phép người dùng chỉnh tay tax_id.
        Không cần làm gì nếu bạn chỉ lưu thẳng vào cột của chính field này."""
        # pass là cũng được, vì Many2one này có cột thật trong DB
        pass

    @api.depends('price_unit', 'quantity', 'tax_id')
    def _compute_price_taxed(self):
        for line in self:
            if line.tax_id:
                taxes = line.tax_id.compute_all(
                    line.price_unit,
                    line.currency_id,
                    line.quantity,
                    product=line.product_id or None,
                    partner=line.vendor_id,
                )
                line.price_unit_taxed = (
                    taxes['total_included'] / line.quantity if line.quantity else 0.0
                )
                line.price_total_taxed = taxes['total_included']
            else:
                line.price_unit_taxed = line.price_unit
                line.price_total_taxed = line.price_total

    @api.depends('quantity', 'estimate_price_unit')
    def _compute_estimate_price_total(self):
        for line in self:
            line.estimate_price_total = line.quantity * line.estimate_price_unit

    @api.depends('material_id', 'sheet_id.project_id')
    def _compute_estimate_price_unit(self):
        """
        Giữ nguyên logic cũ:
        Lấy giá dự toán theo material_id + project.
        """
        CostEstimateLine = self.env['cost.estimate.line']
        for line in self:
            estimate_price = 0.0
            if line.material_id and line.sheet_id and line.sheet_id.project_id:
                estimate_lines = CostEstimateLine.search([
                    ('project_id', '=', line.sheet_id.project_id.id),
                ])
                matched_line = None
                for est_line in estimate_lines:
                    matched_line = est_line.material_line_ids.filtered(
                        lambda m: m.material_id.id == line.material_id.id
                    )
                    if matched_line:
                        break
                if matched_line:
                    estimate_price = matched_line[0].price_unit or 0.0
            line.estimate_price_unit = estimate_price

    @api.depends('quantity', 'price_unit')
    def _compute_price_total(self):
        for line in self:
            line.price_total = line.quantity * line.price_unit

    # ========== ONCHANGE ==========

    @api.onchange('material_id')
    def _onchange_material_id(self):
        for line in self:
            material = line.material_id

            # Nếu xóa vật tư → reset hết (nhưng vẫn để material_id rỗng thôi)
            if not material:
                line.unit = False
                line.price_unit = 0.0
                line.vendor_id = False
                return

            # Kiểm tra đã cấu hình đơn vị chưa
            if not material.unit:
                return {
                    'warning': {
                        'title': 'Thiếu cấu hình',
                        'message': f"Vật tư '{material.name}' chưa có đơn vị được cấu hình.",
                    }
                }

            # Gán từ material
            line.unit = material.unit
            line.price_unit = material.price_unit
            line.vendor_id = material.vendor_id

            # Nếu project.material có product_id thì map sang
            product_from_material = getattr(material, 'product_id', False)
            if product_from_material and not line.product_id:
                line.product_id = product_from_material

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """
        Khi chọn product_id:
        - Tự điền đơn vị (uom_po_id / uom_id)
        - Tự điền vendor & price từ seller đầu tiên nếu chưa nhập
        """
        for line in self:
            product = line.product_id

            # Nếu xóa sản phẩm → reset (trừ khi bạn muốn giữ lại gì đó)
            if not product:
                # Nếu không có material_id thì reset sạch
                if not line.material_id:
                    line.unit = False
                    line.price_unit = 0.0
                    line.vendor_id = False
                return

            # Đơn vị: ưu tiên uom_po_id, không có thì dùng uom_id
            if not line.unit:
                line.unit = product.uom_po_id or product.uom_id

            # Vendor & giá: lấy từ seller đầu tiên nếu có
            seller = product.seller_ids[:1]
            if seller:
                
                    line.vendor_id = seller.partner_id or False
                
                    line.price_unit = seller.price or 0.0
            else:
                    line.vendor_id = False
                    # fallback: lấy list_price (báo giá)
                    line.price_unit = product.lst_price or 0.0

    # ========== CRUD OVERRIDE ==========

    def _ensure_supplierinfo_for_product_vendor(self):
        """
        Nếu có product_id + vendor_id mà chưa có supplierinfo tương ứng
        → tự tạo product.supplierinfo (seller) cho product đó.
        """
        SupplierInfo = self.env['product.supplierinfo']
        for line in self:
            product = line.product_id
            vendor = line.vendor_id
            if not product or not vendor:
                continue

            # Tìm supplierinfo cùng product template + vendor
            existing = SupplierInfo.search([
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ('partner_id', '=', vendor.id),
            ], limit=1)

            if existing:
                # Không tạo trùng, có thể thêm logic cập nhật giá nếu muốn
                continue

            SupplierInfo.create({
                'product_tmpl_id': product.product_tmpl_id.id,
                'partner_id': vendor.id,
                'min_qty': 1.0,
                'price': line.price_unit or 0.0,
            })

    # ========== CRUD OVERRIDE ==========

    @api.model
    def create(self, vals):
        _logger.info("Creating ProposalMaterialLine with vals: %s", vals)

        # Đảm bảo type luôn = 'material'
        if vals.get('type') != 'material':
            vals['type'] = 'material'

        # Check sheet
        if vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError("Phiếu đề xuất không tồn tại.")
            if sheet.type != 'material':
                raise ValidationError("Không thể thêm dòng vật tư vào phiếu đề xuất chi phí.")

        # Logic từ material_id (giữ nguyên như cũ)
        if vals.get('material_id'):
            material = self.env['project.material'].browse(vals['material_id'])
            if not material.exists():
                raise ValidationError("Vật tư không tồn tại.")
            if not material.unit:
                raise ValidationError(f"Vật tư '{material.name}' chưa có đơn vị được cấu hình.")

            vals.setdefault('unit', material.unit.id)
            vals.setdefault('price_unit', material.price_unit or 0.0)
            if material.vendor_id and not vals.get('vendor_id'):
                vals['vendor_id'] = material.vendor_id.id

            # Nếu có field product_id trên project.material → map sang nếu chưa set
            product_from_material = getattr(material, 'product_id', False)
            if product_from_material and not vals.get('product_id'):
                vals['product_id'] = product_from_material.id

        # Thêm logic từ product_id (nếu có / dùng riêng)
        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            if not product.exists():
                raise ValidationError("Sản phẩm không tồn tại.")

            vals.setdefault('unit', (product.uom_po_id or product.uom_id).id)

            if not vals.get('price_unit'):
                seller = product.seller_ids[:1]
                if seller and seller.price:
                    vals['price_unit'] = seller.price
                    if not vals.get('vendor_id') and seller.partner_id:
                        vals['vendor_id'] = seller.partner_id.id
                else:
                    vals['price_unit'] = product.lst_price or 0.0

            if not vals.get('vendor_id') and product.seller_ids:
                first_seller = product.seller_ids[:1]
                if first_seller.partner_id:
                    vals['vendor_id'] = first_seller.partner_id.id

        # Tạo dòng
        record = super().create(vals)

        # Sau khi có product_id + vendor_id cuối cùng → đảm bảo có supplierinfo
        record._ensure_supplierinfo_for_product_vendor()

        return record

    def write(self, vals):
        _logger.info("Writing ProposalMaterialLine with vals: %s", vals)

        # Không cho đổi type
        if 'type' in vals and vals['type'] != 'material':
            raise ValidationError("Không thể thay đổi loại của dòng vật tư.")

        # Check sheet khi đổi sheet_id
        if vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError("Phiếu đề xuất không tồn tại.")
            if sheet.type != 'material':
                raise ValidationError("Không thể thêm dòng vật tư vào phiếu đề xuất chi phí.")

        # Nếu đổi material_id
        if vals.get('material_id'):
            material = self.env['project.material'].browse(vals['material_id'])
            if not material.exists():
                raise ValidationError("Vật tư không tồn tại.")
            if not material.unit:
                raise ValidationError(f"Vật tư '{material.name}' chưa có đơn vị được cấu hình.")

            vals.setdefault('unit', material.unit.id)
            vals.setdefault('price_unit', material.price_unit or 0.0)
            if material.vendor_id and not vals.get('vendor_id'):
                vals['vendor_id'] = material.vendor_id.id

            product_from_material = getattr(material, 'product_id', False)
            if product_from_material and not vals.get('product_id'):
                vals['product_id'] = product_from_material.id

        # Nếu đổi product_id
        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            if not product.exists():
                raise ValidationError("Sản phẩm không tồn tại.")

            vals.setdefault('unit', (product.uom_po_id or product.uom_id).id)

            if not vals.get('price_unit'):
                seller = product.seller_ids[:1]
                if seller and seller.price:
                    vals['price_unit'] = seller.price
                    if not vals.get('vendor_id') and seller.partner_id:
                        vals['vendor_id'] = seller.partner_id.id
                else:
                    vals['price_unit'] = product.lst_price or 0.0

            if not vals.get('vendor_id') and product.seller_ids:
                first_seller = product.seller_ids[:1]
                if first_seller.partner_id:
                    vals['vendor_id'] = first_seller.partner_id.id

        res = super().write(vals)

        # Sau khi ghi xong, đảm bảo supplierinfo tồn tại
        self._ensure_supplierinfo_for_product_vendor()

        return res

    # ========== CONSTRAINTS & ACTIONS ==========

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError("Số lượng vật tư phải lớn hơn 0.")

    def archive(self):
        self.write({'active': False})
        self.message_post(body='Dòng vật tư đã được lưu trữ.')

    def unarchive(self):
        self.write({'active': True})
        self.message_post(body='Dòng vật tư đã được khôi phục.')
