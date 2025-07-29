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

    @api.onchange('expense_id')
    def _onchange_expense_id(self):
        _logger.info("Onchange triggered: expense_id=%s", self.expense_id)
        if self.expense_id and self.expense_id.id:
            self.unit = self.expense_id.default_unit
            self.price_unit = self.expense_id.price_unit or 0.0
        else:
            self.unit = False
            self.price_unit = 0.0

    @api.depends('price_unit', 'quantity')
    def _compute_price_total(self):
        for rec in self:
            _logger.info(
                "Computing total for line ID=%s: qty=%s, price_unit=%s",
                rec.id, rec.quantity, rec.price_unit
            )
            rec.price_total = rec.price_unit * rec.quantity

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if self.product_id.type == 'service':
                self.type = 'other'
                return {
                    'domain': {
                        'type': [('value', '=', 'other')],
                    }
                }
            else:
                # Gợi ý tự động chọn nếu có "nhân công" hoặc "máy"
                name = (self.product_id.name or '').lower()
                if 'nhân công' in name:
                    self.type = 'labor'
                elif 'máy' in name:
                    self.type = 'equipment'
                else:
                    self.type = False  # hoặc chọn mặc định

                return {
                    'domain': {
                        'type': [('value', 'in', ['labor', 'equipment'])],
                    }
                }
