# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class CostEstimateLine(models.Model):
    _name = 'cost.estimate.line'
    _description = 'Chi tiết dự toán'
    _order = "sequence, id"

    sequence = fields.Integer(default=10)

    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False, index=True)

    cost_estimate_id = fields.Many2one('cost.estimate', string='Dự toán', ondelete='cascade', required=True)

    name = fields.Text(string="Tên hạng mục")

    product_id = fields.Many2one('product.product', string='Sản phẩm', ondelete='restrict')
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
        'project.expense.line',
        'estimate_line_id',
        string="Chi phí nhân công",
        domain=[('type', '=', 'labor')]
    )

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

    so_display_name = fields.Char(
        string='Sản phẩm (SO)',
        related='sale_order_line_id.display_name',
        store=True, readonly=True,
        related_sudo=True,
    )
    so_name = fields.Text(
        string='Diễn giải (SO)',
        related='sale_order_line_id.name',
        store=True, readonly=True,
        related_sudo=True,
    )
    so_thongso = fields.Text(
        string='Thông số (SO)',
        related='sale_order_line_id.x_thongso',
        store=True, readonly=True,
        related_sudo=True,
    )
    so_xuatxu = fields.Char(
        string='Xuất xứ (SO)',
        related='sale_order_line_id.x_xuatxu',
        store=True, readonly=True,
        related_sudo=True,
    )

    actual_cost = fields.Float(string="Chi phí thực tế", compute="_compute_actual_cost", store=False)
    difference_cost = fields.Float(string="Chênh lệch", compute="_compute_difference_cost", store=False)

    labor_total_cost = fields.Float(string='Tổng chi phí nhân công', digits=(16, 0), compute='_compute_expense_totals')
    material_total_cost = fields.Float(string='Tổng chi phí vật tư', digits=(16, 0), compute='_compute_expense_totals')
    other_total_cost = fields.Float(string='Tổng chi phí khác', digits=(16, 0), compute='_compute_expense_totals')


    estimate_material_amount = fields.Float(
    string='Dự toán vật tư (theo SL)',
    compute='_compute_estimate_amount_breakdown',
    digits=(16, 0),
    store=False,
)
    estimate_labor_amount = fields.Float(
        string='Dự toán nhân công (theo SL)',
        compute='_compute_estimate_amount_breakdown',
        digits=(16, 0),
        store=False,
    )
    estimate_other_amount = fields.Float(
        string='Dự toán SX chung (theo SL)',
        compute='_compute_estimate_amount_breakdown',
        digits=(16, 0),
        store=False,
    )
    actual_material_cost = fields.Float(
    string="Chi phí thực tế NVL",
    compute="_compute_actual_cost_by_type",
    digits=(16, 0),
    store=False,
    )
    actual_labor_cost = fields.Float(
        string="Chi phí thực tế nhân công",
        compute="_compute_actual_cost_by_type",
        digits=(16, 0),
        store=False,
    )
    actual_manufacturing_cost = fields.Float(
        string="Chi phí thực tế sản xuất chung",
        compute="_compute_actual_cost_by_type",
        digits=(16, 0),
        store=False,
    )

    @api.depends('material_total_cost', 'labor_total_cost', 'other_total_cost', 'quantity', 'display_type')
    def _compute_estimate_amount_breakdown(self):
        for rec in self:
            if rec.display_type:
                rec.estimate_material_amount = 0.0
                rec.estimate_labor_amount = 0.0
                rec.estimate_other_amount = 0.0
                continue

            qty = rec.quantity or 0.0
            rec.estimate_material_amount = (rec.material_total_cost or 0.0) * qty
            rec.estimate_labor_amount = (rec.labor_total_cost or 0.0) * qty
            rec.estimate_other_amount = (rec.other_total_cost or 0.0) * qty
    @api.depends('cost_estimate_id.project_id', 'display_type')
    def _compute_actual_cost_by_type(self):
        Payment = self.env['account.payment.request']

        for line in self:
            line.actual_material_cost = 0.0
            line.actual_labor_cost = 0.0
            line.actual_manufacturing_cost = 0.0

            if line.display_type:
                continue
            if not line.id or not line.cost_estimate_id.project_id:
                continue

            payments = Payment.search([
                ('cost_estimate_line_id', '=', line.id),
                ('project_id', '=', line.cost_estimate_id.project_id.id),
                ('status_expense', '=', 'paid'),   # hoặc ('state', '=', 'done') nếu bạn dùng chuẩn này
            ])

            line.actual_material_cost = sum(
                payments.filtered(lambda p: p.expense_type == 'material').mapped('total')
            )
            line.actual_labor_cost = sum(
                payments.filtered(lambda p: p.expense_type == 'labor').mapped('total')
            )
            line.actual_manufacturing_cost = sum(
                payments.filtered(lambda p: p.expense_type == 'manufacturing').mapped('total')
            )

    # =========================
    # Default sequence like SO
    # =========================
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            est_id = res.get('cost_estimate_id') or self.env.context.get('default_cost_estimate_id') or self.env.context.get('active_id')
            if est_id:
                est = self.env['cost.estimate'].browse(est_id)
                max_seq = max(est.line_ids.mapped('sequence') or [0])
                res['sequence'] = max_seq + 10
        return res

    # =========================
    # SECTION/NOTE helpers
    # =========================
    @api.onchange('display_type')
    def _onchange_display_type(self):
        """Nếu là section/note thì dọn các field không liên quan."""
        for rec in self:
            if rec.display_type:
                rec.product_id = False
                rec.tax_id = False
                rec.unit = False
                rec.quantity = 0.0
                rec.price_unit = 0.0
                rec.material_line_ids = [(5, 0, 0)]
                rec.expense_line_ids = [(5, 0, 0)]
                rec.labor_expense_line_ids = [(5, 0, 0)]

    @api.constrains('display_type', 'product_id', 'unit', 'quantity')
    def _check_required_for_normal_line(self):
        for rec in self:
            if not rec.display_type:
                if not rec.product_id:
                    raise ValidationError("Dòng hạng mục bắt buộc phải có Sản phẩm.")
                if not rec.unit:
                    raise ValidationError("Dòng hạng mục bắt buộc phải có Đơn vị.")
                if (rec.quantity or 0.0) <= 0:
                    raise ValidationError("Số lượng phải > 0.")

    # =========================
    # Computes
    # =========================
    @api.depends('product_id', 'quantity')
    def _compute_actual_cost(self):
        for line in self:
            if line.display_type:
                line.actual_cost = 0.0
                continue
            payments = self.env['account.payment.request'].search([
                ('cost_estimate_line_id', '=', line.id),
                ('project_id', '=', line.cost_estimate_id.project_id.id),
                ('state', '=', 'done'),
            ])
            line.actual_cost = sum(p.total for p in payments)

    @api.depends('actual_cost', 'price_subtotal', 'display_type')
    def _compute_difference_cost(self):
        for line in self:
            if line.display_type:
                line.difference_cost = 0.0
                continue
            line.difference_cost = (line.actual_cost or 0.0) - (line.price_subtotal or 0.0)

    @api.depends('price_subtotal', 'tax_id', 'currency_id', 'display_type')
    def _compute_total_with_tax(self):
        for rec in self:
            if rec.display_type:
                rec.price_tax = 0.0
                rec.price_total = 0.0
                continue

            subtotal = rec.price_subtotal or 0.0
            price_tax = 0.0
            price_total = subtotal

            if subtotal and rec.tax_id:
                res = rec.tax_id.compute_all(subtotal, currency=rec.currency_id, quantity=1)
                price_tax = res['total_included'] - res['total_excluded']
                price_total = res['total_included']

            rec.price_tax = price_tax
            rec.price_total = price_total

    @api.depends('sale_order_line_id')
    def _compute_is_from_sale_order(self):
        for line in self:
            line.is_from_sale_order = bool(line.sale_order_line_id)

    @api.depends(
        'material_line_ids.price_total',
        'expense_line_ids.price_total',
        'labor_expense_line_ids.price_total',
        'quantity',
        'display_type'
    )
    def _compute_price_subtotal(self):
        for rec in self:
            if rec.display_type:
                rec.price_unit = 0.0
                rec.price_subtotal = 0.0
                continue

            total_material = sum(line.price_total for line in rec.material_line_ids)
            total_expense = sum(line.price_total for line in rec.expense_line_ids)
            total_labor = sum(line.price_total for line in rec.labor_expense_line_ids)

            total_all = total_material + total_expense + total_labor
            rec.price_unit = total_all
            rec.price_subtotal = total_all * (rec.quantity or 0.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.unit = rec.product_id.uom_id
                rec.name = rec.product_id.display_name 
                if rec.product_id.detailed_type == 'service' and rec.sale_order_line_id:
                    rec.price_unit = rec.sale_order_line_id.price_unit
            else:
                rec.unit = False

    @api.depends('labor_expense_line_ids.price_total', 'material_line_ids.price_total', 'expense_line_ids.price_total', 'display_type')
    def _compute_expense_totals(self):
        for rec in self:
            if rec.display_type:
                rec.labor_total_cost = 0.0
                rec.material_total_cost = 0.0
                rec.other_total_cost = 0.0
                continue
            rec.labor_total_cost = sum(rec.labor_expense_line_ids.mapped('price_total'))
            rec.material_total_cost = sum(rec.material_line_ids.mapped('price_total'))
            rec.other_total_cost = sum(rec.expense_line_ids.mapped('price_total'))

    def action_open_copy_cost_wizard(self):
        self.ensure_one()
        if self.display_type:
            raise UserError("Không thể sao chép chi phí cho dòng nhóm/ghi chú.")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sao chép chi phí từ hạng mục khác',
            'res_model': 'cost.estimate.copy.cost.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_target_line_id': self.id,
                'default_cost_estimate_id': self.cost_estimate_id.id,
            }
        }