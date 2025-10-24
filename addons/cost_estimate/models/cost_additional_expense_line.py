from odoo import models, fields, api

class CostAdditionalExpenseLine(models.Model):
    _name = 'cost.additional.expense.line'
    _description = 'Dòng chi phí bổ sung'

    expense_id = fields.Many2one(
        'cost.additional.expense',
        string='Phiếu chi phí bổ sung',
        ondelete='cascade',
        required=True
    )
    cost_estimate_id = fields.Many2one(
        'cost.estimate',
        string='Dự toán',
        required=True
    )
    name = fields.Char(string='Mô tả')
    quantity = fields.Float(string='Số lượng', default=1.0)
    price_unit = fields.Monetary(string='Đơn giá')
    uom_id= fields.Many2one('uom.uom', string='Đơn vị')

    price_subtotal = fields.Monetary(
        string='Thành tiền trước thuế',
        compute='_compute_amount',
        store=True
    )
    price_tax = fields.Monetary(
        string='Thuế VAT',
        compute='_compute_amount',
        store=True
    )
    price_total = fields.Monetary(
        string='Thành tiền sau thuế',
        compute='_compute_amount',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='expense_id.currency_id',
        store=True
    )
    tax_id = fields.Many2one(
        'account.tax',
        string='Thuế áp dụng',
        domain=[('type_tax_use', '=', 'sale')]
    )
    project_id = fields.Many2one('project.project', string='Dự án', related='cost_estimate_id.project_id', store=True)
    
    display_name = fields.Char(
    string='Tên hiển thị',
    compute='_compute_display_name',
    store=True
)

    @api.depends('expense_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.expense_id.name or ''
    @api.onchange('expense_id')
    def _onchange_expense_id(self):
        if self.expense_id:
            # gán đơn giá từ cha xuống line
            self.price_unit = self.expense_id.price_unit
            # gán thuế nếu muốn copy luôn
            if self.expense_id.tax_id:
                self.tax_id = self.expense_id.tax_id

    @api.depends('quantity', 'price_unit', 'tax_id', 'expense_id.currency_id')
    def _compute_amount(self):
        for line in self:
            subtotal = line.quantity * (line.price_unit or 0.0)
            taxes = 0.0

            if line.tax_id:
                res = line.tax_id.compute_all(
                    line.price_unit,
                    currency=line.expense_id.currency_id or line.currency_id,
                    quantity=line.quantity
                )
                subtotal = res['total_excluded']
                taxes = sum(t.get('amount', 0.0) for t in res['taxes'])
                line.price_total = res['total_included']
            else:
                line.price_total = subtotal

            line.price_subtotal = subtotal
            line.price_tax = taxes
