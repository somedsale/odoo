# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup


class ProposalSheet(models.Model):
    _inherit = 'proposal.sheet'

    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )

    type = fields.Selection(
        selection_add=[
            ('commercial_purchase', 'Mua hàng thương mại'),
        ],
        ondelete={'commercial_purchase': 'set default'},
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Đơn bán',
        related='project_id.sale_order_id',
        store=True,
        readonly=True,
    )

    sale_order_product_ids = fields.Many2many(
        'product.product',
        'proposal_sheet_sale_order_product_rel',
        'sheet_id',
        'product_id',
        string='Sản phẩm trong đơn bán',
        compute='_compute_sale_order_product_ids',
        store=False,
    )

    commercial_material_line_ids = fields.One2many(
        'proposal.material.line',
        'sheet_id',
        string='Chi tiết mua hàng thương mại',
        domain=[('type', '=', 'commercial_purchase')],
        copy=True,
    )

    @api.depends(
        'project_id',
        'project_id.sale_order_id',
        'project_id.sale_order_id.order_line',
        'project_id.sale_order_id.order_line.product_id',
    )
    def _compute_sale_order_product_ids(self):
        Product = self.env['product.product']
        for rec in self:
            products = Product.browse()
            if rec.project_id and rec.project_id.sale_order_id:
                products = rec.project_id.sale_order_id.order_line.filtered(
                    lambda l: not l.display_type and l.product_id
                ).mapped('product_id')
            rec.sale_order_product_ids = products

    @api.onchange('project_id')
    def _onchange_project_id(self):
        res = {}
        try:
            res = super()._onchange_project_id() or {}
        except AttributeError:
            res = {}

        if self.type == 'commercial_purchase' and self.commercial_material_line_ids:
            self.commercial_material_line_ids = [(5, 0, 0)]

        domain = res.get('domain', {})
        domain.update({
            'task_id': [('project_id', '=', self.project_id.id)] if self.project_id else [],
        })
        res['domain'] = domain

        if self.type == 'commercial_purchase' and self.project_id and not self.sale_order_id:
            res.setdefault('warning', {
                'title': _('Dự án chưa có đơn bán'),
                'message': _('Dự án này chưa liên kết với Đơn bán nên chưa có danh sách hàng hóa để chọn.'),
            })

        return res

    @api.onchange('type')
    def _onchange_type_commercial_purchase(self):
        for rec in self:
            if rec.type != 'commercial_purchase' and rec.commercial_material_line_ids:
                rec.commercial_material_line_ids = [(5, 0, 0)]

    @api.depends(
        'type',
        'material_line_ids.price_total',
        'commercial_material_line_ids.price_total',
        'expense_line_ids.price_total',
        'expense_noproject_line_ids.amount',
    )
    def _compute_amount_total(self):
        for sheet in self:
            if sheet.type == 'material':
                sheet.amount_total = sum(sheet.material_line_ids.mapped('price_total'))
            elif sheet.type == 'commercial_purchase':
                sheet.amount_total = sum(sheet.commercial_material_line_ids.mapped('price_total'))
            elif sheet.type == 'expense':
                sheet.amount_total = sum(sheet.expense_line_ids.mapped('price_total'))
            elif sheet.type == 'other':
                sheet.amount_total = sum(sheet.expense_noproject_line_ids.mapped('amount'))
            else:
                sheet.amount_total = 0.0

    @api.depends(
        'type',
        'material_line_ids.price_total_taxed',
        'commercial_material_line_ids.price_total_taxed',
        'expense_line_ids.price_unit',
        'expense_noproject_line_ids.amount_total',
        'expense_noproject_line_ids.amount_tax',
    )
    def _compute_amount_total_taxes(self):
        for sheet in self:
            if sheet.type == 'material':
                sheet.amount_total_taxes = sum(sheet.material_line_ids.mapped('price_total_taxed'))
            elif sheet.type == 'commercial_purchase':
                sheet.amount_total_taxes = sum(sheet.commercial_material_line_ids.mapped('price_total_taxed'))
            elif sheet.type == 'other':
                sheet.amount_total_taxes = sum(sheet.expense_noproject_line_ids.mapped('amount_total'))
            else:
                sheet.amount_total_taxes = sheet.amount_total or 0.0

    @api.model
    def create(self, vals):
        if not vals.get('type') and vals.get('commercial_material_line_ids'):
            vals['type'] = 'commercial_purchase'
        return super().create(vals)

    def write(self, vals):
        for rec in self:
            if 'type' in vals and vals['type'] != rec.type:
                if rec.commercial_material_line_ids:
                    raise ValidationError(
                        _("Không thể thay đổi loại đề xuất khi đã có dòng mua hàng thương mại.")
                    )
        return super().write(vals)

    def _get_stock_check_lines(self):
        self.ensure_one()
        if self.type == 'commercial_purchase':
            return self.commercial_material_line_ids
        return self.material_line_ids

    def _compute_show_buttons(self):
        super()._compute_show_buttons()

        current_user = self.env.user
        for rec in self:
            if rec.type == 'commercial_purchase':
                is_creator = rec.requested_by.id == current_user.id
                stock_check_lines = rec._get_stock_check_lines()
                has_stock_diff = any(bool(line.count_diff_qty) for line in stock_check_lines)

                rec.show_button_apply_actual_stock = (
                    rec.state == 'draft'
                    and is_creator
                    and not rec.stock_check_done
                    and has_stock_diff
                )

                rec.show_button_reset_stock_check = (
                    rec.state == 'draft'
                    and is_creator
                    and rec.stock_check_done
                )

    def _check_can_apply_actual_stock(self):
        self.ensure_one()

        if self.type not in ('material', 'commercial_purchase'):
            raise UserError(_("Chỉ phiếu vật tư hoặc mua hàng thương mại mới được xác nhận tồn thực tế."))

        if self.state != 'draft':
            raise UserError(_("Chỉ được xác nhận tồn thực tế khi phiếu đang ở trạng thái nháp."))

        if self.requested_by.id != self.env.user.id:
            raise UserError(_("Chỉ người đề xuất mới được xác nhận tồn thực tế."))

        if not self.stock_location_id:
            raise UserError(_("Vui lòng chọn vị trí kho kiểm kê trước khi xác nhận tồn thực tế."))

        lines = self._get_stock_check_lines()
        if not lines:
            raise UserError(_("Phiếu chưa có dòng hàng để xác nhận tồn thực tế."))

    def action_apply_actual_stock(self):
        for rec in self:
            rec._check_can_apply_actual_stock()

            log_items = []
            lines = rec._get_stock_check_lines()

            for line in lines:
                if not line.product_id:
                    raise UserError(_("Có dòng chưa có sản phẩm nên không thể cập nhật tồn."))

                if line.actual_count_qty < 0:
                    raise UserError(
                        _("Số lượng kiểm kê thực tế của sản phẩm '%s' không được âm.")
                        % line.product_id.display_name
                    )

                target_qty = line.actual_count_qty or 0.0

                quant = self.env['stock.quant'].sudo().search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', rec.stock_location_id.id),
                    ('company_id', '=', rec.env.company.id),
                    ('lot_id', '=', False),
                    ('package_id', '=', False),
                    ('owner_id', '=', False),
                ], limit=1)

                old_qty = quant.quantity if quant else 0.0

                if not quant:
                    quant = self.env['stock.quant'].sudo().create({
                        'product_id': line.product_id.id,
                        'location_id': rec.stock_location_id.id,
                        'company_id': rec.env.company.id,
                    })

                if 'inventory_quantity' in quant._fields:
                    quant.sudo().write({
                        'inventory_quantity': target_qty,
                    })
                elif 'inventory_diff_quantity' in quant._fields:
                    quant.sudo().write({
                        'inventory_diff_quantity': target_qty - (quant.quantity or 0.0),
                    })
                else:
                    raise UserError(_("Không tìm thấy trường kiểm kê phù hợp trên stock.quant."))

                quant.with_context(from_proposal_sheet_actual_stock=True).sudo().action_apply_inventory()

                line.write({
                    'last_counted_qty': target_qty,
                    'last_counted_by': self.env.user.id,
                    'last_counted_date': fields.Datetime.now(),
                })

                log_items.append(
                    "<li><b>%s</b>: hệ thống %s → thực tế %s, chênh %s</li>" % (
                        line.product_id.display_name,
                        old_qty,
                        target_qty,
                        target_qty - old_qty,
                    )
                )

            rec.sudo().write({
                'stock_check_done': True,
                'stock_checked_by': self.env.user.id,
                'stock_checked_date': fields.Datetime.now(),
            })

            message = (
                "<p>Đã xác nhận tồn thực tế cho phiếu <strong>%s</strong> tại kho "
                "<strong>%s</strong> bởi <em>%s</em>.</p>"
                "<ul>%s</ul>"
            ) % (
                rec.name,
                rec.stock_location_id.display_name,
                self.env.user.name,
                ''.join(log_items),
            )

            rec.message_post(body=Markup(message))

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_reset_stock_check(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Chỉ được reset xác nhận tồn khi phiếu đang ở trạng thái nháp."))

            if rec.requested_by != self.env.user:
                raise UserError(_("Chỉ người đề xuất mới được reset xác nhận tồn."))

            lines = rec._get_stock_check_lines()
            lines.write({
                'actual_count_qty': 0.0,
                'count_note': False,
                'last_counted_qty': 0.0,
                'last_counted_by': False,
                'last_counted_date': False,
            })

            rec.write({
                'stock_check_done': False,
                'stock_checked_by': False,
                'stock_checked_date': False,
            })

            rec.message_post(body=_("Đã reset thông tin kiểm kê thực tế trên phiếu đề xuất."))

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_load_commercial_from_sale_order(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Chỉ được nạp dữ liệu khi phiếu đang ở trạng thái nháp."))

            if rec.type != 'commercial_purchase':
                raise UserError(_("Chỉ dùng chức năng này cho loại đề xuất Mua hàng thương mại."))

            if not rec.project_id:
                raise UserError(_("Vui lòng chọn Dự án trước."))

            if not rec.sale_order_id:
                raise UserError(_("Dự án này chưa có Đơn bán liên kết."))

            sale_lines = rec.sale_order_id.order_line.filtered(
                lambda l: not l.display_type and l.product_id
            )

            if not sale_lines:
                raise UserError(_("Không tìm thấy sản phẩm nào trong Đơn bán."))

            values = [(5, 0, 0)]

            for sol in sale_lines:
                product = sol.product_id
                seller = product.seller_ids[:1]

                vendor_id = seller.partner_id.id if seller else False
                purchase_price = seller.price if seller else 0.0

                purchase_taxes = product.supplier_taxes_id.filtered(
                    lambda t: not t.company_id or t.company_id == (rec.company_id or rec.env.company)
                )

                values.append((0, 0, {
                    'type': 'commercial_purchase',
                    'sale_order_line_id': sol.id,
                    'product_id': product.id,

                    # Số lượng đề xuất default = số lượng báo giá
                    'quantity': sol.product_uom_qty or 1.0,

                    'unit': sol.product_uom.id,
                    'price_unit': purchase_price or 0.0,
                    'vendor_id': vendor_id,
                    'tax_id': [(6, 0, purchase_taxes.ids)],

                    # Ghi chú để user tự nhập, không tự lấy mô tả sản phẩm
                    'description': False,

                    # Thông tin bán chỉ để xem
                    'sale_qty': sol.product_uom_qty or 0.0,
                    'sale_price_unit': sol.price_unit or 0.0,
                    'sale_subtotal': sol.price_subtotal or 0.0,
                }))

            rec.commercial_material_line_ids = values

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_submit(self):
        for rec in self:
            if rec.type == 'commercial_purchase':
                if not rec.project_id:
                    raise ValidationError(_("Phiếu mua hàng thương mại phải chọn Dự án."))

                if not rec.sale_order_id:
                    raise ValidationError(_("Dự án chưa có Đơn bán nên không thể gửi duyệt phiếu mua hàng thương mại."))

                if not rec.commercial_material_line_ids:
                    raise ValidationError(_("Phiếu mua hàng thương mại phải có ít nhất một dòng hàng."))

                if not rec.stock_check_done:
                    has_stock_diff = any(
                        bool(line.count_diff_qty) for line in rec.commercial_material_line_ids
                    )
                    if has_stock_diff:
                        raise ValidationError(_("Phiếu mua hàng thương mại phải được xác nhận tồn thực tế trước khi gửi duyệt."))

                for line in rec.commercial_material_line_ids:
                    if not line.product_id:
                        raise ValidationError(_("Có dòng chưa chọn sản phẩm."))

                    if not line.sale_order_line_id:
                        raise ValidationError(
                            _("Dòng sản phẩm '%s' chưa liên kết Dòng đơn bán.")
                            % line.product_id.display_name
                        )

                    if not line.vendor_id:
                        raise ValidationError(
                            _("Dòng sản phẩm '%s' chưa chọn Nhà cung cấp.")
                            % line.product_id.display_name
                        )

                    if line.quantity <= 0:
                        raise ValidationError(
                            _("Số lượng đề xuất của sản phẩm '%s' phải lớn hơn 0.")
                            % line.product_id.display_name
                        )

        return super().action_submit()


class ProposalMaterialLine(models.Model):
    _inherit = 'proposal.material.line'

    type = fields.Selection(
        selection_add=[
            ('commercial_purchase', 'Mua hàng thương mại'),
        ],
        ondelete={'commercial_purchase': 'cascade'},
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Đơn bán',
        related='sheet_id.sale_order_id',
        store=True,
        readonly=True,
    )

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Dòng đơn bán',
        domain="[('order_id', '=', sale_order_id), ('display_type', '=', False)]",
    )

    sale_qty = fields.Float(
        string='SL báo giá',
        readonly=True,
        digits='Product Unit of Measure',
    )

    sale_price_unit = fields.Float(
        string='Giá bán',
        readonly=True,
        digits='Product Price',
    )

    sale_subtotal = fields.Monetary(
        string='Thành tiền bán',
        currency_field='currency_id',
        readonly=True,
    )

    allowed_product_ids = fields.Many2many(
        'product.product',
        'proposal_material_line_allowed_product_rel',
        'line_id',
        'product_id',
        string='Sản phẩm được phép chọn',
        compute='_compute_allowed_product_ids',
        store=False,
    )

    @api.depends(
        'sheet_id',
        'sheet_id.sale_order_id',
        'sheet_id.sale_order_id.order_line',
        'sheet_id.sale_order_id.order_line.product_id',
    )
    def _compute_allowed_product_ids(self):
        Product = self.env['product.product']
        for line in self:
            products = Product.browse()
            if line.sheet_id and line.sheet_id.sale_order_id:
                products = line.sheet_id.sale_order_id.order_line.filtered(
                    lambda l: not l.display_type and l.product_id
                ).mapped('product_id')
            line.allowed_product_ids = products

    def _get_purchase_taxes_from_product(self, product, company):
        self.ensure_one()
        return product.supplier_taxes_id.filtered(
            lambda t: not t.company_id or t.company_id == company
        )

    def _get_first_vendor_price(self, product):
        seller = product.seller_ids[:1]
        if seller:
            return seller.partner_id, seller.price or 0.0
        return False, 0.0

    def _prepare_commercial_values_from_sale_line(self, sale_line):
        self.ensure_one()

        product = sale_line.product_id
        company = self.sheet_id.company_id or self.env.company

        self.product_id = product.id
        self.unit = sale_line.product_uom.id

        # Thông tin bán chỉ để xem
        self.sale_qty = sale_line.product_uom_qty or 0.0
        self.sale_price_unit = sale_line.price_unit or 0.0
        self.sale_subtotal = sale_line.price_subtotal or 0.0

        # Số lượng đề xuất default = số lượng báo giá
        self.quantity = sale_line.product_uom_qty or 1.0

        # Không tự fill description.
        # description là ghi chú để người dùng tự nhập.

        vendor, purchase_price = self._get_first_vendor_price(product)

        if vendor and not self.vendor_id:
            self.vendor_id = vendor.id

        # Giá mua đề xuất: chỉ gợi ý nếu đang trống
        if not self.price_unit:
            self.price_unit = purchase_price or 0.0

        purchase_taxes = self._get_purchase_taxes_from_product(product, company)
        if purchase_taxes and not self.tax_id:
            self.tax_id = [(6, 0, purchase_taxes.ids)]

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id_commercial(self):
        for line in self:
            if line.sheet_id and line.sheet_id.type != 'commercial_purchase':
                continue

            sale_line = line.sale_order_line_id
            if not sale_line:
                continue

            line._prepare_commercial_values_from_sale_line(sale_line)

    @api.onchange('product_id')
    def _onchange_product_id_commercial(self):
        for line in self:
            if not line.product_id:
                continue

            if line.sheet_id and line.sheet_id.type != 'commercial_purchase':
                continue

            sheet = line.sheet_id
            if not sheet:
                continue

            if not sheet.sale_order_id:
                line.product_id = False
                return {
                    'warning': {
                        'title': _('Chưa có đơn bán'),
                        'message': _('Vui lòng chọn Dự án có liên kết Đơn bán trước.'),
                    }
                }

            sale_line = sheet.sale_order_id.order_line.filtered(
                lambda l: not l.display_type and l.product_id == line.product_id
            )[:1]

            if not sale_line:
                product_name = line.product_id.display_name
                line.product_id = False
                line.sale_order_line_id = False
                return {
                    'warning': {
                        'title': _('Không thuộc đơn bán'),
                        'message': _("Sản phẩm '%s' không nằm trong Đơn bán của dự án đã chọn.") % product_name,
                    }
                }

            line.sale_order_line_id = sale_line.id
            line._prepare_commercial_values_from_sale_line(sale_line)

    @api.model_create_multi
    def create(self, vals_list):
        normal_vals_list = []
        commercial_vals_list = []

        for vals in vals_list:
            vals = dict(vals)

            sheet = False
            if vals.get('sheet_id'):
                sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])

            if sheet and sheet.exists() and sheet.type == 'commercial_purchase':
                vals['type'] = 'commercial_purchase'

                if not vals.get('sale_order_line_id') and vals.get('product_id') and sheet.sale_order_id:
                    sale_line = sheet.sale_order_id.order_line.filtered(
                        lambda l: not l.display_type and l.product_id.id == vals.get('product_id')
                    )[:1]
                    if sale_line:
                        vals['sale_order_line_id'] = sale_line.id

                if vals.get('sale_order_line_id'):
                    sale_line = self.env['sale.order.line'].browse(vals['sale_order_line_id'])
                    if sale_line.exists():
                        vals.setdefault('product_id', sale_line.product_id.id)
                        vals.setdefault('unit', sale_line.product_uom.id)

                        # Số lượng đề xuất default = số lượng báo giá
                        vals['quantity'] = sale_line.product_uom_qty or 1.0

                        vals.setdefault('sale_qty', sale_line.product_uom_qty or 0.0)
                        vals.setdefault('sale_price_unit', sale_line.price_unit or 0.0)
                        vals.setdefault('sale_subtotal', sale_line.price_subtotal or 0.0)

                        # Không tự fill description từ mô tả sản phẩm / sale line.
                        vals.setdefault('description', False)

                commercial_vals_list.append(vals)
            else:
                normal_vals_list.append(vals)

        records = self.browse()

        if normal_vals_list:
            records |= super(ProposalMaterialLine, self).create(normal_vals_list)

        if commercial_vals_list:
            # Né create gốc của proposal.material.line nếu gốc đang chặn sheet.type != material.
            records |= models.Model.create(self, commercial_vals_list)

        return records

    def write(self, vals):
        vals = dict(vals)

        commercial_lines = self.filtered(
            lambda l: l.sheet_id and l.sheet_id.type == 'commercial_purchase'
        )
        normal_lines = self - commercial_lines

        res = True

        if normal_lines:
            res = super(ProposalMaterialLine, normal_lines).write(vals)

        if commercial_lines:
            commercial_vals = dict(vals)
            commercial_vals['type'] = 'commercial_purchase'

            res = models.Model.write(commercial_lines, commercial_vals) and res

        return res

    @api.constrains('sheet_id', 'type')
    def _check_commercial_line_sheet_type(self):
        for line in self:
            if line.type == 'commercial_purchase':
                if line.sheet_id and line.sheet_id.type != 'commercial_purchase':
                    raise ValidationError(
                        _("Dòng mua hàng thương mại chỉ được nằm trong phiếu loại Mua hàng thương mại.")
                    )

    @api.constrains('product_id', 'sheet_id', 'type')
    def _check_product_belongs_to_sale_order(self):
        for line in self:
            if line.type != 'commercial_purchase':
                continue

            if not line.product_id or not line.sheet_id:
                continue

            if not line.sheet_id.sale_order_id:
                raise ValidationError(_("Dự án chưa có Đơn bán."))

            exists = line.sheet_id.sale_order_id.order_line.filtered(
                lambda l: not l.display_type and l.product_id == line.product_id
            )

            if not exists:
                raise ValidationError(
                    _("Sản phẩm '%s' không thuộc Đơn bán của dự án đã chọn.")
                    % line.product_id.display_name
                )

    @api.constrains('sale_order_line_id', 'sheet_id', 'type')
    def _check_sale_order_line_belongs_to_sale_order(self):
        for line in self:
            if line.type != 'commercial_purchase':
                continue

            if line.sale_order_line_id and line.sheet_id and line.sheet_id.sale_order_id:
                if line.sale_order_line_id.order_id != line.sheet_id.sale_order_id:
                    raise ValidationError(_("Dòng đơn bán phải thuộc Đơn bán của Dự án."))