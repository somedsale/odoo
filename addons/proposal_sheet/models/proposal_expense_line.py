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
            if not expense.default_unit:
                raise ValidationError(f"Chi phí '{expense.name}' chưa có đơn vị được cấu hình.")
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