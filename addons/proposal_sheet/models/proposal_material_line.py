from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ProposalMaterialLine(models.Model):
    _name = 'proposal.material.line'
    _description = 'Chi Tiết Vật Tư'
    _inherit = ['mail.thread']

    active = fields.Boolean(string='Active', default=True)
    sheet_id = fields.Many2one('proposal.sheet', string='Phiếu Đề Xuất', required=True, ondelete='cascade')
    material_id = fields.Many2one('project.material', string='Vật Tư', required=True)
    quantity = fields.Float(string='Số Lượng', default=1.0, digits='Product Unit of Measure')
    unit = fields.Many2one('uom.uom', string='Đơn Vị', required=True)
    price_unit = fields.Float(string='Đơn Giá', digits='Product Price')
    price_total = fields.Float(string='Thành tiền', compute='_compute_price_total', store=True)
    currency_id = fields.Many2one('res.currency', string='Tính Giá', default=lambda self: self.env.company.currency_id)
    vendor_id = fields.Many2one(
    'res.partner',
    string='Nhà Cung Cấp Đề Xuất',
    domain=[('supplier_rank', '>', 0)]
)
    estimate_price_unit = fields.Float(
    string='Giá Dự Toán',
    compute='_compute_estimate_price_unit',
    store=False,
    readonly=True
)
    estimate_price_total = fields.Float(string='Giá Dự Toán', compute='_compute_estimate_price_total', store=False, readonly=True)
    description = fields.Text(string='Ghi Chú')
    type = fields.Selection([('material', 'Vật Tư')], default='material', required=True, readonly=True)

    @api.depends('quantity', 'estimate_price_unit')
    def _compute_estimate_price_total(self):
        for line in self:
            line.estimate_price_total = line.quantity * line.estimate_price_unit
    @api.depends('material_id', 'sheet_id.project_id')
    def _compute_estimate_price_unit(self):
        for line in self:
            estimate_price = 0.0
            if line.material_id and line.sheet_id and line.sheet_id.project_id:
                # Lấy các dòng cost estimate thuộc dự án đó
                estimate_lines = self.env['cost.estimate.line'].search([
                    ('project_id', '=', line.sheet_id.project_id.id)
                ])
                matched_line = None
                for est_line in estimate_lines:
                    # Tìm trong từng dòng material_line_ids có chứa material_id giống nhau
                    matched_line = est_line.material_line_ids.filtered(
                        lambda m: m.material_id.id == line.material_id.id
                    )
                    if matched_line:
                        break  # chỉ lấy dòng đầu tiên khớp

                if matched_line:
                    estimate_price = matched_line[0].price_unit  # hoặc .price_total tùy nhu cầu

            line.estimate_price_unit = estimate_price



    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id:
            if not self.material_id.unit:
                return {
                    'warning': {
                        'title': 'Thiếu cấu hình',
                        'message': f"Vật tư '{self.material_id.name}' chưa có đơn vị được cấu hình."
                    }
                }
            self.unit = self.material_id.unit
            self.price_unit = self.material_id.price_unit 
            self.vendor_id = self.material_id.vendor_id
        else:
            self.unit = False
            self.price_unit = 0.0
            self.vendor_id = False

    @api.model
    def create(self, vals):
        _logger.info("Creating ProposalMaterialLine with vals: %s", vals)
        if 'material_id' in vals and vals.get('material_id'):
            material = self.env['project.material'].browse(vals['material_id'])
            if not material.exists():
                raise ValidationError("Vật tư không tồn tại.")
            if not material.unit:
                raise ValidationError(f"Vật tư '{material.name}' chưa có đơn vị được cấu hình.")
            vals['unit'] = material.unit.id
            if not vals.get('price_unit'):
                vals['price_unit'] = material.price_unit or 0.0
        if 'type' not in vals or vals['type'] != 'material':
            vals['type'] = 'material'
        if 'sheet_id' in vals and vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError("Phiếu đề xuất không tồn tại.")
            if sheet.type != 'material':
                raise ValidationError("Không thể thêm dòng vật tư vào phiếu đề xuất chi phí.")
        return super().create(vals)

    def write(self, vals):
        _logger.info("Writing ProposalMaterialLine with vals: %s", vals)
        if 'material_id' in vals and vals.get('material_id'):
            material = self.env['project.material'].browse(vals['material_id'])
            if not material.exists():
                raise ValidationError("Vật tư không tồn tại.")
            if not material.unit:
                raise ValidationError(f"Vật tư '{material.name}' chưa có đơn vị được cấu hình.")
            vals['unit'] = material.unit.id
        if 'type' in vals and vals['type'] != 'material':
            raise ValidationError("Không thể thay đổi loại của dòng vật tư.")
        if 'sheet_id' in vals and vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError("Phiếu đề xuất không tồn tại.")
            if sheet.type != 'material':
                raise ValidationError("Không thể thêm dòng vật tư vào phiếu đề xuất chi phí.")
        return super().write(vals)

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError("Số lượng vật tư phải lớn hơn 0.")
    @api.constrains('price_unit','estimate_price_unit')
    def _check_price_unit(self):
        for line in self:
            if line.price_unit <= 0:
                raise ValidationError("Giá vật tư phải lớn hơn 0.")
            if line.price_unit > line.estimate_price_unit:
                raise ValidationError("Giá đề xuất không được lớn hơn dự toán")

    def archive(self):
        self.write({'active': False})
        self.message_post(body='Dòng vật tư đã được lưu trữ.')

    def unarchive(self):
        self.write({'active': True})
        self.message_post(body='Dòng vật tư đã được khôi phục.')
    @api.depends('quantity', 'price_unit')
    def _compute_price_total(self):
        for line in self:
            line.price_total = line.quantity * line.price_unit

    