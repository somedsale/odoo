from odoo import models, fields, api

class ProposalSheet(models.Model):
    _inherit = 'proposal.sheet'

    cost_estimate_line_id = fields.Many2one(
        'cost.estimate.line',
        string='Hạng mục dự toán',
        domain="[('cost_estimate_id.project_id', '=', project_id)]"
    )

    @api.onchange('project_id', 'product_id')
    def _onchange_project_product(self):
        """Tự tìm hạng mục trong dự toán khi chọn dự án + sản phẩm"""
        if self.project_id:
            line = self.env['cost.estimate.line'].search([
                ('project_id', '=', self.project_id.id),
            ], limit=1)
            self.cost_estimate_line_id = line.id if line else False
    other_estimate_item = fields.Many2one(
        comodel_name="estimate.item.other",
        string="Hạng mục khác",
    )
    estimate_choice = fields.Selection([
        ("estimate", "Chọn từ dự toán"),
        ("other", "Khác"),
    ], string="Loại hạng mục", default="estimate", required=True)
