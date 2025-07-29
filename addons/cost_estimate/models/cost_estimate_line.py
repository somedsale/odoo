from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class CostEstimateLine(models.Model):
    _name = 'cost.estimate.line'
    _description = 'Chi tiết dự toán'

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán', ondelete='cascade', required=True)
    product_id = fields.Many2one('product.template', string='Sản phẩm', ondelete='restrict', required=True)
    product_name = fields.Char(string="Tên sản phẩm", related='product_id.name', store=False)
    quantity = fields.Float('Số lượng', default=1.0, required=True)
    unit = fields.Many2one('uom.uom', string='Đơn vị')
    price_unit = fields.Float(string='Đơn giá', digits=(16, 0), default=0.0)
    price_subtotal = fields.Float(
        string='Thành tiền',
        compute='_compute_price_subtotal',
        store=True,
        digits=(16, 0)
    )
    material_line_ids = fields.One2many(
        'product.material.line',
        'estimate_line_id',
        string='Dòng vật tư'
    )
    expense_line_ids = fields.One2many(
        'project.expense.line',
        'estimate_line_id',
        string='Dòng chi phí khác'
)
    labor_expense_line_ids = fields.One2many(
    'project.expense.line',
    compute='_compute_labor_expense_lines',
    string='Chi phí nhân công',
    store=False
)
    equipment_expense_line_ids = fields.One2many(
    'project.expense.line',
    compute='_compute_equipment_expense_lines',
    string='Chi phí máy móc',
    store=False
)
    @api.depends('expense_line_ids')
    def _compute_labor_expense_lines(self):
        for line in self:
            line.labor_expense_line_ids = line.expense_line_ids.filtered(lambda e: e.expense_id.type == 'labor')

    @api.depends('expense_line_ids')
    def _compute_equipment_expense_lines(self):
        for line in self:
            line.equipment_expense_line_ids = line.expense_line_ids.filtered(lambda e: e.expense_id.type == 'equipment')

    sale_order_line_id = fields.Many2one('sale.order.line', string="Dòng báo giá gốc")
    is_from_sale_order = fields.Boolean(string='Từ báo giá', compute='_compute_is_from_sale_order')
    task_id = fields.Many2one('project.task', string='Nhiệm vụ')
    product_type = fields.Selection(related='product_id.detailed_type', store=True)

    @api.depends('sale_order_line_id')
    def _compute_is_from_sale_order(self):
        for line in self:
            line.is_from_sale_order = bool(line.sale_order_line_id)

    @api.depends('material_line_ids.price_total', 'expense_line_ids.price_total', 'quantity', 'price_unit', 'product_id.detailed_type')
    def _compute_price_subtotal(self):
        for rec in self:
            if rec.product_id.detailed_type == 'service':
                total_expense = sum(line.price_total for line in rec.expense_line_ids)
                rec.price_unit = total_expense
                rec.price_subtotal = total_expense or (rec.price_unit * rec.quantity)
                
            else:
                total_material = sum(line.price_total for line in rec.material_line_ids)
                rec.price_unit = total_material
                rec.price_subtotal = total_material * rec.quantity if total_material else rec.price_unit * rec.quantity
    

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit = self.product_id.uom_id
            # Nếu từ báo giá và là dịch vụ thì lấy đơn giá từ SO line
            if self.product_id.detailed_type == 'service' and self.sale_order_line_id:
                self.price_unit = self.sale_order_line_id.price_unit
        else:
            self.unit = False
