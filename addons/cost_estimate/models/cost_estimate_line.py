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
        string='Thành tiền dự toán',
        compute='_compute_price_subtotal',
        store=True,
        digits=(16, 0)
    )
    project_id = fields.Many2one('project.project', string='Dự án', related='cost_estimate_id.project_id', store=True)
    material_line_ids = fields.One2many(
        'product.material.line',
        'estimate_line_id',
        string='Dòng vật tư'
    )
    expense_line_ids = fields.One2many(
        'project.expense.line',
        'estimate_line_id',
        string='Dòng chi phí khác',
        domain=[('type', '=', 'other')]
)
    labor_expense_line_ids = fields.One2many(
    'project.expense.line', 'estimate_line_id',
    string="Chi phí nhân công",
    domain=[('type', '=', 'labor')]
)
    # equipment_expense_line_ids = fields.One2many(
    #     'project.expense.line', 'estimate_line_id',
    #     string="Chi phí máy móc",
    #     domain=[('type', '=', 'equipment')]
    # )
    sale_order_line_id = fields.Many2one('sale.order.line', string="Dòng báo giá gốc")
    is_from_sale_order = fields.Boolean(string='Từ báo giá', compute='_compute_is_from_sale_order')
    task_id = fields.Many2one('project.task', string='Nhiệm vụ')
    product_type = fields.Selection(related='product_id.detailed_type', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    tax_id = fields.Many2one(
        'account.tax',
        string='Thuế',
        domain=[('type_tax_use', '=', 'sale')]
    )
    price_tax = fields.Float(
        string='Thuế',
        compute='_compute_total_with_tax',
        store=True,
        digits=(16, 0)
    )
    price_total = fields.Float(
        string='Thành tiền dự toán (sau thuế)',
        compute='_compute_total_with_tax',
        store=True,
        digits=(16, 0)
    )
    sale_order_price_unit = fields.Float(
    string="Đơn giá báo giá",
    related="sale_order_line_id.price_unit",
    store=False,
    readonly=True,
    digits=(16, 0),
)
    sale_order_price_subtotal = fields.Monetary(
    string="Thành tiền báo giá trước thuế",
    related="sale_order_line_id.price_subtotal",
    store=False,
    readonly=True,
    currency_field="currency_id",
)
    sale_order_price_total = fields.Monetary(
    string="Thành tiền báo giá sau thuế",
    related="sale_order_line_id.price_total",
    store=False,
    readonly=True,
    currency_field="currency_id"    
)

    @api.depends('price_subtotal', 'tax_id', 'currency_id')
    def _compute_total_with_tax(self):
        for rec in self:
            subtotal = rec.price_subtotal or 0.0
            price_tax = 0.0
            price_total = subtotal

            if subtotal and rec.tax_id:
                res = rec.tax_id.compute_all(
                    subtotal,
                    currency=rec.currency_id,
                    quantity=1
                )
                price_tax = res['total_included'] - res['total_excluded']
                price_total = res['total_included']

            rec.price_tax = price_tax
            rec.price_total = price_total


    @api.depends('sale_order_line_id')
    def _compute_is_from_sale_order(self):
        for line in self:
            line.is_from_sale_order = bool(line.sale_order_line_id)

    @api.depends('material_line_ids.price_total', 'expense_line_ids.price_total', 'quantity', 'price_unit', 'labor_expense_line_ids.price_total')
    def _compute_price_subtotal(self):
        for rec in self:
            total_material = sum(line.price_total for line in rec.material_line_ids)
            total_expense = sum(line.price_total for line in rec.expense_line_ids)
            total_labor = sum(line.price_total for line in rec.labor_expense_line_ids)
            total_all = total_material + total_expense + total_labor
            rec.price_unit = total_all
            rec.price_subtotal = total_all * rec.quantity if total_all else rec.price_unit * rec.quantity
    

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit = self.product_id.uom_id
            # Nếu từ báo giá và là dịch vụ thì lấy đơn giá từ SO line
            if self.product_id.detailed_type == 'service' and self.sale_order_line_id:
                self.price_unit = self.sale_order_line_id.price_unit
        else:
            self.unit = False

    labor_total_cost = fields.Float(string='Tổng chi phí nhân công', digits=(16, 0), compute='_compute_expense_totals')
    # equipment_total_cost = fields.Float(string='Tổng chi phí máy móc', digits=(16, 0), compute='_compute_expense_totals')
    material_total_cost = fields.Float(string='Tổng chi phí vật tư', digits=(16, 0), compute='_compute_expense_totals')
    other_total_cost = fields.Float(string='Tổng chi phí khác', digits=(16, 0), compute='_compute_expense_totals')


    @api.depends( 'labor_expense_line_ids.price_total','material_line_ids.price_total','expense_line_ids.price_total')
    def _compute_expense_totals(self):
        for rec in self:
            rec.labor_total_cost = sum(rec.labor_expense_line_ids.mapped('price_total'))
            # rec.equipment_total_cost = sum(rec.equipment_expense_line_ids.mapped('price_total'))
            rec.material_total_cost = sum(rec.material_line_ids.mapped('price_total'))
            rec.other_total_cost = sum(rec.expense_line_ids.mapped('price_total'))
