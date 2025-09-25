from odoo import models,api,fields

class ProjectTask(models.Model):
    _inherit = "project.task"
    partner_id = fields.Many2one(
        'res.partner',
        string="Khách hàng",
        related="project_id.partner_id",
        store=True,
        readonly=True
    )
    @api.onchange('parent_id')
    def _onchange_parent_id_project(self):
        if self.parent_id:
            self.project_id = self.parent_id.project_id.id
            if self.parent_id.project_sale_order_id:
                self.project_sale_order_id = self.parent_id.project_sale_order_id
            if self.parent_id.sale_order_line_id:
                self.sale_order_line_id = self.parent_id.sale_order_line_id

    @api.model
    def create(self, vals):
        if vals.get('parent_id'):
            parent_task = self.browse(vals['parent_id'])
            if parent_task:
                if parent_task.project_id and not vals.get('project_id'):
                    vals['project_id'] = parent_task.project_id.id
                if parent_task.project_sale_order_id and not vals.get('project_sale_order_id'):
                    vals['project_sale_order_id'] = parent_task.project_sale_order_id.id
                if parent_task.sale_order_line_id and not vals.get('sale_order_line_id'):
                    vals['sale_order_line_id'] = parent_task.sale_order_line_id.id
        return super().create(vals)

