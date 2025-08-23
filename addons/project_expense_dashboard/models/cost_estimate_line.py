from odoo import models, fields, api
class CostEstimateLine(models.Model):
    _inherit = 'cost.estimate.line'
    actual_cost = fields.Float(
        string="Chi phí thực tế",
        compute="_compute_actual_cost",
        store=False
    )
    name = fields.Char(compute="_compute_name", store=True)
    difference_cost = fields.Float(
        string="Chênh lệch",
        compute="_compute_difference_cost",
        store=False
    )

    @api.depends('cost_estimate_id.project_id.name', 'product_id', 'quantity')
    def _compute_name(self):
        for rec in self:
            stt = 0
            if rec.cost_estimate_id and rec.id:
                lines = rec.cost_estimate_id.line_ids.sorted(lambda l: l.create_date or l.id)
                for idx, line in enumerate(lines, start=1):
                    if line.id == rec.id:
                        stt = idx
                        break
            rec.name = f"{stt}. [{rec.cost_estimate_id.project_id.name}] {rec.product_id.display_name or ''}"

    @api.depends('product_id', 'quantity')
    def _compute_actual_cost(self):
        for line in self:
            payments = self.env['account.payment.request'].search([
                ('cost_estimate_line_id', '=', line.id),
                ('project_id', '=', line.cost_estimate_id.project_id.id),
                ('state', '=', 'done'),
            ])
            line.actual_cost = sum(p.total for p in payments)
    @api.depends('actual_cost', 'price_subtotal')
    def _compute_difference_cost(self):
        for line in self:
            line.difference_cost = (line.actual_cost or 0.0) - (line.price_subtotal or 0.0)