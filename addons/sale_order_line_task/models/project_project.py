from odoo import models, _

class ProjectProject(models.Model):
    _inherit = "project.project"

    def action_open_create_tasks_wizard(self):
        self.ensure_one()
        return {
            "name": "Tạo nhiệm vụ từ đơn hàng",
            "type": "ir.actions.act_window",
            "res_model": "wizard.create.tasks.from.sale",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "default_sale_order_id": self.sale_order_id.id,
                "default_sale_order_line_ids": self.sale_order_id.order_line.ids,
            }
        }