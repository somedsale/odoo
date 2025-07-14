from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProposalExpenseLine(models.Model):
    _name = 'proposal.expense.line'
    _description = 'Chi tiết chi phí'

    sheet_id = fields.Many2one('proposal.sheet', string='Phiếu đề xuất', required=True, ondelete='cascade')
    expense_id = fields.Many2one('project.expense', string='Chi phí', required=True)
    quantity = fields.Float(string='Số lượng', default=1.0)
    unit = fields.Many2one('uom.uom', string='Đơn vị', required=True)
    price_unit = fields.Float(string='Số tiền')
    description = fields.Text(string='Ghi chú')
    type = fields.Selection(selection=[('expense', 'Chi phí')], default='expense', required=True)

