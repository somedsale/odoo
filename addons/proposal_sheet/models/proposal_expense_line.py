from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ProposalExpenseLine(models.Model):
    _name = 'proposal.expense.line'
    _description = 'Chi Tiết Chi Phí'
    _inherit = ['mail.thread']

    active = fields.Boolean(string='Active', default=True)
    sheet_id = fields.Many2one('proposal.sheet', string='Phiếu Đề Xuất', required=True, ondelete='cascade')
    expense_id = fields.Many2one('project.expense', string='Chi Phí', required=True)
    quantity = fields.Float(string='Số Lượng', default=1.0, digits='Product Unit of Measure')
    unit = fields.Many2one('uom.uom', string='Đơn Vị', required=True)
    price_unit = fields.Float(string='Đơn giá', digits='Product Price', required=True)
    price_total = fields.Float(string='Thành tiền', compute='_compute_price_total', store=True)
    description = fields.Text(string='Ghi Chú')
    type = fields.Selection([('expense', 'Chi Phí')], default='expense', required=True, readonly=True)
    type_expense = fields.Selection(related='expense_id.type', string='Loại Chi Phí', readonly=True)
    estimate_price_unit = fields.Float(
    string='Giá Dự Toán',
    compute='_compute_estimate_price_unit',
    store=False,
    readonly=True
)
    estimate_price_total = fields.Float(string='Giá Dự Toán', compute='_compute_estimate_price_total', store=False, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Tính Giá', default=lambda self: self.env.company.currency_id)
    @api.depends('expense_id', 'sheet_id')
    def _compute_estimate_price_unit(self):
        for line in self:
            if not line.expense_id or not line.sheet_id or not line.sheet_id.project_id:
                line.estimate_price_unit = 0.0
                continue
            
            project = line.sheet_id.project_id
            
            # Lấy tất cả dòng dự toán của dự án
            estimate_lines = self.env['cost.estimate.line'].search([
                ('cost_estimate_id.project_id', '=', project.id)
            ])
            
            if not estimate_lines:
                line.estimate_price_unit = 0.0
                continue
            
            # Lấy các mapping project.expense.line với estimate_line_id trong estimate_lines
            mappings = self.env['project.expense.line'].search([
                ('estimate_line_id', 'in', estimate_lines.ids),
                ('expense_id', '=', line.expense_id.id)
            ], limit=1)  # lấy 1 mapping tương ứng expense_id và estimate_line
            
            if mappings and mappings.estimate_line_id:
                line.estimate_price_unit = mappings.price_unit or 0.0
            else:
                line.estimate_price_unit = 0.0

    @api.depends('quantity', 'estimate_price_unit')
    def _compute_estimate_price_total(self):
        for line in self:
            line.estimate_price_total = line.quantity * (line.estimate_price_unit or 0.0)

    @api.onchange('expense_id')
    def _onchange_expense_id(self):
        if self.expense_id:
            if not self.expense_id.exists():
                return {
                    'warning': {
                        'title': 'Lỗi',
                        'message': 'Chi phí không tồn tại.'
                    }
                }
            if not self.expense_id.default_unit:
                return {
                    'warning': {
                        'title': 'Thiếu cấu hình',
                        'message': f"Chi phí '{self.expense_id.name}' chưa có đơn vị được cấu hình."
                    }
                }
            self.unit = self.expense_id.default_unit
            self.price_unit = self.expense_id.price_unit or 0.0
        else:
            self.unit = False
            self.price_unit = 0.0

    @api.model
    def create(self, vals):
        _logger.info("Creating ProposalExpenseLine with vals: %s", vals)
        if 'expense_id' in vals and vals.get('expense_id'):
            expense = self.env['project.expense'].browse(vals['expense_id'])
            if not expense.exists():
                raise ValidationError("Chi phí không tồn tại.")
            vals['unit'] = expense.default_unit.id
            if not vals.get('price_unit'):
                vals['price_unit'] = expense.price_unit or 0.0
        if 'type' not in vals or vals['type'] != 'expense':
            vals['type'] = 'expense'
        if 'sheet_id' in vals and vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError("Phiếu đề xuất không tồn tại.")
            if sheet.type != 'expense':
                raise ValidationError("Không thể thêm dòng chi phí vào phiếu đề xuất vật tư.")
        return super().create(vals)

    def write(self, vals):
        _logger.info("Writing ProposalExpenseLine with vals: %s", vals)
        if 'expense_id' in vals and vals.get('expense_id'):
            expense = self.env['project.expense'].browse(vals['expense_id'])
            if not expense.exists():
                raise ValidationError("Chi phí không tồn tại.")
            if not expense.default_unit:
                raise ValidationError(f"Chi phí '{expense.name}' chưa có đơn vị được cấu hình.")
            vals['unit'] = expense.default_unit.id
        if 'type' in vals and vals['type'] != 'expense':
            raise ValidationError("Không thể thay đổi loại của dòng chi phí.")
        if 'sheet_id' in vals and vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError("Phiếu đề xuất không tồn tại.")
            if sheet.type != 'expense':
                raise ValidationError("Không thể thêm dòng chi phí vào phiếu đề xuất vật tư.")
        return super().write(vals)

    @api.constrains('quantity', 'price_unit')
    def _check_quantity_price(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError("Số lượng chi phí phải lớn hơn 0.")
            if line.price_unit <= 0:
                raise ValidationError("Số tiền chi phí phải lớn hơn 0.")

    def archive(self):
        self.write({'active': False})
        self.message_post(body='Dòng chi phí đã được lưu trữ.')

    def unarchive(self):
        self.write({'active': True})
        self.message_post(body='Dòng chi phí đã được khôi phục.')
    @api.depends('quantity', 'price_unit')
    def _compute_price_total(self):
        for line in self:
            line.price_total = line.quantity * line.price_unit