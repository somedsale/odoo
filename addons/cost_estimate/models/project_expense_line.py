from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)

class ProjectExpenseLine(models.Model):
    _name = 'project.expense.line'
    _description = 'Dòng chi phí khác'

    expense_id = fields.Many2one('project.expense', string='Chi phí', required=True)
    quantity = fields.Float(string='Số lượng', default=1.0)
    unit = fields.Many2one('uom.uom', string='Đơn vị', required=True)
    price_unit = fields.Float(string='Đơn giá', digits=(16, 0), default=0.0)
    price_total = fields.Float(
        string='Thành tiền',
        compute='_compute_price_total',
        store=True,
        digits=(16, 0)
    )
    estimate_line_id = fields.Many2one(
        'cost.estimate.line',
        string='Dòng dự toán',
        ondelete='cascade',
        required=True
    )
    type = fields.Selection([
    ('labor', 'Nhân công'),
    # ('equipment', 'Máy móc'),
    ('other', 'Chi phí khác')
], string="Loại chi phí", default=lambda self: self.env.context.get('default_type'), store=True)
    
    percent = fields.Float(
        string='Hệ số (%)',
        default=0.0,
        help="Tăng/Giảm theo % trên thành tiền gốc"
    )

    @api.onchange('expense_id')
    def _onchange_expense_id(self):
        
        if self.expense_id and self.expense_id.id:
            self.unit = self.expense_id.default_unit
            # Ưu tiên default_type từ context, nếu không có thì lấy từ expense_id
            self.type =  self.expense_id.type 
            self.price_unit = self.expense_id.price_unit or 0.0
        else:
            self.unit = False
            self.price_unit = 0.0
            self.type = 'other'

    @api.depends('price_unit', 'quantity', 'percent')
    def _compute_price_total(self):
        for rec in self:
            base_amount = rec.price_unit * rec.quantity
            rec.price_total = base_amount * (1 + (rec.percent or 0.0) / 100.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('type') and vals.get('expense_id'):
                expense = self.env['project.expense'].browse(vals['expense_id'])
                vals['type'] = expense.type
        return super().create(vals_list)

