from odoo import models, fields, api
class CostEstimateLine(models.Model):
    _inherit = 'cost.estimate.line'
    actual_cost = fields.Float(
        string="Chi phí thực tế",
        compute="_compute_actual_cost",
        store=False
    )
    name = fields.Char(compute="_compute_name", store=True)

    @api.depends('cost_estimate_id.project_id.name', 'product_id', 'quantity')
    def _compute_name(self):
        for line in self:
            line.name = f"[{line.cost_estimate_id.project_id.name}] {line.product_id.display_name or ''} ({line.quantity or 0})"

    @api.depends('product_id', 'quantity')
    def _compute_actual_cost(self):
        for line in self:
            payments = self.env['account.payment.request'].search([
                ('cost_estimate_line_id', '=', line.id),
                ('project_id', '=', line.cost_estimate_id.project_id.id),
                ('state', '=', 'done'),
            ])
            line.actual_cost = sum(p.total for p in payments)