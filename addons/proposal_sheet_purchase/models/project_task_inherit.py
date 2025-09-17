# models/project_task_inherit.py
from odoo import models, fields, api, _

class ProjectTask(models.Model):
    _inherit = "project.task"

    purchase_order_count = fields.Integer(
        string="Số PO",
        compute="_compute_purchase_order_count",
    )
    def _compute_purchase_order_count(self):
        for task in self:
            task.purchase_order_count = self.env['purchase.order'].search_count([
                ('proposal_sheet_id.task_id', '=', task.id)
            ])

    def action_view_task_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Đơn mua hàng'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            # Dùng domain dựa trên field lưu trong DB (tránh field compute store=False)
            'domain': [('proposal_sheet_id.task_id', '=', self.id)],
            'target': 'current',
            'context': {
                # tuỳ chọn: preset search/domain
                'default_proposal_sheet_id': False,
            },
        }