from odoo import models, fields, api

class AssignUserWizard(models.TransientModel):
    _name = "assign.user.wizard"
    _description = "Wizard Phân công User cho Task"

    user_ids = fields.Many2many("res.users", string="Người phụ trách", required=True)

    def action_assign(self):
        active_ids = self.env.context.get("active_ids", [])
        tasks = self.env["project.task"].browse(active_ids)
        for task in tasks:
            task.user_ids = [(4, user.id) for user in self.user_ids]
        return {"type": "ir.actions.act_window_close"}
