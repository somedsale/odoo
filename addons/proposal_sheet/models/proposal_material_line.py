from odoo import models, fields, api, _
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

    material_id = fields.Many2one(
        'project.material',
        string='Vật Tư',
    )

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

    stock_qty_on_hand = fields.Float(
        string="Tồn thực tế",
        compute="_compute_stock_qty",
        store=False,
    )

    stock_qty_available = fields.Float(
        string="Tồn có thể dùng",
        compute="_compute_stock_qty",
        store=False,
    )

    other_estimate_item = fields.Many2one(
        'estimate.item.other',
        string='Hạng mục khác',
    )
    cost_estimate_line_id = fields.Many2one(
    'cost.estimate.line',
    string='Hạng mục dự toán',
)
    # ========== COMPUTE ==========
    @api.depends('product_id')
    def _compute_stock_qty(self):
        Quant = self.env['stock.quant']
        Location = self.env['stock.location']

        internal_locs = Location.search([('usage', '=', 'internal')]).ids

        for line in self:
            line.stock_qty_on_hand = 0.0
            line.stock_qty_available = 0.0

            if not line.product_id or not internal_locs:
                continue

            data = Quant.read_group(
                [
                    ('product_id', '=', line.product_id.id),
                    ('location_id', 'in', internal_locs),
                ],
                ['quantity:sum', 'reserved_quantity:sum'],
                ['product_id'],
            )

            if data:
                qty = data[0]['quantity'] or 0.0
                reserved = data[0]['reserved_quantity'] or 0.0
                line.stock_qty_on_hand = qty
                line.stock_qty_available = qty - reserved

    @api.depends('price_unit', 'quantity', 'tax_id', 'product_id', 'vendor_id')
    def _compute_price_taxed(self):
        for line in self:
            if line.tax_id:
                taxes = line.tax_id.compute_all(
                    line.price_unit or 0.0,
                    line.currency_id,
                    line.quantity or 0.0,
                    product=line.product_id or None,
                    partner=line.vendor_id or None,
                )
                line.price_unit_taxed = (
                    taxes['total_included'] / line.quantity if line.quantity else 0.0
                )
                line.price_total_taxed = taxes['total_included']
            else:
                line.price_unit_taxed = line.price_unit or 0.0
                line.price_total_taxed = line.price_total or 0.0

    @api.depends('quantity', 'estimate_price_unit')
    def _compute_estimate_price_total(self):
        for line in self:
            line.estimate_price_total = (line.quantity or 0.0) * (line.estimate_price_unit or 0.0)

    @api.depends('material_id', 'sheet_id.project_id')
    def _compute_estimate_price_unit(self):
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
            line.price_total = (line.quantity or 0.0) * (line.price_unit or 0.0)

    def _get_last_purchase_line(self):
        self.ensure_one()
        PurchaseLine = self.env['purchase.order.line'].sudo()

        if not self.product_id:
            return PurchaseLine.browse()

        def _line_dt(pol):
            return pol.order_id.date_approve or pol.order_id.date_order or pol.create_date or fields.Datetime.now()

        def _pick_latest(lines):
            if not lines:
                return PurchaseLine.browse()
            return lines.sorted(
                key=lambda l: (_line_dt(l), l.id),
                reverse=True,
            )[:1]

        base_domain = [
            ('product_id', '=', self.product_id.id),
            ('order_id.state', 'in', ['purchase', 'done']),
        ]

        if self.vendor_id:
            vendor_lines = PurchaseLine.search(
                base_domain + [('order_id.partner_id', '=', self.vendor_id.id)]
            )
            latest_vendor_line = _pick_latest(vendor_lines)
            if latest_vendor_line:
                return latest_vendor_line

        all_lines = PurchaseLine.search(base_domain)
        return _pick_latest(all_lines)

    def _get_fallback_default_vendor(self):
        self.ensure_one()
        if not self.product_id:
            return False

        sellers = self.product_id.seller_ids
        if self.vendor_id:
            seller = sellers.filtered(lambda s: s.partner_id == self.vendor_id)[:1]
            if seller:
                return seller.partner_id
        return sellers[:1].partner_id if sellers[:1] else False

    def _get_fallback_default_price(self):
        self.ensure_one()
        if not self.product_id:
            return 0.0

        sellers = self.product_id.seller_ids
        if self.vendor_id:
            seller = sellers.filtered(lambda s: s.partner_id == self.vendor_id)[:1]
            if seller:
                return seller.price or 0.0

        return sellers[:1].price if sellers[:1] else 0.0

    def _get_fallback_default_tax(self):
        self.ensure_one()
        if self.material_id and getattr(self.material_id, 'tax_id', False):
            return self.material_id.tax_id

        if self.product_id and self.product_id.supplier_taxes_id:
            return self.product_id.supplier_taxes_id[:1]

        return False

    def _get_default_purchase_price(self):
        self.ensure_one()

        last_po_line = self._get_last_purchase_line()
        if last_po_line:
            return last_po_line.price_unit or 0.0

        if self.material_id and self.material_id.price_unit:
            return self.material_id.price_unit or 0.0

        return self._get_fallback_default_price()

    def _get_default_purchase_tax(self):
        self.ensure_one()

        last_po_line = self._get_last_purchase_line()
        if last_po_line and last_po_line.taxes_id:
            return last_po_line.taxes_id[:1]

        return self._get_fallback_default_tax()

    def _apply_purchase_defaults(self):
        for line in self:
            if not line.product_id and not line.material_id:
                line.unit = False
                line.price_unit = 0.0
                line.tax_id = False
                if not line.product_id:
                    line.vendor_id = False
                continue

            if line.material_id:
                if line.material_id.unit:
                    line.unit = line.material_id.unit

                product_from_material = getattr(line.material_id, 'product_id', False)
                if product_from_material and not line.product_id:
                    line.product_id = product_from_material

                if line.material_id.vendor_id and not line.vendor_id:
                    line.vendor_id = line.material_id.vendor_id

            if line.product_id and not line.unit:
                line.unit = line.product_id.uom_po_id or line.product_id.uom_id

            if line.product_id and not line.vendor_id:
                line.vendor_id = line._get_fallback_default_vendor() or False

            line.price_unit = line._get_default_purchase_price()
            line.tax_id = line._get_default_purchase_tax() or False

    @api.onchange('material_id')
    def _onchange_material_id(self):
        for line in self:
            material = line.material_id

            if not material:
                if not line.product_id:
                    line.unit = False
                    line.price_unit = 0.0
                    line.vendor_id = False
                    line.tax_id = False
                continue

            if not material.unit:
                return {
                    'warning': {
                        'title': 'Thiếu cấu hình',
                        'message': f"Vật tư '{material.name}' chưa có đơn vị được cấu hình.",
                    }
                }

            product_from_material = getattr(material, 'product_id', False)
            if product_from_material and not line.product_id:
                line.product_id = product_from_material

            if material.vendor_id and not line.vendor_id:
                line.vendor_id = material.vendor_id

            line._apply_purchase_defaults()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            product = line.product_id

            if not product:
                if not line.material_id:
                    line.unit = False
                    line.price_unit = 0.0
                    line.vendor_id = False
                    line.tax_id = False
                continue

            if not line.unit:
                line.unit = product.uom_po_id or product.uom_id

            if not line.vendor_id:
                line.vendor_id = line._get_fallback_default_vendor() or False

            line.price_unit = line._get_default_purchase_price()
            line.tax_id = line._get_default_purchase_tax() or False

    @api.onchange('vendor_id')
    def _onchange_vendor_id(self):
        for line in self:
            if line.product_id:
                line.price_unit = line._get_default_purchase_price()
                line.tax_id = line._get_default_purchase_tax() or False

    def _ensure_supplierinfo_for_product_vendor(self):
        SupplierInfo = self.env['product.supplierinfo']
        for line in self:
            product = line.product_id
            vendor = line.vendor_id
            if not product or not vendor:
                continue

            existing = SupplierInfo.search([
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ('partner_id', '=', vendor.id),
            ], limit=1)

            if existing:
                continue

            SupplierInfo.create({
                'product_tmpl_id': product.product_tmpl_id.id,
                'partner_id': vendor.id,
                'min_qty': 1.0,
                'price': line.price_unit or 0.0,
            })

    @api.model
    def create(self, vals):
        _logger.info("Creating ProposalMaterialLine with vals: %s", vals)

        if vals.get('type') != 'material':
            vals['type'] = 'material'

        if vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError("Phiếu đề xuất không tồn tại.")
            if sheet.type != 'material':
                raise ValidationError("Không thể thêm dòng vật tư vào phiếu đề xuất chi phí.")

        if vals.get('material_id'):
            material = self.env['project.material'].browse(vals['material_id'])
            if not material.exists():
                raise ValidationError("Vật tư không tồn tại.")
            if not material.unit:
                raise ValidationError(f"Vật tư '{material.name}' chưa có đơn vị được cấu hình.")

            vals.setdefault('unit', material.unit.id)

            if material.vendor_id and not vals.get('vendor_id'):
                vals['vendor_id'] = material.vendor_id.id

            product_from_material = getattr(material, 'product_id', False)
            if product_from_material and not vals.get('product_id'):
                vals['product_id'] = product_from_material.id

        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            if not product.exists():
                raise ValidationError("Sản phẩm không tồn tại.")

            vals.setdefault('unit', (product.uom_po_id or product.uom_id).id)

            if not vals.get('vendor_id') and product.seller_ids:
                first_seller = product.seller_ids[:1]
                if first_seller.partner_id:
                    vals['vendor_id'] = first_seller.partner_id.id

        record = super().create(vals)

        # Sau create: set lại theo ưu tiên giá/thuế mua gần nhất -> mặc định
        write_vals = {}
        if record.product_id:
            write_vals['price_unit'] = record._get_default_purchase_price()
            default_tax = record._get_default_purchase_tax()
            write_vals['tax_id'] = default_tax.id if default_tax else False

        if write_vals:
            record.write(write_vals)

        record._ensure_supplierinfo_for_product_vendor()
        return record

    def write(self, vals):
        _logger.info("Writing ProposalMaterialLine with vals: %s", vals)

        if 'type' in vals and vals['type'] != 'material':
            raise ValidationError("Không thể thay đổi loại của dòng vật tư.")

        if vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError("Phiếu đề xuất không tồn tại.")
            if sheet.type != 'material':
                raise ValidationError("Không thể thêm dòng vật tư vào phiếu đề xuất chi phí.")

        if vals.get('material_id'):
            material = self.env['project.material'].browse(vals['material_id'])
            if not material.exists():
                raise ValidationError("Vật tư không tồn tại.")
            if not material.unit:
                raise ValidationError(f"Vật tư '{material.name}' chưa có đơn vị được cấu hình.")

            vals.setdefault('unit', material.unit.id)

            if material.vendor_id and not vals.get('vendor_id'):
                vals['vendor_id'] = material.vendor_id.id

            product_from_material = getattr(material, 'product_id', False)
            if product_from_material and not vals.get('product_id'):
                vals['product_id'] = product_from_material.id

        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            if not product.exists():
                raise ValidationError("Sản phẩm không tồn tại.")

            vals.setdefault('unit', (product.uom_po_id or product.uom_id).id)

            if not vals.get('vendor_id') and product.seller_ids:
                first_seller = product.seller_ids[:1]
                if first_seller.partner_id:
                    vals['vendor_id'] = first_seller.partner_id.id

        res = super().write(vals)

        # Nếu thay product/material/vendor mà user KHÔNG truyền giá/thuế tay
        trigger_fields = {'product_id', 'material_id', 'vendor_id'}
        if trigger_fields.intersection(vals.keys()):
            for rec in self:
                extra_vals = {}
                if 'price_unit' not in vals:
                    extra_vals['price_unit'] = rec._get_default_purchase_price()
                if 'tax_id' not in vals:
                    default_tax = rec._get_default_purchase_tax()
                    extra_vals['tax_id'] = default_tax.id if default_tax else False
                if extra_vals:
                    super(ProposalMaterialLine, rec).write(extra_vals)

        self._ensure_supplierinfo_for_product_vendor()
        return res

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